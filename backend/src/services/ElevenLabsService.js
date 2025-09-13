import fetch from 'node-fetch';

export class ElevenLabsService {
  constructor() {
    this.apiKey = process.env.ELEVENLABS_API_KEY;
    this.baseUrl = 'https://api.elevenlabs.io/v1';
    this.voiceId = process.env.ELEVENLABS_VOICE_ID || '21m00Tcm4TlvDq8ikWAM'; // Rachel voice
    
    if (!this.apiKey) {
      throw new Error('ELEVENLABS_API_KEY environment variable is required');
    }
  }

  async synthesizeSpeech(text, options = {}) {
    try {
      const defaultOptions = {
        voice_id: this.voiceId,
        model_id: 'eleven_monolingual_v1',
        voice_settings: {
          stability: 0.5,
          similarity_boost: 0.75,
          style: 0.0,
          use_speaker_boost: true
        }
      };

      const synthesisOptions = { ...defaultOptions, ...options };
      
      const response = await fetch(`${this.baseUrl}/text-to-speech/${synthesisOptions.voice_id}`, {
        method: 'POST',
        headers: {
          'Accept': 'audio/mpeg',
          'Content-Type': 'application/json',
          'xi-api-key': this.apiKey
        },
        body: JSON.stringify({
          text: text,
          model_id: synthesisOptions.model_id,
          voice_settings: synthesisOptions.voice_settings
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`ElevenLabs API error: ${response.status} - ${errorText}`);
      }

      const audioBuffer = await response.buffer();
      
      return {
        audio: audioBuffer,
        contentType: 'audio/mpeg',
        size: audioBuffer.length
      };

    } catch (error) {
      console.error('ElevenLabs synthesis error:', error);
      throw new Error(`Failed to synthesize speech: ${error.message}`);
    }
  }

  async synthesizeWithStreaming(text, options = {}) {
    try {
      const defaultOptions = {
        voice_id: this.voiceId,
        model_id: 'eleven_monolingual_v1',
        voice_settings: {
          stability: 0.5,
          similarity_boost: 0.75,
          style: 0.0,
          use_speaker_boost: true
        },
        optimize_streaming_latency: 2
      };

      const synthesisOptions = { ...defaultOptions, ...options };
      
      const response = await fetch(`${this.baseUrl}/text-to-speech/${synthesisOptions.voice_id}/stream`, {
        method: 'POST',
        headers: {
          'Accept': 'audio/mpeg',
          'Content-Type': 'application/json',
          'xi-api-key': this.apiKey
        },
        body: JSON.stringify({
          text: text,
          model_id: synthesisOptions.model_id,
          voice_settings: synthesisOptions.voice_settings,
          optimize_streaming_latency: synthesisOptions.optimize_streaming_latency
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`ElevenLabs streaming API error: ${response.status} - ${errorText}`);
      }

      return response.body; // Return the readable stream

    } catch (error) {
      console.error('ElevenLabs streaming synthesis error:', error);
      throw new Error(`Failed to synthesize speech with streaming: ${error.message}`);
    }
  }

  async getVoices() {
    try {
      const response = await fetch(`${this.baseUrl}/voices`, {
        headers: {
          'xi-api-key': this.apiKey
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch voices: ${response.status}`);
      }

      const data = await response.json();
      return data.voices;

    } catch (error) {
      console.error('Error fetching ElevenLabs voices:', error);
      // Return default voice info if API fails
      return [{
        voice_id: this.voiceId,
        name: 'Rachel',
        category: 'premade',
        description: 'Professional female voice'
      }];
    }
  }

  async getVoiceSettings(voiceId = null) {
    try {
      const targetVoiceId = voiceId || this.voiceId;
      
      const response = await fetch(`${this.baseUrl}/voices/${targetVoiceId}/settings`, {
        headers: {
          'xi-api-key': this.apiKey
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch voice settings: ${response.status}`);
      }

      const settings = await response.json();
      return settings;

    } catch (error) {
      console.error('Error fetching voice settings:', error);
      // Return default settings
      return {
        stability: 0.5,
        similarity_boost: 0.75,
        style: 0.0,
        use_speaker_boost: true
      };
    }
  }

  // Utility method to validate text length
  validateText(text) {
    if (!text || typeof text !== 'string') {
      throw new Error('Text must be a non-empty string');
    }

    if (text.length > 5000) {
      throw new Error('Text length exceeds maximum limit of 5000 characters');
    }

    return text.trim();
  }

  // Method to split long text into chunks for better synthesis
  splitTextIntoChunks(text, maxChunkSize = 500) {
    const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0);
    const chunks = [];
    let currentChunk = '';

    for (const sentence of sentences) {
      const trimmedSentence = sentence.trim();
      if (currentChunk.length + trimmedSentence.length + 1 <= maxChunkSize) {
        currentChunk += (currentChunk ? '. ' : '') + trimmedSentence;
      } else {
        if (currentChunk) {
          chunks.push(currentChunk + '.');
        }
        currentChunk = trimmedSentence;
      }
    }

    if (currentChunk) {
      chunks.push(currentChunk + '.');
    }

    return chunks;
  }

  // Method to get user's subscription info (for rate limiting)
  async getUserInfo() {
    try {
      const response = await fetch(`${this.baseUrl}/user`, {
        headers: {
          'xi-api-key': this.apiKey
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch user info: ${response.status}`);
      }

      const userInfo = await response.json();
      return userInfo;

    } catch (error) {
      console.error('Error fetching user info:', error);
      return null;
    }
  }
}

