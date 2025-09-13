"""Twilio call control utilities."""

import logging
from typing import Optional
from twilio.rest import Client
from twilio.twiml import TwiML
from server.config import settings

logger = logging.getLogger(__name__)


class TwilioCallController:
    """Helper class for controlling active Twilio calls."""
    
    def __init__(self):
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    
    def create_play_gather_twiml(
        self, 
        audio_url: str, 
        gather_action: str = "/twilio/gather",
        timeout: int = 5,
        speech_timeout: str = "auto",
        hints: Optional[str] = None
    ) -> str:
        """Create TwiML for playing audio with speech gathering."""
        
        response = TwiML()
        
        # Create Gather element with speech input
        gather_attrs = {
            'input': 'speech',
            'action': gather_action,
            'method': 'POST',
            'timeout': timeout,
            'speechTimeout': speech_timeout,
            'bargeIn': True,
            'language': 'en-US'
        }
        
        if hints:
            gather_attrs['hints'] = hints
        
        gather = response.gather(**gather_attrs)
        gather.play(audio_url)
        
        # Fallback if no input
        response.say("I didn't hear anything. How can I help you?", voice="Polly.Joanna-Neural")
        response.redirect("/twilio/gather")
        
        return str(response)
    
    def create_say_gather_twiml(
        self, 
        text: str, 
        gather_action: str = "/twilio/gather",
        timeout: int = 5,
        voice: str = "Polly.Joanna-Neural"
    ) -> str:
        """Create TwiML for saying text with speech gathering (fallback)."""
        
        response = TwiML()
        
        gather = response.gather(
            input='speech',
            action=gather_action,
            method='POST',
            timeout=timeout,
            speechTimeout='auto',
            bargeIn=True,
            language='en-US',
            hints='pharmacy, prescription, refill, medication'
        )
        
        gather.say(text, voice=voice)
        
        # Fallback
        response.say("I didn't hear anything. How can I help you?", voice=voice)
        response.redirect("/twilio/gather")
        
        return str(response)
    
    def create_empty_response(self) -> str:
        """Create empty TwiML response to stop current playback."""
        response = TwiML()
        return str(response)
    
    def create_hangup_twiml(self, message: Optional[str] = None) -> str:
        """Create TwiML to end the call."""
        response = TwiML()
        
        if message:
            response.say(message, voice="Polly.Joanna-Neural")
        
        response.hangup()
        return str(response)
    
    async def update_call_twiml(self, call_sid: str, twiml: str) -> bool:
        """Update an active call with new TwiML."""
        try:
            call = self.client.calls(call_sid).update(twiml=twiml)
            logger.info(f"Updated call {call_sid} with new TwiML")
            return True
        except Exception as e:
            logger.error(f"Error updating call {call_sid}: {e}")
            return False
    
    async def stop_current_playback(self, call_sid: str) -> bool:
        """Stop current audio playback by sending empty TwiML."""
        empty_twiml = self.create_empty_response()
        return await self.update_call_twiml(call_sid, empty_twiml)
    
    async def play_audio_with_barge_in(
        self, 
        call_sid: str, 
        audio_url: str,
        hints: Optional[str] = None
    ) -> bool:
        """Play audio file with barge-in capability."""
        twiml = self.create_play_gather_twiml(
            audio_url=audio_url,
            hints=hints or "pharmacy, prescription, refill, medication, doctor"
        )
        return await self.update_call_twiml(call_sid, twiml)
    
    async def say_with_barge_in(
        self, 
        call_sid: str, 
        text: str,
        voice: str = "Polly.Joanna-Neural"
    ) -> bool:
        """Speak text with barge-in capability (fallback when TTS fails)."""
        twiml = self.create_say_gather_twiml(text, voice=voice)
        return await self.update_call_twiml(call_sid, twiml)
    
    async def end_call(self, call_sid: str, farewell_message: Optional[str] = None) -> bool:
        """End the call with optional farewell message."""
        message = farewell_message or "Thank you for calling. Have a great day!"
        twiml = self.create_hangup_twiml(message)
        return await self.update_call_twiml(call_sid, twiml)
    
    def create_media_stream_twiml(
        self, 
        websocket_url: str, 
        initial_message: Optional[str] = None
    ) -> str:
        """Create TwiML to start a media stream and optionally play initial message."""
        response = TwiML()
        
        # Start media stream
        start = response.start()
        start.stream(url=websocket_url)
        
        # Optional initial message
        if initial_message:
            response.say(initial_message, voice="Polly.Joanna-Neural")
        
        # Start with a gather to enable speech input
        gather = response.gather(
            input='speech',
            action='/twilio/gather',
            method='POST',
            timeout=30,
            speechTimeout='auto',
            bargeIn=True,
            language='en-US',
            hints='pharmacy, prescription, refill, medication, help'
        )
        
        gather.pause(length=1)  # Brief pause to let media stream start
        
        return str(response)
    
    async def get_call_status(self, call_sid: str) -> Optional[dict]:
        """Get current call status."""
        try:
            call = self.client.calls(call_sid).fetch()
            return {
                'sid': call.sid,
                'status': call.status,
                'duration': call.duration,
                'start_time': call.start_time,
                'end_time': call.end_time
            }
        except Exception as e:
            logger.error(f"Error fetching call status for {call_sid}: {e}")
            return None


# Global Twilio controller instance
twilio_controller = TwilioCallController()
