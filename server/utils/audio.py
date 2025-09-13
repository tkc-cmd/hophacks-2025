"""Audio processing utilities."""

import base64
import struct
try:
    import audioop
except ImportError:
    import audioop_lts as audioop
import re
from typing import List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class AudioFrame:
    """Represents an audio frame."""
    data: bytes
    timestamp: datetime
    sequence_number: int
    format: str = "mulaw"  # mulaw, linear16


def mulaw_to_linear16(mulaw_data: bytes) -> bytes:
    """Convert 8-bit μ-law audio to 16-bit linear PCM."""
    try:
        return audioop.ulaw2lin(mulaw_data, 2)
    except Exception as e:
        # Fallback to manual conversion if audioop fails
        return _manual_mulaw_to_linear16(mulaw_data)


def _manual_mulaw_to_linear16(mulaw_data: bytes) -> bytes:
    """Manual μ-law to linear PCM conversion."""
    # μ-law decompression table (simplified)
    MULAW_BIAS = 0x84
    MULAW_MAX = 0x1FFF
    
    linear_data = []
    
    for byte in mulaw_data:
        # Complement the byte
        byte = ~byte & 0xFF
        
        # Extract sign, exponent, and mantissa
        sign = byte & 0x80
        exponent = (byte & 0x70) >> 4
        mantissa = byte & 0x0F
        
        # Calculate linear value
        if exponent == 0:
            linear = (mantissa << 4) + MULAW_BIAS
        else:
            linear = ((mantissa + 16) << (exponent + 3)) + MULAW_BIAS
        
        if sign:
            linear = -linear
        
        # Clamp to 16-bit range
        linear = max(-32768, min(32767, linear))
        
        # Pack as 16-bit little-endian
        linear_data.extend(struct.pack('<h', linear))
    
    return bytes(linear_data)


def linear16_to_mulaw(linear_data: bytes) -> bytes:
    """Convert 16-bit linear PCM to 8-bit μ-law."""
    try:
        return audioop.lin2ulaw(linear_data, 2)
    except Exception as e:
        raise ValueError(f"Failed to convert linear16 to mulaw: {e}")


def decode_twilio_audio(base64_payload: str) -> bytes:
    """Decode base64 μ-law audio from Twilio Media Streams."""
    try:
        return base64.b64decode(base64_payload)
    except Exception as e:
        raise ValueError(f"Failed to decode Twilio audio: {e}")


def resample_audio(audio_data: bytes, from_rate: int, to_rate: int, sample_width: int = 2) -> bytes:
    """Resample audio data."""
    try:
        return audioop.ratecv(audio_data, sample_width, 1, from_rate, to_rate, None)[0]
    except Exception as e:
        raise ValueError(f"Failed to resample audio: {e}")


class JitterBuffer:
    """Simple jitter buffer for audio frames."""
    
    def __init__(self, buffer_size: int = 10, target_delay_ms: int = 60):
        self.buffer_size = buffer_size
        self.target_delay_ms = target_delay_ms
        self.frames: List[AudioFrame] = []
        self.expected_sequence = 0
        self.last_output_time = datetime.now()
    
    def add_frame(self, frame: AudioFrame):
        """Add an audio frame to the buffer."""
        # Insert frame in sequence order
        inserted = False
        for i, existing_frame in enumerate(self.frames):
            if frame.sequence_number < existing_frame.sequence_number:
                self.frames.insert(i, frame)
                inserted = True
                break
        
        if not inserted:
            self.frames.append(frame)
        
        # Limit buffer size
        if len(self.frames) > self.buffer_size:
            self.frames.pop(0)
    
    def get_frame(self) -> Optional[AudioFrame]:
        """Get the next frame from the buffer."""
        if not self.frames:
            return None
        
        # Check if we should wait longer for out-of-order frames
        now = datetime.now()
        if len(self.frames) < 3:  # Wait for more frames if buffer is small
            time_since_last = (now - self.last_output_time).total_seconds() * 1000
            if time_since_last < self.target_delay_ms:
                return None
        
        # Return the oldest frame
        frame = self.frames.pop(0)
        self.last_output_time = now
        return frame
    
    def flush(self) -> List[AudioFrame]:
        """Flush all frames from the buffer."""
        frames = self.frames.copy()
        self.frames.clear()
        return frames


