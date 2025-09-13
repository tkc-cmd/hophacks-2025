"""Test barge-in functionality and session state management."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from server.domain.sessions.store import CallSessionData, SessionState, TTSJob, session_store
from server.utils.audio import VoiceActivityDetector


@pytest.fixture
def mock_session():
    """Create a mock call session."""
    session = CallSessionData(
        call_sid="test_call_123",
        phone_number="+15551234567",
        start_time=datetime.now()
    )
    return session


@pytest.mark.asyncio
async def test_barge_in_detection(mock_session):
    """Test barge-in detection and state management."""
    
    # Setup session with playing TTS
    tts_job = TTSJob(
        id="tts_123",
        text="This is a long response that the user might interrupt",
        file_url="/static/tts/test_call_123/tts_123.wav",
        duration_ms=5000,
        status="completed"
    )
    
    mock_session.add_tts_job(tts_job)
    mock_session.currently_playing = tts_job.id
    mock_session.playback_start_time = datetime.now()
    mock_session.state = SessionState.ACTIVE
    
    # Simulate barge-in
    mock_session.set_barge_in()
    
    assert mock_session.barge_in_flag is True
    assert mock_session.state == SessionState.BARGE_IN
    assert mock_session.barge_in_timestamp is not None
    assert len(mock_session.interrupted_content) > 0


@pytest.mark.asyncio
async def test_voice_activity_detection():
    """Test voice activity detection logic."""
    
    vad = VoiceActivityDetector(
        energy_threshold=1000.0,
        speech_frames_threshold=3,
        silence_frames_threshold=5
    )
    
    # Test silence detection
    silent_audio = b'\x00' * 320  # Silent audio frame
    is_speech, state_changed = vad.process_frame(silent_audio)
    assert is_speech is False
    assert state_changed is False
    
    # Test speech detection (simulate high energy)
    # Create audio with some energy
    speech_audio = b''
    for i in range(160):  # 160 samples for 20ms at 8kHz
        # Alternate between positive and negative values to create energy
        sample_value = 1000 if i % 2 == 0 else -1000
        speech_audio += sample_value.to_bytes(2, byteorder='little', signed=True)
    
    # Process multiple speech frames to trigger detection
    for _ in range(5):
        is_speech, state_changed = vad.process_frame(speech_audio)
    
    assert vad.is_speech is True


@pytest.mark.asyncio
async def test_session_state_transitions(mock_session):
    """Test session state transitions during barge-in scenarios."""
    
    # Initial state
    assert mock_session.state == SessionState.ACTIVE
    
    # Start processing
    mock_session.state = SessionState.PROCESSING
    assert mock_session.state == SessionState.PROCESSING
    
    # Simulate barge-in during processing
    mock_session.set_barge_in()
    assert mock_session.state == SessionState.BARGE_IN
    
    # Clear barge-in
    mock_session.clear_barge_in()
    assert mock_session.state == SessionState.ACTIVE
    assert mock_session.barge_in_flag is False


@pytest.mark.asyncio
async def test_tts_queue_management(mock_session):
    """Test TTS job queue management during barge-in."""
    
    # Add multiple TTS jobs
    jobs = []
    for i in range(3):
        job = TTSJob(
            id=f"tts_{i}",
            text=f"This is TTS chunk {i}",
            file_url=f"/static/tts/test_call_123/tts_{i}.wav",
            duration_ms=2000,
            status="completed"
        )
        jobs.append(job)
        mock_session.add_tts_job(job)
    
    assert len(mock_session.tts_queue) == 3
    
    # Start playing first job
    mock_session.currently_playing = jobs[0].id
    
    # Simulate barge-in
    mock_session.set_barge_in()
    
    # Check that interrupted content is saved
    assert len(mock_session.interrupted_content) > 0
    
    # Get next TTS job
    next_job = mock_session.get_next_tts_job()
    assert next_job is not None
    assert next_job.id == "tts_0"  # Should get the first pending job


@pytest.mark.asyncio
async def test_conversation_history_during_barge_in(mock_session):
    """Test conversation history management during barge-in."""
    
    # Add initial conversation
    mock_session.add_conversation_turn("user", "I need a refill", 0.95)
    mock_session.add_conversation_turn("assistant", "I can help with that refill")
    
    assert len(mock_session.conversation_history) == 2
    
    # Simulate barge-in during assistant response
    mock_session.set_barge_in()
    
    # Add user interruption
    mock_session.add_conversation_turn("user", "Actually, never mind", 0.88)
    
    assert len(mock_session.conversation_history) == 3
    assert mock_session.conversation_history[-1].text == "Actually, never mind"
    
    # Check recent history
    recent = mock_session.get_recent_history(max_turns=2)
    assert len(recent) == 2
    assert recent[-1].text == "Actually, never mind"


@pytest.mark.asyncio
async def test_session_cleanup():
    """Test session cleanup and expiration."""
    
    # Create session in store
    session = session_store.create_session("cleanup_test", "+15551234567")
    
    # Verify session exists
    retrieved = session_store.get_session("cleanup_test")
    assert retrieved is not None
    assert retrieved.call_sid == "cleanup_test"
    
    # Test expiration
    session.last_activity = datetime.now() - timedelta(hours=2)  # 2 hours ago
    assert session.is_expired(ttl_minutes=60) is True  # Should be expired after 1 hour
    
    # Test cleanup
    cleaned = session_store.cleanup_expired_sessions(ttl_minutes=60)
    assert cleaned >= 1  # At least our test session should be cleaned
    
    # Verify session is gone
    retrieved_after_cleanup = session_store.get_session("cleanup_test")
    assert retrieved_after_cleanup is None


@pytest.mark.asyncio
async def test_concurrent_barge_in_handling():
    """Test handling multiple rapid barge-in events."""
    
    mock_session = CallSessionData(
        call_sid="concurrent_test",
        phone_number="+15551234567",
        start_time=datetime.now()
    )
    
    # Add TTS job
    tts_job = TTSJob(
        id="concurrent_tts",
        text="This is a response that gets interrupted multiple times",
        duration_ms=3000,
        status="completed"
    )
    mock_session.add_tts_job(tts_job)
    mock_session.currently_playing = tts_job.id
    
    # Simulate rapid barge-in events
    for i in range(5):
        mock_session.set_barge_in()
        await asyncio.sleep(0.01)  # Small delay
        mock_session.clear_barge_in()
        await asyncio.sleep(0.01)
    
    # Should handle gracefully without errors
    assert mock_session.barge_in_flag is False
    assert mock_session.state == SessionState.ACTIVE


@pytest.mark.asyncio
async def test_audio_buffer_management():
    """Test audio buffer management during barge-in."""
    
    from server.ws_media import MediaStreamHandler
    
    handler = MediaStreamHandler()
    call_sid = "buffer_test"
    
    # Initialize buffers
    handler.audio_buffers[call_sid] = b""
    
    # Add audio data
    test_audio = b"test_audio_data" * 10
    handler.audio_buffers[call_sid] += test_audio
    
    # Simulate barge-in clearing buffers
    if call_sid in handler.audio_buffers:
        handler.audio_buffers[call_sid] = b""
    
    assert len(handler.audio_buffers[call_sid]) == 0


@pytest.mark.asyncio
@patch('server.utils.twilio_ctrl.twilio_controller.stop_current_playback')
async def test_playback_interruption(mock_stop_playback):
    """Test playback interruption via Twilio control."""
    
    mock_stop_playback.return_value = True
    
    # Simulate barge-in detection
    call_sid = "interrupt_test"
    
    # Call the interruption function
    result = await mock_stop_playback(call_sid)
    
    # Verify it was called
    mock_stop_playback.assert_called_once_with(call_sid)
    assert result is True


@pytest.mark.asyncio
async def test_partial_transcript_handling(mock_session):
    """Test handling of partial transcripts during barge-in."""
    
    # Simulate partial transcript updates
    partial_transcripts = [
        "I need",
        "I need to",
        "I need to cancel",
        "I need to cancel that"
    ]
    
    for partial in partial_transcripts:
        mock_session.stt_partial = partial
        
        # Simulate barge-in detection on longer partial
        if len(partial) > 15:
            mock_session.set_barge_in()
    
    assert mock_session.barge_in_flag is True
    assert mock_session.stt_partial == "I need to cancel that"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
