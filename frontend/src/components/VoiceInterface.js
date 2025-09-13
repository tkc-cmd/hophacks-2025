import React, { useState, useRef, useEffect } from 'react';
import { Mic, MicOff, Send, Loader2 } from 'lucide-react';

const VoiceInterface = ({ 
  microphoneState, 
  isConnected, 
  isProcessing,
  onSendMessage,
  wsRef,
  sessionId,
  sendWebSocketMessage
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [textInput, setTextInput] = useState('');
  const [permissionGranted, setPermissionGranted] = useState(false);
  const [permissionError, setPermissionError] = useState(null);
  
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);

  useEffect(() => {
    // Request microphone permission on component mount
    requestMicrophonePermission();
    
    return () => {
      stopRecording();
    };
  }, []);

  const requestMicrophonePermission = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000
        } 
      });
      
      setPermissionGranted(true);
      setPermissionError(null);
      
      // Stop the stream for now, we'll create a new one when recording
      stream.getTracks().forEach(track => track.stop());
      
    } catch (err) {
      console.error('Microphone permission error:', err);
      setPermissionGranted(false);
      setPermissionError('Microphone access is required for voice interaction');
    }
  };

  const startRecording = async () => {
    if (!permissionGranted || !isConnected || isRecording) {
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000
        } 
      });
      
      streamRef.current = stream;
      audioChunksRef.current = [];

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
          
          // Convert to base64 and send chunk
          const reader = new FileReader();
          reader.onload = () => {
            const base64Audio = reader.result.split(',')[1];
            sendWebSocketMessage({
              type: 'audio_chunk',
              sessionId,
              payload: base64Audio
            });
          };
          reader.readAsDataURL(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        sendWebSocketMessage({
          type: 'end_audio',
          sessionId
        });
        
        // Clean up stream
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
          streamRef.current = null;
        }
      };

      mediaRecorder.start(100); // Collect data every 100ms
      setIsRecording(true);
      
    } catch (err) {
      console.error('Recording start error:', err);
      setPermissionError('Failed to start recording');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
    
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
  };

  const handleMicrophoneClick = () => {
    if (microphoneState === 'speaking') {
      // Interrupt the agent
      sendWebSocketMessage({
        type: 'interrupt',
        sessionId
      });
      return;
    }

    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const handleTextSubmit = (e) => {
    e.preventDefault();
    if (textInput.trim() && isConnected) {
      onSendMessage(textInput.trim());
      setTextInput('');
    }
  };

  const getMicrophoneIcon = () => {
    switch (microphoneState) {
      case 'listening':
        return <MicOff className="w-8 h-8" />;
      case 'processing':
        return <Loader2 className="w-8 h-8 animate-spin" />;
      case 'speaking':
        return <div className="flex items-center space-x-1">
          <div className="sound-wave h-6"></div>
          <div className="sound-wave h-8"></div>
          <div className="sound-wave h-4"></div>
          <div className="sound-wave h-7"></div>
          <div className="sound-wave h-5"></div>
        </div>;
      default:
        return <Mic className="w-8 h-8" />;
    }
  };

  const getMicrophoneLabel = () => {
    switch (microphoneState) {
      case 'listening':
        return 'Stop Recording';
      case 'processing':
        return 'Processing...';
      case 'speaking':
        return 'Tap to Interrupt';
      default:
        return 'Start Recording';
    }
  };

  const isButtonDisabled = () => {
    return !isConnected || !permissionGranted || isProcessing;
  };

  return (
    <div className="glass-effect rounded-xl p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-6">Voice Interface</h2>
      
      {/* Microphone Button */}
      <div className="flex flex-col items-center space-y-4 mb-8">
        <button
          onClick={handleMicrophoneClick}
          disabled={isButtonDisabled()}
          className={`microphone-button ${microphoneState} ${
            isButtonDisabled() ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
          }`}
          title={getMicrophoneLabel()}
        >
          {getMicrophoneIcon()}
        </button>
        
        <div className="text-center">
          <p className="text-sm font-medium text-gray-700">
            {getMicrophoneLabel()}
          </p>
          {microphoneState === 'listening' && (
            <p className="text-xs text-gray-500 mt-1">
              Listening... Speak clearly
            </p>
          )}
        </div>
      </div>

      {/* Permission Error */}
      {permissionError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700">{permissionError}</p>
          <button
            onClick={requestMicrophonePermission}
            className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Text Input Alternative */}
      <div className="border-t border-gray-200 pt-6">
        <h3 className="text-sm font-medium text-gray-700 mb-3">
          Or type your message:
        </h3>
        
        <form onSubmit={handleTextSubmit} className="flex space-x-2">
          <input
            type="text"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder="Type your message here..."
            disabled={!isConnected}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-medical-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={!textInput.trim() || !isConnected}
            className="px-4 py-2 bg-medical-500 text-white rounded-lg hover:bg-medical-600 focus:outline-none focus:ring-2 focus:ring-medical-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>

      {/* Status Information */}
      <div className="mt-6 text-xs text-gray-500 space-y-1">
        <div className="flex justify-between">
          <span>Connection:</span>
          <span className={isConnected ? 'text-green-600' : 'text-red-600'}>
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <div className="flex justify-between">
          <span>Microphone:</span>
          <span className={permissionGranted ? 'text-green-600' : 'text-red-600'}>
            {permissionGranted ? 'Ready' : 'Not Available'}
          </span>
        </div>
        <div className="flex justify-between">
          <span>State:</span>
          <span className="capitalize">{microphoneState}</span>
        </div>
      </div>
    </div>
  );
};

export default VoiceInterface;

