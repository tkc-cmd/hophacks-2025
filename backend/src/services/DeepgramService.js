import fetch from 'node-fetch';

export class DeepgramService {
  constructor() {
    this.apiKey = process.env.DEEPGRAM_API_KEY;
    this.baseUrl = 'https://api.deepgram.com/v1';
    
    if (!this.apiKey) {
      throw new Error('DEEPGRAM_API_KEY environment variable is required');
    }
  }

  async transcribeAudio(audioBuffer, options = {}) {
    try {
      const defaultOptions = {
        model: 'nova-2',
        language: 'en-US',
        punctuate: true,
        diarize: false,
        smart_format: true,
        interim_results: false
      };

      const transcriptionOptions = { ...defaultOptions, ...options };
      
      // Build query parameters
      const params = new URLSearchParams();
      Object.entries(transcriptionOptions).forEach(([key, value]) => {
        params.append(key, value.toString());
      });

      const response = await fetch(`${this.baseUrl}/listen?${params}`, {
        method: 'POST',
        headers: {
          'Authorization': `Token ${this.apiKey}`,
          'Content-Type': 'audio/wav'
        },
        body: audioBuffer
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Deepgram API error: ${response.status} - ${errorText}`);
      }

      const result = await response.json();
      
      // Extract transcript from Deepgram response
      const transcript = result.results?.channels?.[0]?.alternatives?.[0]?.transcript || '';
      const confidence = result.results?.channels?.[0]?.alternatives?.[0]?.confidence || 0;

      return {
        transcript: transcript.trim(),
        confidence,
        duration: result.metadata?.duration || 0,
        raw: result
      };

    } catch (error) {
      console.error('Deepgram transcription error:', error);
      throw new Error(`Failed to transcribe audio: ${error.message}`);
    }
  }

  async createLiveTranscription(websocket, options = {}) {
    try {
      const defaultOptions = {
        model: 'nova-2',
        language: 'en-US',
        punctuate: true,
        interim_results: true,
        smart_format: true,
        endpointing: 300,
        vad_events: true
      };

      const transcriptionOptions = { ...defaultOptions, ...options };
      
      // Build query parameters for live transcription
      const params = new URLSearchParams();
      Object.entries(transcriptionOptions).forEach(([key, value]) => {
        params.append(key, value.toString());
      });

      const deepgramUrl = `wss://api.deepgram.com/v1/listen?${params}`;
      
      // In a real implementation, you would create a WebSocket connection to Deepgram
      // and pipe audio data through it. For this demo, we'll simulate the connection.
      
      return {
        url: deepgramUrl,
        headers: {
          'Authorization': `Token ${this.apiKey}`
        },
        options: transcriptionOptions
      };

    } catch (error) {
      console.error('Deepgram live transcription setup error:', error);
      throw new Error(`Failed to setup live transcription: ${error.message}`);
    }
  }

  // Utility method to check if audio buffer is valid
  isValidAudioBuffer(buffer) {
    if (!buffer || !Buffer.isBuffer(buffer)) {
      return false;
    }

    // Check minimum size (at least 1KB)
    if (buffer.length < 1024) {
      return false;
    }

    return true;
  }

  // Convert various audio formats to WAV (simplified)
  async convertToWav(audioBuffer, inputFormat = 'webm') {
    // In a production app, you'd use ffmpeg or similar to convert audio formats
    // For this demo, we'll assume the audio is already in a compatible format
    
    if (!this.isValidAudioBuffer(audioBuffer)) {
      throw new Error('Invalid audio buffer provided');
    }

    // For now, return the buffer as-is
    // In production, implement proper audio format conversion
    return audioBuffer;
  }

  // Get supported models and languages
  async getModels() {
    try {
      const response = await fetch(`${this.baseUrl}/projects`, {
        headers: {
          'Authorization': `Token ${this.apiKey}`
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch models: ${response.status}`);
      }

      const data = await response.json();
      return data;

    } catch (error) {
      console.error('Error fetching Deepgram models:', error);
      return {
        models: ['nova-2', 'nova', 'enhanced', 'base'],
        languages: ['en-US', 'en-GB', 'es', 'fr', 'de']
      };
    }
  }
}

