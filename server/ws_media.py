"""Twilio Media Streams WebSocket endpoint."""

import json
import base64
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from server.config import settings
from server.domain.sessions.store import session_store, SessionState, TTSJob
from server.stt.deepgram_client import deepgram_manager, TranscriptResult
from server.llm.gemini_client import pharmacy_llm
from server.tts.elevenlabs_client import tts_client
from server.utils.audio import mulaw_to_linear16, decode_twilio_audio, VoiceActivityDetector, SentenceBoundaryDetector
from server.utils.twilio_ctrl import twilio_controller
from server.persistence import get_db
from server.domain.refill.service import RefillService
from server.middleware.phi_guard import create_audit_log_entry

logger = logging.getLogger(__name__)


class MediaStreamHandler:
    """Handles Twilio Media Streams WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.vad_detectors: Dict[str, VoiceActivityDetector] = {}
        self.sentence_detectors: Dict[str, SentenceBoundaryDetector] = {}
        self.audio_buffers: Dict[str, bytes] = {}
    
    async def handle_connection(self, websocket: WebSocket, call_sid: str, token: str):
        """Handle a new Media Streams connection."""
        
        # Accept connection first
        await websocket.accept()
        
        # Validate token (basic implementation)
        if not self._validate_token(call_sid, token):
            logger.warning(f"Invalid token for call {call_sid}")
            await websocket.close(code=1008, reason="Invalid token")
            return
        self.active_connections[call_sid] = websocket
        
        # Initialize session if not exists
        session = session_store.get_session(call_sid)
        if not session:
            # Create session with placeholder phone number (will be updated from Twilio webhook)
            session = session_store.create_session(call_sid, "unknown")
        
        # Initialize audio processing components
        self.vad_detectors[call_sid] = VoiceActivityDetector()
        self.sentence_detectors[call_sid] = SentenceBoundaryDetector()
        self.audio_buffers[call_sid] = b""
        
        # Start Deepgram connection
        deepgram_client = await deepgram_manager.create_connection(
            call_sid=call_sid,
            on_transcript=self._on_transcript,
            on_error=self._on_deepgram_error
        )
        
        if not deepgram_client:
            logger.error(f"Failed to create Deepgram connection for {call_sid}")
            await websocket.close(code=1011, reason="STT service unavailable")
            return
        
        logger.info(f"Media stream started for call {call_sid}")
        
        try:
            # Handle messages
            async for message in websocket.iter_text():
                await self._handle_message(call_sid, message)
                
        except WebSocketDisconnect:
            logger.info(f"Media stream disconnected for call {call_sid}")
        except Exception as e:
            logger.error(f"Error in media stream for call {call_sid}: {e}")
        finally:
            await self._cleanup_connection(call_sid)
    
    def _validate_token(self, call_sid: str, token: str) -> bool:
        """Validate the session token."""
        # Simple token validation - in production, use proper JWT or signed tokens
        expected_token = f"session_{call_sid}_{settings.static_signing_secret[:8]}"
        return token == expected_token
    
    async def _handle_message(self, call_sid: str, message: str):
        """Handle incoming WebSocket message."""
        
        try:
            data = json.loads(message)
            event = data.get('event')
            
            if event == 'start':
                await self._handle_start(call_sid, data)
            elif event == 'media':
                await self._handle_media(call_sid, data)
            elif event == 'stop':
                await self._handle_stop(call_sid, data)
            else:
                logger.warning(f"Unknown event type: {event}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in media stream: {e}")
        except Exception as e:
            logger.error(f"Error handling media message: {e}")
    
    async def _handle_start(self, call_sid: str, data: Dict[str, Any]):
        """Handle media stream start event."""
        
        stream_sid = data.get('streamSid')
        logger.info(f"Media stream {stream_sid} started for call {call_sid}")
        
        # Update session
        session = session_store.get_session(call_sid)
        if session:
            session.state = SessionState.ACTIVE
    
    async def _handle_media(self, call_sid: str, data: Dict[str, Any]):
        """Handle incoming media frames."""
        
        try:
            # Extract audio data
            media_data = data.get('media', {})
            payload = media_data.get('payload')
            sequence_number = data.get('sequenceNumber', 0)
            
            if not payload:
                return
            
            # Decode audio (8kHz μ-law from Twilio)
            mulaw_audio = decode_twilio_audio(payload)
            
            # Convert to linear PCM 16-bit for Deepgram
            linear_audio = mulaw_to_linear16(mulaw_audio)
            
            # Resample from 8kHz to 16kHz for Deepgram
            # Simple upsampling by repeating samples
            upsampled_audio = b""
            for i in range(0, len(linear_audio), 2):
                sample = linear_audio[i:i+2]
                upsampled_audio += sample + sample  # Repeat each sample
            
            # Voice Activity Detection
            session = session_store.get_session(call_sid)
            if session:
                vad = self.vad_detectors.get(call_sid)
                if vad:
                    is_speech, state_changed = vad.process_frame(linear_audio)
                    
                    # If we detect speech while playing audio, trigger barge-in
                    if is_speech and session.currently_playing and not session.barge_in_flag:
                        logger.info(f"Barge-in detected for call {call_sid}")
                        session.set_barge_in()
                        
                        # Stop current playback
                        await twilio_controller.stop_current_playback(call_sid)
            
            # Buffer audio for Deepgram
            buffer = self.audio_buffers.get(call_sid, b"")
            buffer += upsampled_audio
            self.audio_buffers[call_sid] = buffer
            
            # Send buffered audio to Deepgram when we have enough
            if len(buffer) >= 3200:  # ~100ms at 16kHz
                await deepgram_manager.send_audio(call_sid, buffer)
                self.audio_buffers[call_sid] = b""
            
        except Exception as e:
            logger.error(f"Error processing media frame for call {call_sid}: {e}")
    
    async def _handle_stop(self, call_sid: str, data: Dict[str, Any]):
        """Handle media stream stop event."""
        
        stream_sid = data.get('streamSid')
        logger.info(f"Media stream {stream_sid} stopped for call {call_sid}")
        
        # Update session
        session = session_store.get_session(call_sid)
        if session:
            session.state = SessionState.COMPLETED
    
    async def _on_transcript(self, call_sid: str, result: TranscriptResult):
        """Handle transcript results from Deepgram."""
        
        try:
            session = session_store.get_session(call_sid)
            if not session:
                return
            
            if result.is_final:
                # Final transcript
                session.stt_final = result.text
                session.stt_confidence = result.confidence
                
                # Add to conversation history
                session.add_conversation_turn("user", result.text, result.confidence)
                
                # Clear barge-in state if it was active
                if session.barge_in_flag:
                    session.clear_barge_in()
                
                logger.info(f"Final transcript for {call_sid}: {result.text}")
                
                # Process the final transcript with LLM
                await self._process_user_input(call_sid, result.text)
                
            else:
                # Interim transcript
                session.stt_partial = result.text
                
                # Check for sentence boundaries in partial transcript
                sentence_detector = self.sentence_detectors.get(call_sid)
                if sentence_detector:
                    sentences = sentence_detector.find_sentences(result.text)
                    
                    # If we have complete sentences, we can start processing early
                    if len(sentences) > 1:  # More than one sentence means first is complete
                        complete_sentence = sentences[0]
                        if sentence_detector.is_complete_sentence(complete_sentence):
                            logger.info(f"Early sentence detection for {call_sid}: {complete_sentence}")
                            # Could start LLM processing here for lower latency
        
        except Exception as e:
            logger.error(f"Error processing transcript for call {call_sid}: {e}")
    
    async def _on_deepgram_error(self, call_sid: str, error: Exception):
        """Handle Deepgram errors."""
        logger.error(f"Deepgram error for call {call_sid}: {error}")
        
        # Try to recover by creating a new connection
        try:
            await deepgram_manager.close_connection(call_sid)
            await asyncio.sleep(1)
            
            new_client = await deepgram_manager.create_connection(
                call_sid=call_sid,
                on_transcript=self._on_transcript,
                on_error=self._on_deepgram_error
            )
            
            if new_client:
                logger.info(f"Recovered Deepgram connection for call {call_sid}")
            else:
                # Fallback to Twilio's built-in speech recognition
                await twilio_controller.say_with_barge_in(
                    call_sid, 
                    "I'm having trouble with speech recognition. Please speak clearly."
                )
        
        except Exception as e:
            logger.error(f"Failed to recover Deepgram connection for call {call_sid}: {e}")
    
    async def _process_user_input(self, call_sid: str, user_text: str):
        """Process user input with the LLM and generate response."""
        
        try:
            session = session_store.get_session(call_sid)
            if not session:
                return
            
            # Mark as processing
            session.state = SessionState.PROCESSING
            session.llm_processing = True
            
            # Get database session for refill service
            db_session = next(get_db())
            try:
                refill_service = RefillService(db_session)
                
                # Generate LLM response
                llm_response = await pharmacy_llm.generate_response(
                    user_message=user_text,
                    session=session,
                    refill_service=refill_service
                )
                
                # Update session with response
                session.llm_final = llm_response.text
                session.llm_processing = False
                
                # Add assistant response to conversation history
                session.add_conversation_turn("assistant", llm_response.text)
                
                # Generate TTS and play response
                await self._generate_and_play_response(call_sid, llm_response.text)
                
            finally:
                db_session.close()
            
        except Exception as e:
            logger.error(f"Error processing user input for call {call_sid}: {e}")
            
            # Fallback response
            fallback_text = "I apologize, but I'm having technical difficulties. Please try again or call your pharmacy directly."
            await self._generate_and_play_response(call_sid, fallback_text)
    
    async def _generate_and_play_response(self, call_sid: str, response_text: str):
        """Generate TTS for response and play it."""
        
        try:
            session = session_store.get_session(call_sid)
            if not session:
                return
            
            # Split response into chunks for better barge-in responsiveness
            chunks = self._split_response_into_chunks(response_text)
            
            for i, chunk in enumerate(chunks):
                if session.barge_in_flag:
                    # User interrupted, stop processing remaining chunks
                    break
                
                # Generate TTS for chunk
                tts_result = await tts_client.synthesize_text(chunk, call_sid)
                
                if tts_result:
                    # Create TTS job
                    job = TTSJob(
                        id=tts_result.job_id,
                        text=chunk,
                        file_url=tts_result.file_url,
                        duration_ms=tts_result.duration_ms,
                        status="completed"
                    )
                    
                    session.add_tts_job(job)
                    
                    # Play the audio
                    session.currently_playing = job.id
                    session.playback_start_time = datetime.now()
                    
                    success = await twilio_controller.play_audio_with_barge_in(
                        call_sid=call_sid,
                        audio_url=tts_result.file_url,
                        hints="pharmacy, prescription, refill, medication"
                    )
                    
                    if success:
                        logger.info(f"Playing TTS chunk {i+1}/{len(chunks)} for call {call_sid}")
                        
                        # Wait for estimated playback duration before next chunk
                        if i < len(chunks) - 1:  # Not the last chunk
                            wait_time = (tts_result.duration_ms / 1000) + 0.5  # Add small buffer
                            await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Failed to play TTS chunk for call {call_sid}")
                        # Fallback to Twilio Say
                        await twilio_controller.say_with_barge_in(call_sid, chunk)
                
                else:
                    # TTS failed, use Twilio Say as fallback
                    logger.warning(f"TTS failed for call {call_sid}, using fallback")
                    await twilio_controller.say_with_barge_in(call_sid, chunk)
            
            # Mark as no longer playing
            session.currently_playing = None
            session.playback_start_time = None
            session.state = SessionState.ACTIVE
            
        except Exception as e:
            logger.error(f"Error generating/playing response for call {call_sid}: {e}")
    
    def _split_response_into_chunks(self, text: str, max_chunk_size: int = 200) -> list:
        """Split response text into chunks for better barge-in experience."""
        
        if len(text) <= max_chunk_size:
            return [text]
        
        # Split by sentences first
        sentence_detector = SentenceBoundaryDetector()
        sentences = sentence_detector.find_sentences(text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def _cleanup_connection(self, call_sid: str):
        """Clean up resources for a disconnected call."""
        
        # Remove from active connections
        if call_sid in self.active_connections:
            del self.active_connections[call_sid]
        
        # Clean up audio processing components
        if call_sid in self.vad_detectors:
            del self.vad_detectors[call_sid]
        
        if call_sid in self.sentence_detectors:
            del self.sentence_detectors[call_sid]
        
        if call_sid in self.audio_buffers:
            del self.audio_buffers[call_sid]
        
        # Close Deepgram connection
        await deepgram_manager.close_connection(call_sid)
        
        # Update session state
        session = session_store.get_session(call_sid)
        if session:
            session.state = SessionState.COMPLETED
        
        logger.info(f"Cleaned up media stream resources for call {call_sid}")


# Global media stream handler
media_handler = MediaStreamHandler()