class VoiceActivityDetector:
    """Simple voice activity detection based on energy levels."""
    
    def __init__(self, 
                 energy_threshold: float = 1000.0,
                 speech_frames_threshold: int = 3,
                 silence_frames_threshold: int = 10):
        self.energy_threshold = energy_threshold
        self.speech_frames_threshold = speech_frames_threshold
        self.silence_frames_threshold = silence_frames_threshold
        
        self.speech_frames = 0
        self.silence_frames = 0
        self.is_speech = False
        self.speech_start_time: Optional[datetime] = None
    
    def process_frame(self, audio_data: bytes) -> Tuple[bool, bool]:
        """
        Process an audio frame and return (is_speech, speech_state_changed).
        
        Returns:
            Tuple of (is_speech, state_changed) where:
            - is_speech: True if current frame contains speech
            - state_changed: True if speech state changed from previous frame
        """
        # Calculate energy (RMS)
        energy = self._calculate_energy(audio_data)
        
        state_changed = False
        
        if energy > self.energy_threshold:
            # Potential speech frame
            self.speech_frames += 1
            self.silence_frames = 0
            
            if not self.is_speech and self.speech_frames >= self.speech_frames_threshold:
                # Transition to speech
                self.is_speech = True
                self.speech_start_time = datetime.now()
                state_changed = True
        else:
            # Silence frame
            self.silence_frames += 1
            self.speech_frames = 0
            
            if self.is_speech and self.silence_frames >= self.silence_frames_threshold:
                # Transition to silence
                self.is_speech = False
                self.speech_start_time = None
                state_changed = True
        
        return self.is_speech, state_changed
    
    def _calculate_energy(self, audio_data: bytes) -> float:
        """Calculate RMS energy of audio data."""
        if len(audio_data) == 0:
            return 0.0
        
        # Assume 16-bit samples
        samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
        
        # Calculate RMS
        sum_squares = sum(sample * sample for sample in samples)
        rms = (sum_squares / len(samples)) ** 0.5
        
        return rms
    
    def reset(self):
        """Reset the VAD state."""
        self.speech_frames = 0
        self.silence_frames = 0
        self.is_speech = False
        self.speech_start_time = None


class SentenceBoundaryDetector:
    """Detect sentence boundaries in partial transcripts."""
    
    def __init__(self):
        self.sentence_endings = r'[.!?]'
        self.abbreviations = {
            'dr', 'mr', 'mrs', 'ms', 'prof', 'inc', 'ltd', 'corp',
            'mg', 'ml', 'oz', 'lb', 'ft', 'in', 'vs', 'etc'
        }
    
    def find_sentences(self, text: str) -> List[str]:
        """Split text into sentences, handling common abbreviations."""
        if not text.strip():
            return []
        
        sentences = []
        current_sentence = ""
        
        # Split on potential sentence boundaries
        parts = re.split(f'({self.sentence_endings})', text)
        
        i = 0
        while i < len(parts):
            part = parts[i]
            
            if re.match(self.sentence_endings, part):
                # This is a sentence ending punctuation
                current_sentence += part
                
                # Check if this is likely an abbreviation
                words = current_sentence.strip().split()
                if (words and 
                    len(words[-1]) <= 4 and 
                    words[-1].lower().rstrip('.!?') in self.abbreviations):
                    # Likely an abbreviation, continue building sentence
                    if i + 1 < len(parts):
                        current_sentence += parts[i + 1]
                        i += 1
                else:
                    # End of sentence
                    sentence = current_sentence.strip()
                    if sentence:
                        sentences.append(sentence)
                    current_sentence = ""
            else:
                current_sentence += part
            
            i += 1
        
        # Add any remaining text as incomplete sentence
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        return sentences
    
    def is_complete_sentence(self, text: str) -> bool:
        """Check if text appears to be a complete sentence."""
        text = text.strip()
        if not text:
            return False
        
        # Must end with sentence punctuation
        if not re.search(f'{self.sentence_endings}$', text):
            return False
        
        # Must have reasonable length and structure
        words = text.split()
        if len(words) < 2:
            return False
        
        # Check for abbreviation at the end
        last_word = words[-1].lower().rstrip('.!?')
        if last_word in self.abbreviations:
            return False
        
        return True
