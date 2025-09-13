"""ElevenLabs text-to-speech client."""

import os
import uuid
import asyncio
import aiofiles
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import hmac
import time
import logging

from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from server.config import settings, get_static_file_url

logger = logging.getLogger(__name__)


class TTSResult:
    """Result of a TTS generation."""
    def __init__(self, 
                 job_id: str,
                 text: str, 
                 file_path: str, 
                 file_url: str,
                 duration_ms: Optional[int] = None):
        self.job_id = job_id
        self.text = text
        self.file_path = file_path
        self.file_url = file_url
        self.duration_ms = duration_ms
        self.created_at = datetime.now()


class ElevenLabsTTSClient:
    """ElevenLabs TTS client with local file serving."""
    
    def __init__(self):
        self.client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        self.voice_settings = VoiceSettings(
            stability=settings.tts_stability,
            similarity_boost=settings.tts_similarity_boost,
            style=0.0,
            use_speaker_boost=True
        )
        
        # Ensure TTS directory exists
        self.tts_dir = Path("static/tts")
        self.tts_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for generated files
        self.file_cache: Dict[str, TTSResult] = {}
    
    async def synthesize_text(
        self, 
        text: str, 
        call_sid: Optional[str] = None,
        voice_id: Optional[str] = None
    ) -> Optional[TTSResult]:
        """Synthesize text to speech and save as local file."""
        
        if not text.strip():
            return None
        
        try:
            # Generate unique job ID
            job_id = str(uuid.uuid4())
            
            # Use configured voice or default
            voice_id = voice_id or settings.tts_voice_id
            
            # Create call-specific directory
            if call_sid:
                call_dir = self.tts_dir / call_sid
                call_dir.mkdir(exist_ok=True)
                file_path = call_dir / f"{job_id}.wav"
            else:
                file_path = self.tts_dir / f"{job_id}.wav"
            
            # Generate speech
            logger.info(f"Generating TTS for job {job_id}: {text[:50]}...")
            
            # Use the synchronous client in a thread pool
            audio_generator = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.generate(
                    text=text,
                    voice=voice_id,
                    voice_settings=self.voice_settings,
                    model="eleven_turbo_v2"
                )
            )
            
            # Save audio to file
            audio_data = b"".join(audio_generator)
            
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(audio_data)
            
            # Calculate duration (rough estimate based on text length and speech rate)
            estimated_duration_ms = self._estimate_duration(text)
            
            # Generate file URL
            if settings.require_signed_static_urls:
                file_url = self._generate_signed_url(str(file_path.relative_to("static")))
            else:
                file_url = get_static_file_url(file_path.name, call_sid)
            
            # Create result
            result = TTSResult(
                job_id=job_id,
                text=text,
                file_path=str(file_path),
                file_url=file_url,
                duration_ms=estimated_duration_ms
            )
            
            # Cache result
            self.file_cache[job_id] = result
            
            logger.info(f"TTS generation completed for job {job_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None
    
    async def synthesize_chunks(
        self, 
        text_chunks: List[str], 
        call_sid: Optional[str] = None
    ) -> List[TTSResult]:
        """Synthesize multiple text chunks in parallel."""
        
        tasks = []
        for chunk in text_chunks:
            if chunk.strip():
                task = self.synthesize_text(chunk, call_sid)
                tasks.append(task)
        
        if not tasks:
            return []
        
        # Run all synthesis tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and None results
        valid_results = []
        for result in results:
            if isinstance(result, TTSResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                logger.error(f"TTS chunk failed: {result}")
        
        return valid_results
    
    def _estimate_duration(self, text: str) -> int:
        """Estimate audio duration in milliseconds based on text."""
        # Rough estimation: ~150 words per minute, ~5 characters per word
        words = len(text.split())
        chars = len(text)
        
        # Use character count for more accuracy with short texts
        if chars < 50:
            # Very short texts: ~10 chars per second
            duration_seconds = max(1.0, chars / 10.0)
        else:
            # Longer texts: ~150 words per minute
            duration_seconds = max(1.0, (words / 150.0) * 60.0)
        
        return int(duration_seconds * 1000)
    
    def _generate_signed_url(self, relative_path: str) -> str:
        """Generate a signed URL for static files."""
        # Create expiration timestamp (5 minutes from now)
        expires = int(time.time()) + settings.token_ttl_seconds
        
        # Create signature
        message = f"{relative_path}:{expires}"
        signature = hmac.new(
            settings.static_signing_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Return signed URL
        return f"{settings.public_host}/static/{relative_path}?expires={expires}&signature={signature}"
    
    def verify_signed_url(self, relative_path: str, expires: str, signature: str) -> bool:
        """Verify a signed URL."""
        try:
            # Check expiration
            if int(expires) < time.time():
                return False
            
            # Verify signature
            message = f"{relative_path}:{expires}"
            expected_signature = hmac.new(
                settings.static_signing_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except (ValueError, TypeError):
            return False
    
    async def cleanup_old_files(self, max_age_hours: int = 1):
        """Clean up old TTS files."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        cleaned_count = 0
        
        # Clean up cache
        expired_jobs = []
        for job_id, result in self.file_cache.items():
            if result.created_at < cutoff_time:
                expired_jobs.append(job_id)
        
        for job_id in expired_jobs:
            result = self.file_cache.pop(job_id)
            try:
                if os.path.exists(result.file_path):
                    os.remove(result.file_path)
                    cleaned_count += 1
            except Exception as e:
                logger.error(f"Error removing TTS file {result.file_path}: {e}")
        
        # Clean up orphaned files in TTS directory
        if self.tts_dir.exists():
            for file_path in self.tts_dir.rglob("*.wav"):
                try:
                    file_stat = file_path.stat()
                    file_time = datetime.fromtimestamp(file_stat.st_mtime)
                    if file_time < cutoff_time:
                        file_path.unlink()
                        cleaned_count += 1
                except Exception as e:
                    logger.error(f"Error removing orphaned TTS file {file_path}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old TTS files")
        
        return cleaned_count
    
    async def get_result(self, job_id: str) -> Optional[TTSResult]:
        """Get TTS result by job ID."""
        return self.file_cache.get(job_id)
    
    async def concatenate_files(self, results: List[TTSResult], output_path: str) -> Optional[str]:
        """Concatenate multiple TTS files into one (if needed for long responses)."""
        if not results:
            return None
        
        if len(results) == 1:
            # Just return the single file
            return results[0].file_path
        
        try:
            # Simple concatenation by reading all files and joining
            combined_audio = b""
            
            for result in results:
                if os.path.exists(result.file_path):
                    async with aiofiles.open(result.file_path, 'rb') as f:
                        audio_data = await f.read()
                        combined_audio += audio_data
            
            # Write combined audio
            async with aiofiles.open(output_path, 'wb') as f:
                await f.write(combined_audio)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error concatenating TTS files: {e}")
            return None


# Global TTS client instance
tts_client = ElevenLabsTTSClient()
