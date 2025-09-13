import React, { useEffect, useRef } from 'react';
import { Trash2, User, Bot, Clock } from 'lucide-react';

const TranscriptDisplay = ({ transcript, isProcessing, onClear }) => {
  const scrollRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript, isProcessing]);

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const getMessageIcon = (role) => {
    switch (role) {
      case 'user':
        return <User className="w-4 h-4" />;
      case 'assistant':
        return <Bot className="w-4 h-4" />;
      case 'system':
        return <Clock className="w-4 h-4" />;
      default:
        return <Bot className="w-4 h-4" />;
    }
  };

  const getMessageStyle = (role) => {
    switch (role) {
      case 'user':
        return 'transcript-message user';
      case 'assistant':
        return 'transcript-message assistant';
      case 'system':
        return 'transcript-message bg-gray-100 text-gray-600 text-sm italic mr-auto';
      default:
        return 'transcript-message assistant';
    }
  };

  return (
    <div className="glass-effect rounded-xl p-6 h-[600px] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-800">Conversation</h2>
        {transcript.length > 0 && (
          <button
            onClick={onClear}
            className="flex items-center space-x-1 px-3 py-1 text-sm text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            title="Clear conversation"
          >
            <Trash2 className="w-4 h-4" />
            <span>Clear</span>
          </button>
        )}
      </div>

      {/* Messages Container */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto custom-scrollbar space-y-4 pr-2"
      >
        {transcript.length === 0 && !isProcessing ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-500">
              <Bot className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p className="text-lg font-medium">Ready to help!</p>
              <p className="text-sm">Start by saying hello or asking about prescription refills.</p>
            </div>
          </div>
        ) : (
          <>
            {transcript.map((entry) => (
              <div key={entry.id} className="flex flex-col space-y-2">
                <div className={`flex ${entry.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={getMessageStyle(entry.role)}>
                    <div className="flex items-start space-x-2">
                      <div className={`flex-shrink-0 mt-0.5 ${
                        entry.role === 'user' ? 'text-white' : 'text-gray-500'
                      }`}>
                        {getMessageIcon(entry.role)}
                      </div>
                      <div className="flex-1">
                        <p className="leading-relaxed">{entry.message}</p>
                        <div className={`text-xs mt-2 opacity-75 ${
                          entry.role === 'user' ? 'text-white' : 'text-gray-500'
                        }`}>
                          {formatTime(entry.timestamp)}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}

            {/* Processing Indicator */}
            {isProcessing && (
              <div className="flex justify-start">
                <div className="transcript-message assistant">
                  <div className="flex items-center space-x-2">
                    <Bot className="w-4 h-4 text-gray-500" />
                    <div className="flex-1">
                      <div className="typing-indicator">
                        <div className="typing-dot"></div>
                        <div className="typing-dot"></div>
                        <div className="typing-dot"></div>
                      </div>
                      <p className="text-sm text-gray-500 mt-1">Assistant is thinking...</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer with conversation stats */}
      {transcript.length > 0 && (
        <div className="border-t border-gray-200 pt-3 mt-4">
          <div className="flex justify-between text-xs text-gray-500">
            <span>{transcript.length} messages</span>
            <span>
              {transcript.length > 0 && 
                `Started ${formatTime(transcript[0].timestamp)}`
              }
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default TranscriptDisplay;

