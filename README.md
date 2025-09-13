# RxVoice Assistant - Pharmacist Voice Agent Web Application

A full-stack voice-enabled pharmacy assistant that allows patients to refill prescriptions through natural conversation. Built for hackathon demo using mock data.

## 🎯 Overview

RxVoice Assistant is an AI-powered pharmacy helper that enables patients to:
- Refill prescriptions through voice interaction
- Verify patient identity securely
- Check for drug interactions automatically
- Get confirmation numbers and pickup times
- Handle natural conversation flow with interruption support

## 🏗️ Architecture

### Frontend
- **React 18** with modern hooks and functional components
- **Tailwind CSS** for responsive, medical-themed UI
- **WebSocket** integration for real-time audio streaming
- **Web Audio API** for microphone recording and audio playback
- **Lucide React** icons for clean, professional interface

### Backend
- **Node.js** with Express server
- **WebSocket** server for bidirectional audio streaming
- **SQLite** database with mock prescription data
- **RESTful APIs** for prescription management

### AI Services Integration
- **Deepgram** - Speech-to-Text (STT)
- **Google Gemini Pro** - Large Language Model for conversation
- **ElevenLabs** - Text-to-Speech (TTS)

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and npm
- API keys for Deepgram, Google Gemini Pro, and ElevenLabs

### Installation

1. **Clone and setup**
   ```bash
   cd pharmabot3
   ```

2. **Backend Setup**
   ```bash
   cd backend
   npm install
   
   # Copy environment template
   cp env.example .env
   
   # Edit .env with your API keys
   nano .env
   ```

3. **Frontend Setup**
   ```bash
   cd ../frontend
   npm install
   ```

4. **Start the Application**
   
   Terminal 1 (Backend):
   ```bash
   cd backend
   npm run dev
   ```
   
   Terminal 2 (Frontend):
   ```bash
   cd frontend
   npm start
   ```

5. **Access the Application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:3001

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```env
# API Keys
DEEPGRAM_API_KEY=your_deepgram_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here

# Server Configuration
PORT=3001
NODE_ENV=development

# Database
DATABASE_PATH=../database/pharmacy.db

# Voice Configuration
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
SESSION_TIMEOUT=300000
```

### API Keys Setup

1. **Deepgram**: Sign up at [deepgram.com](https://deepgram.com) for speech-to-text
2. **Google Gemini Pro**: Get API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
3. **ElevenLabs**: Register at [elevenlabs.io](https://elevenlabs.io) for text-to-speech

## 💾 Database Schema

### Patients Table
```sql
CREATE TABLE patients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  date_of_birth TEXT NOT NULL,
  phone TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Prescriptions Table
```sql
CREATE TABLE prescriptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id INTEGER NOT NULL,
  medication_name TEXT NOT NULL,
  dosage TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  refills_remaining INTEGER NOT NULL,
  prescriber TEXT NOT NULL,
  last_filled DATE,
  prescribed_date DATE NOT NULL,
  expires_date DATE NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (patient_id) REFERENCES patients (id)
);
```

## 🎭 Mock Data

The application includes 10 mock patients with 20+ prescriptions for testing:

**Sample Patient:**
- Name: John Smith
- DOB: 1965-05-15
- Prescriptions: Metformin 500mg, Lisinopril 10mg, Atorvastatin 20mg

**Test Scenarios:**
- Patients with multiple prescriptions
- Prescriptions with varying refill counts (0-5)
- Expired prescriptions
- Medications with potential interactions

## 🗣️ Conversation Flow

1. **Greeting**: "Hello! I'm RxVoice Assistant..."
2. **Intent Recognition**: Understand refill request
3. **Identity Verification**: Request full name
4. **Date of Birth**: Verify with DOB
5. **Prescription Review**: List available prescriptions
6. **Selection**: Choose medication to refill
7. **Safety Check**: Check drug interactions
8. **Confirmation**: Process refill and provide details

## 🎤 Voice Features

### Audio Processing
- Real-time speech-to-text transcription
- Natural language understanding
- Text-to-speech with professional voice
- Voice activity detection
- Background noise suppression

### Interruption Handling
- Users can interrupt the agent naturally
- Immediate audio stop and queue clearing
- Seamless transition back to listening mode
- Visual feedback for all voice states

### Microphone States
- **Idle**: Subtle pulse animation
- **Listening**: Animated sound waves
- **Processing**: Spinning loader
- **Speaking**: Wave pattern animation

## 🔒 Security & Compliance

### HIPAA Considerations
- Basic patient data protection
- Secure API communication
- Input sanitization
- Session timeout (5 minutes)
- No persistent audio storage

### Error Handling
- Graceful API failure recovery
- WebSocket reconnection logic
- Clear user error messages
- Fallback responses for service outages

## 🧪 Testing Scenarios

Test these scenarios with the application:

1. **Happy Path**: John Smith, DOB 05/15/1965, refill Metformin
2. **Patient Not Found**: Try invalid name/DOB combination
3. **No Refills**: Select prescription with 0 refills remaining
4. **Drug Interactions**: Test Warfarin with other medications
5. **Interruption**: Interrupt agent while speaking
6. **Network Issues**: Disconnect and reconnect WebSocket
7. **Expired Prescription**: Try to refill expired medication

## 📱 UI/UX Features

### Design System
- Medical/healthcare color palette (blues and whites)
- Professional but approachable aesthetic
- Smooth transitions and micro-animations
- WCAG AA accessibility compliance
- Responsive design for mobile devices

### Visual Feedback
- Real-time connection status
- Microphone permission indicators
- Audio processing states
- Conversation transcript with timestamps
- Error messages and recovery options

## 🚀 Performance

### Optimizations
- Audio latency under 500ms
- Efficient WebSocket message handling
- Optimized database queries
- Proper audio buffering
- Component-level error boundaries

### Monitoring
- Connection status indicators
- Session timeout handling
- Error logging and recovery
- Performance metrics tracking

## 🔧 Development

### Project Structure
```
pharmabot3/
├── backend/
│   ├── src/
│   │   ├── database/
│   │   ├── routes/
│   │   └── services/
│   ├── server.js
│   └── package.json
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── App.js
│   │   └── index.js
│   └── package.json
├── database/
└── README.md
```

### Available Scripts

**Backend:**
- `npm start` - Production server
- `npm run dev` - Development with nodemon
- `npm test` - Run tests

**Frontend:**
- `npm start` - Development server
- `npm run build` - Production build
- `npm test` - Run tests

## 🐛 Troubleshooting

### Common Issues

1. **Microphone not working**
   - Check browser permissions
   - Ensure HTTPS in production
   - Try different browser

2. **WebSocket connection fails**
   - Verify backend is running on port 3001
   - Check firewall settings
   - Confirm proxy configuration

3. **API errors**
   - Verify all API keys in .env
   - Check API key permissions
   - Monitor rate limits

4. **Audio playback issues**
   - Check browser audio permissions
   - Verify ElevenLabs API key
   - Test with different audio format

## 📄 License

This project is for demonstration purposes only. Not for production medical use.

## ⚠️ Disclaimer

**DEMO APPLICATION**: This is a demonstration using mock data. Do not use for actual medical decisions. Always consult with healthcare providers and pharmacists for real prescription needs.

## 🤝 Contributing

This is a hackathon demo project. For improvements or issues, please create GitHub issues or submit pull requests.

---

Built with ❤️ for healthcare innovation

