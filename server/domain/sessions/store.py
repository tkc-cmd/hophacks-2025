"""Session store for managing call state and conversation history."""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
from enum import Enum
import asyncio
import json
from dataclasses import dataclass, field


class SessionState(str, Enum):
    ACTIVE = "active"
    IDENTITY_PENDING = "identity_pending"
    IDENTITY_VERIFIED = "identity_verified"
    PROCESSING = "processing"
    BARGE_IN = "barge_in"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ConversationTurn:
    """Represents a single turn in the conversation."""
    timestamp: datetime
    speaker: str  # "user" or "assistant"
    text: str
    confidence: float = 1.0
    is_final: bool = True


@dataclass
class TTSJob:
    """Represents a TTS generation job."""
    id: str
    text: str
    file_url: Optional[str] = None
    file_path: Optional[str] = None
    duration_ms: Optional[int] = None
    status: str = "pending"  # pending, processing, completed, failed
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CallSessionData:
    """Complete session data for a call."""
    call_sid: str
    phone_number: str
    start_time: datetime
    state: SessionState = SessionState.ACTIVE
    
    # Identity verification
    identity_verified: bool = False
    patient_name: Optional[str] = None
    patient_dob: Optional[str] = None
    verification_attempts: int = 0
    
    # Speech processing
    stt_partial: str = ""
    stt_final: str = ""
    stt_confidence: float = 0.0
    
    # LLM processing
    llm_partial: str = ""
    llm_final: str = ""
    llm_processing: bool = False
    
    # TTS and playback
    tts_queue: List[TTSJob] = field(default_factory=list)
    currently_playing: Optional[str] = None  # TTS job ID
    playback_start_time: Optional[datetime] = None
    
    # Barge-in handling
    barge_in_flag: bool = False
    barge_in_timestamp: Optional[datetime] = None
    interrupted_content: List[str] = field(default_factory=list)
    
    # Conversation history
    conversation_history: List[ConversationTurn] = field(default_factory=list)
    
    # Metadata
    last_activity: datetime = field(default_factory=datetime.now)
    total_turns: int = 0
    
    def add_conversation_turn(self, speaker: str, text: str, confidence: float = 1.0):
        """Add a turn to conversation history."""
        turn = ConversationTurn(
            timestamp=datetime.now(),
            speaker=speaker,
            text=text,
            confidence=confidence
        )
        self.conversation_history.append(turn)
        self.total_turns += 1
        self.last_activity = datetime.now()
    
    def get_recent_history(self, max_turns: int = 10) -> List[ConversationTurn]:
        """Get recent conversation history."""
        return self.conversation_history[-max_turns:]
    
    def set_barge_in(self):
        """Mark session as in barge-in state."""
        self.barge_in_flag = True
        self.barge_in_timestamp = datetime.now()
        self.state = SessionState.BARGE_IN
        
        # Save any currently playing content for potential resumption
        if self.currently_playing and self.llm_partial:
            self.interrupted_content.append(self.llm_partial)
    
    def clear_barge_in(self):
        """Clear barge-in state."""
        self.barge_in_flag = False
        self.barge_in_timestamp = None
        if self.state == SessionState.BARGE_IN:
            self.state = SessionState.ACTIVE
    
    def add_tts_job(self, job: TTSJob):
        """Add TTS job to queue."""
        self.tts_queue.append(job)
    
    def get_next_tts_job(self) -> Optional[TTSJob]:
        """Get next TTS job to process."""
        for job in self.tts_queue:
            if job.status == "pending":
                return job
        return None
    
    def mark_tts_completed(self, job_id: str, file_url: str, duration_ms: int):
        """Mark TTS job as completed."""
        for job in self.tts_queue:
            if job.id == job_id:
                job.status = "completed"
                job.file_url = file_url
                job.duration_ms = duration_ms
                break
    
    def is_expired(self, ttl_minutes: int = 30) -> bool:
        """Check if session has expired."""
        expiry_time = self.last_activity + timedelta(minutes=ttl_minutes)
        return datetime.now() > expiry_time


class SessionStore:
    """In-memory store for managing call sessions."""
    
    def __init__(self):
        self._sessions: Dict[str, CallSessionData] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_started = False
    
    def create_session(self, call_sid: str, phone_number: str) -> CallSessionData:
        """Create a new session."""
        # Start cleanup task if not already started and event loop is available
        if not self._cleanup_started:
            self._start_cleanup_task()
            
        session = CallSessionData(
            call_sid=call_sid,
            phone_number=phone_number,
            start_time=datetime.now()
        )
        self._sessions[call_sid] = session
        return session
    
    def get_session(self, call_sid: str) -> Optional[CallSessionData]:
        """Get session by call SID."""
        session = self._sessions.get(call_sid)
        if session:
            session.last_activity = datetime.now()
        return session
    
    def update_session(self, call_sid: str, **updates) -> Optional[CallSessionData]:
        """Update session with new data."""
        session = self._sessions.get(call_sid)
        if session:
            for key, value in updates.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            session.last_activity = datetime.now()
        return session
    
    def delete_session(self, call_sid: str) -> bool:
        """Delete a session."""
        if call_sid in self._sessions:
            del self._sessions[call_sid]
            return True
        return False
    
    def list_active_sessions(self) -> List[CallSessionData]:
        """List all active sessions."""
        return [
            session for session in self._sessions.values()
            if session.state in [SessionState.ACTIVE, SessionState.IDENTITY_PENDING, 
                               SessionState.IDENTITY_VERIFIED, SessionState.PROCESSING]
        ]
    
    def get_session_count(self) -> int:
        """Get total number of active sessions."""
        return len(self._sessions)
    
    def cleanup_expired_sessions(self, ttl_minutes: int = 30):
        """Remove expired sessions."""
        expired_sessions = [
            call_sid for call_sid, session in self._sessions.items()
            if session.is_expired(ttl_minutes)
        ]
        
        for call_sid in expired_sessions:
            del self._sessions[call_sid]
        
        return len(expired_sessions)
    
    def _start_cleanup_task(self):
        """Start background cleanup task."""
        if self._cleanup_started:
            return
            
        try:
            async def cleanup_loop():
                while True:
                    try:
                        await asyncio.sleep(300)  # Run every 5 minutes
                        cleaned = self.cleanup_expired_sessions()
                        if cleaned > 0:
                            print(f"Cleaned up {cleaned} expired sessions")
                    except Exception as e:
                        print(f"Error in session cleanup: {e}")
            
            self._cleanup_task = asyncio.create_task(cleanup_loop())
            self._cleanup_started = True
        except RuntimeError:
            # No event loop running, will start later
            pass
    
    async def shutdown(self):
        """Shutdown the session store."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass


# Global session store instance
session_store = SessionStore()
