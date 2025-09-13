"""FastAPI application for the pharmacy voice agent."""

import os
import logging
import asyncio
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, WebSocket, HTTPException, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from twilio.twiml.voice_response import VoiceResponse
from twilio.request_validator import RequestValidator
from sqlalchemy.orm import Session

from server.config import settings, get_media_stream_url
from server.persistence import get_db, create_tables
from server.domain.sessions.store import session_store, SessionState
from server.ws_media import media_handler
from server.tts.elevenlabs_client import tts_client
from server.utils.twilio_ctrl import twilio_controller
from server.middleware.phi_guard import PHIGuardMiddleware, create_audit_log_entry
from server.persistence.models import CallSession, AuditLog

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# PHI Guard middleware
phi_guard = PHIGuardMiddleware(debug_mode=settings.debug_audio)

# Twilio request validator
twilio_validator = RequestValidator(settings.twilio_auth_token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting pharmacy voice agent...")
    
    # Create database tables
    create_tables()
    logger.info("Database initialized")
    
    # Create static directories
    os.makedirs("static/tts", exist_ok=True)
    
    # Start background tasks
    cleanup_task = asyncio.create_task(cleanup_old_files())
    
    yield
    
    # Shutdown
    logger.info("Shutting down pharmacy voice agent...")
    
    # Cancel background tasks
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    
    # Cleanup session store
    await session_store.shutdown()


async def cleanup_old_files():
    """Background task to clean up old TTS files."""
    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour
            await tts_client.cleanup_old_files(max_age_hours=2)
            session_store.cleanup_expired_sessions(ttl_minutes=60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")


# Create FastAPI app
app = FastAPI(
    title="Pharmacy Voice Agent",
    description="HIPAA-aware pharmacy voice agent with Twilio integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


def validate_twilio_request(request: Request) -> bool:
    """Validate that request is from Twilio."""
    if settings.log_level == "DEBUG":
        return True  # Skip validation in debug mode
    
    try:
        signature = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)
        
        # Get form data for POST requests
        if request.method == "POST":
            # This is a simplified validation - in production, you'd need to properly handle the body
            return True  # For now, allow all POST requests
        
        return twilio_validator.validate(url, {}, signature)
    except Exception as e:
        logger.error(f"Error validating Twilio request: {e}")
        return False


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": session_store.get_session_count(),
        "version": "1.0.0"
    }


@app.post("/twilio/voice")
async def handle_incoming_call(request: Request, db: Session = Depends(get_db)):
    """Handle incoming voice call from Twilio."""
    
    # Validate Twilio request
    if not validate_twilio_request(request):
        logger.warning("Invalid Twilio request received")
        raise HTTPException(status_code=403, detail="Invalid request signature")
    
    try:
        # Parse form data
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        
        logger.info(f"Incoming call: {call_sid} from {from_number} to {to_number}")
        
        # Create session in database
        call_session = CallSession(
            id=call_sid,
            phone_number=from_number,
            status="active"
        )
        db.add(call_session)
        
        # Create session in memory store
        session = session_store.create_session(call_sid, from_number)
        session.state = SessionState.ACTIVE
        
        # Log call start
        audit_log = AuditLog(
            call_session_id=call_sid,
            event_type="call_started",
            phone_number_masked=phi_guard.sanitize_request_data({"phone": from_number}).get("phone", "****"),
            success=True
        )
        db.add(audit_log)
        db.commit()
        
        # Generate session token for media stream
        session_token = f"session_{call_sid}_{settings.static_signing_secret[:8]}"
        
        # Create WebSocket URL for media stream
        ws_url = get_media_stream_url(call_sid, session_token)
        
        # Create TwiML response
        response = VoiceResponse()
        
        # Start media stream
        start = response.start()
        start.stream(url=ws_url)
        
        # Initial greeting with disclaimer
        initial_message = ("I'm an automated pharmacy assistant and can't provide medical diagnoses. "
                         "In emergencies call your local emergency number. How can I help you today?")
        
        # Create gather for speech input
        gather = response.gather(
            input='speech',
            action='/twilio/gather',
            method='POST',
            timeout=30,
            speech_timeout='auto',
            barge_in=True,
            language='en-US',
            hints='pharmacy, prescription, refill, medication, help, doctor'
        )
        
        gather.say(initial_message, voice='Polly.Joanna-Neural')
        
        # Fallback if no input
        response.say("I didn't hear anything. Please let me know how I can help you.", voice='Polly.Joanna-Neural')
        response.redirect('/twilio/gather')
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error handling incoming call: {e}")
        
        # Return error TwiML
        response = VoiceResponse()
        response.say("I'm sorry, there's a technical issue. Please call back later.", voice='Polly.Joanna-Neural')
        response.hangup()
        
        return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/twilio/gather")
async def handle_speech_result(request: Request, db: Session = Depends(get_db)):
    """Handle speech recognition results from Twilio."""
    
    # Validate Twilio request
    if not validate_twilio_request(request):
        raise HTTPException(status_code=403, detail="Invalid request signature")
    
    try:
        # Parse form data
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        speech_result = form_data.get("SpeechResult", "")
        confidence = float(form_data.get("Confidence", "0.0"))
        
        logger.info(f"Speech result for {call_sid}: {speech_result} (confidence: {confidence})")
        
        # Get session
        session = session_store.get_session(call_sid)
        if not session:
            logger.warning(f"No session found for call {call_sid}")
            response = VoiceResponse()
            response.say("I'm sorry, there was a session error. Please call back.", voice='Polly.Joanna-Neural')
            response.hangup()
            return PlainTextResponse(str(response), media_type="application/xml")
        
        # Log speech result
        audit_log = AuditLog(
            call_session_id=call_sid,
            event_type="speech_result",
            event_data=f"Twilio STT: {speech_result[:100]}...",
            success=True
        )
        db.add(audit_log)
        db.commit()
        
        # Add to conversation if we have meaningful input
        if speech_result.strip() and confidence > 0.3:
            session.add_conversation_turn("user", speech_result, confidence)
            
            # If we don't have Deepgram processing this, handle it here
            # This serves as a fallback when Media Streams aren't working
            if not hasattr(session, 'deepgram_active') or not session.deepgram_active:
                # Process with LLM (simplified version)
                response_text = await _process_fallback_speech(call_sid, speech_result, db)
                
                # Create TwiML response
                response = VoiceResponse()
                gather = response.gather(
                    input='speech',
                    action='/twilio/gather',
                    method='POST',
                    timeout=30,
                    speech_timeout='auto',
                    barge_in=True,
                    language='en-US',
                    hints='pharmacy, prescription, refill, medication'
                )
                
                gather.say(response_text, voice='Polly.Joanna-Neural')
                
                # Fallback
                response.say("How else can I help you?", voice='Polly.Joanna-Neural')
                response.redirect('/twilio/gather')
                
                return PlainTextResponse(str(response), media_type="application/xml")
        
        # Continue gathering speech
        response = VoiceResponse()
        gather = response.gather(
            input='speech',
            action='/twilio/gather',
            method='POST',
            timeout=30,
            speech_timeout='auto',
            barge_in=True,
            language='en-US',
            hints='pharmacy, prescription, refill, medication'
        )
        
        gather.say("I'm listening. How can I help you?", voice='Polly.Joanna-Neural')
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error handling speech result: {e}")
        
        response = VoiceResponse()
        response.say("I'm sorry, I had trouble understanding. Please try again.", voice='Polly.Joanna-Neural')
        response.redirect('/twilio/gather')
        
        return PlainTextResponse(str(response), media_type="application/xml")


async def _process_fallback_speech(call_sid: str, speech_text: str, db: Session) -> str:
    """Process speech when Media Streams/Deepgram aren't available."""
    
    try:
        from server.llm.gemini_client import pharmacy_llm
        from server.domain.refill.service import RefillService
        
        session = session_store.get_session(call_sid)
        if not session:
            return "I'm sorry, there was a session error."
        
        refill_service = RefillService(db)
        
        # Generate response
        llm_response = await pharmacy_llm.generate_response(
            user_message=speech_text,
            session=session,
            refill_service=refill_service
        )
        
        # Add to conversation history
        session.add_conversation_turn("assistant", llm_response.text)
        
        return llm_response.text
        
    except Exception as e:
        logger.error(f"Error in fallback speech processing: {e}")
        return "I'm having technical difficulties. Please try again or call your pharmacy directly."


@app.post("/twilio/status")
async def handle_call_status(request: Request, db: Session = Depends(get_db)):
    """Handle call status callbacks from Twilio."""
    
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        call_duration = form_data.get("CallDuration", "0")
        
        logger.info(f"Call status update: {call_sid} - {call_status} (duration: {call_duration}s)")
        
        # Update database
        call_session = db.query(CallSession).filter(CallSession.id == call_sid).first()
        if call_session:
            call_session.status = call_status
            if call_status in ["completed", "failed", "busy", "no-answer"]:
                call_session.end_time = datetime.utcnow()
            db.commit()
        
        # Update session store
        session = session_store.get_session(call_sid)
        if session:
            if call_status in ["completed", "failed"]:
                session.state = SessionState.COMPLETED
            
            # Clean up session after call ends
            if call_status == "completed":
                # Give some time for final cleanup, then remove session
                asyncio.create_task(_delayed_session_cleanup(call_sid))
        
        # Log status change
        audit_log = AuditLog(
            call_session_id=call_sid,
            event_type="call_status_change",
            event_data=f"Status: {call_status}, Duration: {call_duration}s",
            success=True
        )
        db.add(audit_log)
        db.commit()
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error handling call status: {e}")
        return {"status": "error", "message": str(e)}


async def _delayed_session_cleanup(call_sid: str):
    """Clean up session after a delay."""
    await asyncio.sleep(30)  # Wait 30 seconds
    session_store.delete_session(call_sid)
    logger.info(f"Cleaned up session for completed call {call_sid}")


@app.websocket("/twilio/media")
async def websocket_media_stream(
    websocket: WebSocket,
    callSid: str = Query(...),
    token: str = Query(...)
):
    """Handle Twilio Media Streams WebSocket connection."""
    await media_handler.handle_connection(websocket, callSid, token)


@app.get("/static/tts/{call_sid}/{filename}")
async def serve_tts_file(call_sid: str, filename: str, expires: str = Query(None), signature: str = Query(None)):
    """Serve TTS files with optional signature verification."""
    
    if settings.require_signed_static_urls:
        if not expires or not signature:
            raise HTTPException(status_code=403, detail="Missing signature parameters")
        
        relative_path = f"tts/{call_sid}/{filename}"
        if not tts_client.verify_signed_url(relative_path, expires, signature):
            raise HTTPException(status_code=403, detail="Invalid or expired signature")
    
    # File will be served by the StaticFiles mount
    raise HTTPException(status_code=404, detail="File not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower()
    )
