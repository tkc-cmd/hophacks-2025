"""Deepgram streaming speech-to-text client."""

import asyncio
import json
import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from deepgram import Deepgram, DeepgramClient, LiveOptions, LiveTranscriptionEvents
from server.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TranscriptResult:
    """Represents a transcript result from Deepgram."""
    text: str
    confidence: float
    is_final: bool
    timestamp: datetime
    duration: Optional[float] = None
    words: Optional[list] = None


class DeepgramSTTClient:
    """Streaming speech-to-text client using Deepgram."""
    
    def __init__(
        self,
        on_transcript: Optional[Callable[[TranscriptResult], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ):
        self.client = DeepgramClient(settings.deepgram_api_key)
        self.connection = None
        self.is_connected = False
        self.on_transcript = on_transcript
        self.on_error = on_error
        
        # Configure live transcription options
        self.live_options = LiveOptions(
            model="nova-2",
            language="en-US",
            smart_format=True,
            interim_results=True,
            utterance_end_ms=1000,  # 1 second of silence to end utterance
            vad_events=True,  # Voice activity detection
            punctuate=True,
            diarize=False,  # Single speaker
            encoding="linear16",
            sample_rate=16000,
            channels=1,
            endpointing=True,
            keywords=["pharmacy", "prescription", "refill", "medication", "doctor", "CVS", "Walgreens", "Rite Aid"]
        )
    
    async def start_connection(self) -> bool:
        """Start the Deepgram connection."""
        try:
            # Create the connection
            self.connection = self.client.listen.asynclive.v("1")
            
            # Set up event handlers
            self.connection.on(LiveTranscriptionEvents.Open, self._on_open)
            self.connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
            self.connection.on(LiveTranscriptionEvents.Error, self._on_error)
            self.connection.on(LiveTranscriptionEvents.Close, self._on_close)
            self.connection.on(LiveTranscriptionEvents.Metadata, self._on_metadata)
            self.connection.on(LiveTranscriptionEvents.UtteranceEnd, self._on_utterance_end)
            
            # Start the connection
            if await self.connection.start(self.live_options):
                self.is_connected = True
                logger.info("Deepgram connection started successfully")
                return True
            else:
                logger.error("Failed to start Deepgram connection")
                return False
                
        except Exception as e:
            logger.error(f"Error starting Deepgram connection: {e}")
            if self.on_error:
                self.on_error(e)
            return False
    
    async def send_audio(self, audio_data: bytes) -> bool:
        """Send audio data to Deepgram."""
        if not self.is_connected or not self.connection:
            logger.warning("Attempted to send audio but connection is not active")
            return False
        
        try:
            await self.connection.send(audio_data)
            return True
        except Exception as e:
            logger.error(f"Error sending audio to Deepgram: {e}")
            if self.on_error:
                self.on_error(e)
            return False
    
    async def finish(self):
        """Finish the current audio stream and get final results."""
        if self.connection:
            try:
                await self.connection.finish()
            except Exception as e:
                logger.error(f"Error finishing Deepgram stream: {e}")
    
    async def close(self):
        """Close the Deepgram connection."""
        if self.connection:
            try:
                await self.connection.finish()
                self.is_connected = False
                logger.info("Deepgram connection closed")
            except Exception as e:
                logger.error(f"Error closing Deepgram connection: {e}")
    
    def _on_open(self, *args):
        """Handle connection open event."""
        logger.info("Deepgram connection opened")
        self.is_connected = True
    
    def _on_transcript(self, *args, **kwargs):
        """Handle transcript events."""
        try:
            # Extract the result from the event
            result = args[0] if args else kwargs.get('result')
            
            if not result:
                return
            
            # Parse the transcript result
            channel = result.channel
            alternatives = channel.alternatives
            
            if not alternatives:
                return
            
            # Get the best alternative
            alternative = alternatives[0]
            transcript_text = alternative.transcript.strip()
            confidence = alternative.confidence
            
            # Skip empty transcripts
            if not transcript_text:
                return
            
            # Determine if this is a final result
            is_final = result.is_final
            
            # Create transcript result
            transcript_result = TranscriptResult(
                text=transcript_text,
                confidence=confidence,
                is_final=is_final,
                timestamp=datetime.now(),
                words=getattr(alternative, 'words', None)
            )
            
            logger.debug(f"Transcript ({'final' if is_final else 'interim'}): {transcript_text}")
            
            # Call the callback if provided
            if self.on_transcript:
                try:
                    self.on_transcript(transcript_result)
                except Exception as e:
                    logger.error(f"Error in transcript callback: {e}")
            
        except Exception as e:
            logger.error(f"Error processing transcript: {e}")
            if self.on_error:
                self.on_error(e)
    
    def _on_error(self, *args, **kwargs):
        """Handle error events."""
        error = args[0] if args else kwargs.get('error', 'Unknown error')
        logger.error(f"Deepgram error: {error}")
        
        if self.on_error:
            self.on_error(Exception(str(error)))
    
    def _on_close(self, *args):
        """Handle connection close event."""
        logger.info("Deepgram connection closed")
        self.is_connected = False
    
    def _on_metadata(self, *args, **kwargs):
        """Handle metadata events."""
        metadata = args[0] if args else kwargs.get('metadata')
        logger.debug(f"Deepgram metadata: {metadata}")
    
    def _on_utterance_end(self, *args, **kwargs):
        """Handle utterance end events."""
        logger.debug("Utterance ended")
        
        # This can be used to trigger processing of the complete utterance
        # For now, we'll just log it


class DeepgramManager:
    """Manager for Deepgram connections per call session."""
    
    def __init__(self):
        self.connections: Dict[str, DeepgramSTTClient] = {}
    
    async def create_connection(
        self,
        call_sid: str,
        on_transcript: Optional[Callable[[str, TranscriptResult], None]] = None,
        on_error: Optional[Callable[[str, Exception], None]] = None
    ) -> Optional[DeepgramSTTClient]:
        """Create a new Deepgram connection for a call session."""
        
        # Wrap callbacks to include call_sid
        def transcript_callback(result: TranscriptResult):
            if on_transcript:
                on_transcript(call_sid, result)
        
        def error_callback(error: Exception):
            if on_error:
                on_error(call_sid, error)
        
        # Create client
        client = DeepgramSTTClient(
            on_transcript=transcript_callback,
            on_error=error_callback
        )
        
        # Start connection
        if await client.start_connection():
            self.connections[call_sid] = client
            return client
        else:
            return None
    
    async def send_audio(self, call_sid: str, audio_data: bytes) -> bool:
        """Send audio data for a specific call session."""
        client = self.connections.get(call_sid)
        if client:
            return await client.send_audio(audio_data)
        return False
    
    async def close_connection(self, call_sid: str):
        """Close connection for a call session."""
        client = self.connections.get(call_sid)
        if client:
            await client.close()
            del self.connections[call_sid]
    
    async def close_all_connections(self):
        """Close all active connections."""
        for call_sid in list(self.connections.keys()):
            await self.close_connection(call_sid)


# Global Deepgram manager instance
deepgram_manager = DeepgramManager()
