import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Volume2, VolumeX, Wifi, WifiOff } from 'lucide-react';
import VoiceInterface from './components/VoiceInterface';
import TranscriptDisplay from './components/TranscriptDisplay';
import StatusIndicator from './components/StatusIndicator';
import ErrorBoundary from './components/ErrorBoundary';

function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [transcript, setTranscript] = useState([]);
  const [microphoneState, setMicrophoneState] = useState('idle');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [sessionId, setSessionId] = useState(null);

  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  // Initialize WebSocket connection
  useEffect(() => {
    connectWebSocket();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    try {
      const wsUrl = process.env.NODE_ENV === 'production' 
        ? 'wss://your-domain.com/api/voice/stream'
        : 'ws://localhost:3001';
      
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setConnectionStatus('connected');
        setError(null);
        startSession();
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleWebSocketMessage(data);
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        setConnectionStatus('disconnected');
        setMicrophoneState('idle');
        
        // Attempt to reconnect after 3 seconds
        setTimeout(() => {
          if (connectionStatus !== 'connected') {
            connectWebSocket();
          }
        }, 3000);
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Connection error. Retrying...');
        setConnectionStatus('error');
      };

    } catch (err) {
      console.error('Failed to connect WebSocket:', err);
      setError('Failed to connect to voice service');
    }
  };

  const startSession = () => {
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    
    sendWebSocketMessage({
      type: 'start_session',
      sessionId: newSessionId
    });
  };

  const handleWebSocketMessage = (data) => {
    switch (data.type) {
      case 'session_started':
        console.log('Session started:', data.sessionId);
        addToTranscript('assistant', data.message);
        break;
        
      case 'transcript':
        addToTranscript(data.role, data.message);
        break;
        
      case 'audio_response':
        if (voiceEnabled) {
          playAudioResponse(data.audio, data.contentType);
        }
        break;
        
      case 'recording_status':
        setMicrophoneState(data.isRecording ? 'listening' : 'idle');
        break;
        
      case 'speaking_status':
        setMicrophoneState(data.isSpeaking ? 'speaking' : 'idle');
        break;
        
      case 'processing':
        setIsProcessing(true);
        setMicrophoneState('processing');
        addToTranscript('system', data.message);
        break;
        
      case 'interrupted':
        setMicrophoneState('idle');
        break;
        
      case 'error':
        setError(data.message);
        setMicrophoneState('idle');
        setIsProcessing(false);
        break;
        
      case 'session_ended':
        setSessionId(null);
        setMicrophoneState('idle');
        break;
        
      default:
        console.log('Unknown message type:', data.type);
    }
  };

  const sendWebSocketMessage = (message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected');
      setError('Not connected to voice service');
    }
  };

  const addToTranscript = (role, message) => {
    const entry = {
      id: Date.now(),
      role,
      message,
      timestamp: new Date()
    };
    
    setTranscript(prev => [...prev, entry]);
    setIsProcessing(false);
  };

  const playAudioResponse = async (audioBase64, contentType) => {
    try {
      const audioData = atob(audioBase64);
      const audioBuffer = new ArrayBuffer(audioData.length);
      const view = new Uint8Array(audioBuffer);
      
      for (let i = 0; i < audioData.length; i++) {
        view[i] = audioData.charCodeAt(i);
      }

      const blob = new Blob([audioBuffer], { type: contentType });
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      
      audio.onplay = () => setMicrophoneState('speaking');
      audio.onended = () => {
        setMicrophoneState('idle');
        URL.revokeObjectURL(audioUrl);
      };
      
      await audio.play();
      
    } catch (err) {
      console.error('Audio playback error:', err);
      setMicrophoneState('idle');
    }
  };

  const generateSessionId = () => {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  };

  const clearTranscript = () => {
    setTranscript([]);
  };

  const toggleVoice = () => {
    setVoiceEnabled(!voiceEnabled);
  };

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gradient-to-br from-medical-50 to-primary-50">
        {/* Header */}
        <header className="glass-effect border-b border-white/20">
          <div className="max-w-4xl mx-auto px-4 py-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-medical-500 rounded-lg flex items-center justify-center">
                  <Mic className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-gray-800">RxVoice Assistant</h1>
                  <p className="text-sm text-gray-600">Your AI-powered pharmacy helper</p>
                </div>
              </div>
              
              <div className="flex items-center space-x-4">
                <button
                  onClick={toggleVoice}
                  className="p-2 rounded-lg bg-white/50 hover:bg-white/70 transition-colors"
                  title={voiceEnabled ? 'Disable voice' : 'Enable voice'}
                >
                  {voiceEnabled ? (
                    <Volume2 className="w-5 h-5 text-gray-700" />
                  ) : (
                    <VolumeX className="w-5 h-5 text-gray-700" />
                  )}
                </button>
                
                <StatusIndicator 
                  isConnected={isConnected}
                  connectionStatus={connectionStatus}
                />
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="max-w-4xl mx-auto px-4 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            {/* Voice Interface */}
            <div className="lg:col-span-1">
              <VoiceInterface
                microphoneState={microphoneState}
                isConnected={isConnected}
                isProcessing={isProcessing}
                onStartRecording={() => {/* handled in VoiceInterface */}}
                onStopRecording={() => {/* handled in VoiceInterface */}}
                onSendMessage={(message) => {
                  sendWebSocketMessage({
                    type: 'text_input',
                    sessionId,
                    payload: message
                  });
                }}
                wsRef={wsRef}
                sessionId={sessionId}
                sendWebSocketMessage={sendWebSocketMessage}
              />
            </div>

            {/* Transcript Display */}
            <div className="lg:col-span-2">
              <TranscriptDisplay
                transcript={transcript}
                isProcessing={isProcessing}
                onClear={clearTranscript}
              />
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-center space-x-2">
                <WifiOff className="w-5 h-5 text-red-500" />
                <p className="text-red-700">{error}</p>
              </div>
            </div>
          )}

          {/* Disclaimer */}
          <div className="mt-8 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-sm text-yellow-800">
              <strong>Demo Notice:</strong> This is a demonstration application using mock data. 
              Do not use for actual medical decisions. Always consult with your healthcare provider 
              and pharmacist for real prescription needs.
            </p>
          </div>
        </main>
      </div>
    </ErrorBoundary>
  );
}

export default App;

