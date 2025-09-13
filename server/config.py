"""Configuration management for the pharmacy voice agent."""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Twilio Configuration
    twilio_account_sid: str = Field(..., env="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(..., env="TWILIO_AUTH_TOKEN")
    twilio_voice_number: str = Field(..., env="TWILIO_VOICE_NUMBER")
    public_host: str = Field(..., env="PUBLIC_HOST")
    
    # AI Service API Keys
    deepgram_api_key: str = Field(..., env="DEEPGRAM_API_KEY")
    elevenlabs_api_key: str = Field(..., env="ELEVENLABS_API_KEY")
    google_api_key: str = Field(..., env="GOOGLE_API_KEY")
    
    # Security & Privacy
    static_signing_secret: str = Field(..., env="STATIC_SIGNING_SECRET")
    token_ttl_seconds: int = Field(300, env="TOKEN_TTL_SECONDS")
    require_signed_static_urls: bool = Field(True, env="REQUIRE_SIGNED_STATIC_URLS")
    debug_audio: bool = Field(False, env="DEBUG_AUDIO")
    
    # Database
    database_url: str = Field("sqlite:///./pharmacy_voice.db", env="DATABASE_URL")
    
    # Development
    log_level: str = Field("INFO", env="LOG_LEVEL")
    cors_origins: List[str] = Field(
        ["http://localhost:3000"], 
        env="CORS_ORIGINS"
    )
    
    # Audio Processing
    audio_sample_rate: int = 8000
    audio_chunk_size: int = 160  # 20ms at 8kHz
    speech_timeout_ms: int = 1500
    max_silence_ms: int = 2000
    
    # TTS Configuration
    tts_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs Rachel voice
    tts_stability: float = 0.5
    tts_similarity_boost: float = 0.8
    max_tts_chunk_chars: int = 200
    
    # LLM Configuration
    gemini_model: str = "gemini-pro"
    max_conversation_history: int = 10
    max_response_tokens: int = 150
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


# Utility functions
def get_static_file_url(filename: str, call_sid: Optional[str] = None) -> str:
    """Generate a URL for static TTS files."""
    base_path = f"/static/tts"
    if call_sid:
        base_path = f"{base_path}/{call_sid}"
    return f"{settings.public_host}{base_path}/{filename}"


def get_media_stream_url(call_sid: str, token: str) -> str:
    """Generate WebSocket URL for Twilio Media Streams."""
    return f"wss://{settings.public_host.replace('https://', '').replace('http://', '')}/twilio/media?callSid={call_sid}&token={token}"
