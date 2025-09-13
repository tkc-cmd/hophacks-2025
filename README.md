# Pharmacy Voice Agent MVP

Voice agent pharmacy tool for refilling prescriptions, pharmacological conflicts, and administration advice

Contributors: Theo Chapman, Rohan Butani, Rohan Badal, Soren Ghorai

A HIPAA-aware pharmacy voice agent that runs on Twilio phone calls and supports prescription refills, drug interaction checks, and administration guidance with real-time audio processing, barge-in capabilities, and latency-hiding response synthesis.

## Features

- **🔊 Real-time Voice Processing**: Twilio Media Streams with Deepgram STT and ElevenLabs TTS
- **🧠 AI-Powered Responses**: Google Gemini with specialized pharmacy tools
- **⚡ Barge-in Support**: Users can interrupt TTS playback by speaking
- **🔒 Privacy-First**: PHI protection with audit logging and data masking
- **💊 Pharmacy Services**:
  - Prescription refill requests
  - Drug interaction checking
  - Medication administration guidance
- **📱 Production-Ready**: FastAPI with WebSocket support and static file serving

## Quick Start

### Prerequisites

- Python 3.11+
- Twilio account with Voice capabilities
- ngrok (for local development)
- API keys for:
  - Deepgram (Speech-to-Text)
  - ElevenLabs (Text-to-Speech)
  - Google AI (Gemini LLM)

### Installation

1. **Clone and setup:**
   ```bash
   git clone <your-repo>
   cd pharmacy-voice-agent
   make install
   ```

2. **Configure environment:**
   ```bash
   cp env.example .env
   # Edit .env with your API keys and settings
   ```

3. **Initialize database:**
   ```bash
   make init-db
   make seed
   ```

4. **Start development server:**
   ```bash
   make dev
   ```

5. **Expose with ngrok (in another terminal):**
   ```bash
   make tunnel
   # Copy the https URL and update PUBLIC_HOST in .env
   ```

6. **Configure Twilio phone number:**
   - Voice webhook URL: `https://your-ngrok-url.ngrok.io/twilio/voice`
   - Status callback URL: `https://your-ngrok-url.ngrok.io/twilio/status`

### Environment Variables

```bash
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_VOICE_NUMBER=+1234567890
PUBLIC_HOST=https://your-ngrok-url.ngrok.io

# AI Service API Keys
DEEPGRAM_API_KEY=your_deepgram_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
GOOGLE_API_KEY=your_google_api_key

# Security & Privacy
STATIC_SIGNING_SECRET=your_random_secret_key_here
TOKEN_TTL_SECONDS=300
REQUIRE_SIGNED_STATIC_URLS=true
DEBUG_AUDIO=false
```

## Architecture

### Call Flow
1. **Incoming Call** → Twilio webhook creates session and starts Media Stream
2. **Audio Processing** → Real-time STT with Deepgram, voice activity detection
3. **AI Processing** → Gemini LLM with pharmacy-specific tools
4. **Response Generation** → ElevenLabs TTS with chunked playback
5. **Barge-in Handling** → Interrupt detection and graceful response switching

### Tech Stack
- **Backend**: FastAPI + Uvicorn ASGI server
- **Database**: SQLite with SQLAlchemy ORM
- **Voice**: Twilio Programmable Voice + Media Streams
- **STT**: Deepgram streaming API
- **LLM**: Google Gemini with function calling
- **TTS**: ElevenLabs voice synthesis
- **Audio**: Real-time μ-law/PCM processing

## Usage Examples

### Test Call Flow

1. **Call the Twilio number**
2. **Hear welcome**: "I'm an automated pharmacy assistant..."
3. **Try these interactions**:

#### Prescription Refill
```
User: "I need to refill my blood pressure medication"
Assistant: "I can help with that refill. To access your prescription information, 
          I'll need to verify your identity. Could you provide your full name 
          and date of birth?"
User: "Jane Smith, January 2nd, 1975"
Assistant: "Thank you. What medication would you like to refill?"
User: "Lisinopril 10 milligrams"
Assistant: [Uses refill tool] "I found your prescription. How many would you like?"
```

#### Drug Interactions
```
User: "Can I take ibuprofen with my other medications?"
Assistant: "I can check for interactions. What other medications are you taking?"
User: "I take lisinopril for blood pressure"
Assistant: [Uses interaction tool] "⚠️ CAUTION: NSAID-ACE inhibitor interaction.
          NSAIDs may reduce effectiveness of blood pressure medications..."
```

#### Administration Guidance
```
User: "How should I take my atorvastatin?"
Assistant: [Uses admin guide tool] "For atorvastatin: Take once daily, 
          preferably in the evening. Can be taken with or without food.
          Avoid grapefruit and grapefruit juice..."
```

### Test Data

The system comes with seeded test patients:

- **Jane Smith** (DOB: 1975-01-02)
  - Atorvastatin 20mg (2 refills remaining)
  - Lisinopril 10mg (1 refill remaining)

- **John Doe** (DOB: 1980-06-15)
  - Metformin 500mg (3 refills remaining)
  - Sertraline 50mg (0 refills remaining)

## Development

### Project Structure
```
server/
├── app.py                 # FastAPI application
├── ws_media.py           # Media Streams WebSocket handler
├── config.py             # Configuration management
├── domain/               # Business logic
│   ├── drug_info/        # Drug information service
│   ├── refill/           # Prescription refill service
│   └── sessions/         # Session state management
├── stt/                  # Speech-to-text
├── llm/                  # Language model integration
├── tts/                  # Text-to-speech
├── persistence/          # Database models and operations
├── middleware/           # PHI protection and logging
└── utils/               # Audio processing and Twilio control

tests/                   # Test suite
docs/                    # Documentation
static/tts/             # Generated TTS files
```

### Available Commands
```bash
make install      # Install dependencies
make dev          # Start development server
make test         # Run tests
make lint         # Lint code
make fmt          # Format code
make init-db      # Initialize database
make seed         # Seed test data
make clean        # Clean up temporary files
make tunnel       # Start ngrok tunnel
```

### Testing

```bash
# Run all tests
make test

# Test specific functionality
python -m pytest tests/test_refill_flow.py -v
python -m pytest tests/test_barge_in.py -v
```

## Security & Privacy

### PHI Protection
- **Data Masking**: Phone numbers show only last 4 digits in logs
- **DOB Masking**: Only month/day stored in audit logs
- **Audio Storage**: Raw audio not stored unless `DEBUG_AUDIO=true`
- **Signed URLs**: TTS files served with time-limited signatures

### Audit Logging
All PHI-touching operations are logged:
- Identity verification attempts
- Prescription lookups
- Refill requests
- Interaction checks
- System errors

### Request Validation
- Twilio webhook signature verification
- Session token validation for Media Streams
- CORS restrictions

## Production Deployment

### Scaling Considerations
- **Session Store**: Move to Redis for multi-instance deployments
- **File Storage**: Use S3/CloudFront for TTS files
- **Database**: Migrate to PostgreSQL
- **Load Balancing**: Sticky sessions required for WebSockets

### Monitoring
- Active session count via `/health` endpoint
- Error rates and response latencies
- PHI access audit logs
- TTS/STT success rates

### Environment Setup
```bash
# Production environment variables
DATABASE_URL=postgresql://user:pass@host:5432/pharmacy_voice
REDIS_URL=redis://localhost:6379
DEBUG_AUDIO=false
LOG_LEVEL=INFO
```

## API Documentation

See [docs/API.md](docs/API.md) for detailed API documentation including:
- Webhook endpoints
- WebSocket message formats
- Database schemas
- Error responses

## Architecture Details

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for:
- System architecture diagrams
- Media flow sequences
- Component interactions
- Scaling strategies

## Limitations & Disclaimers

⚠️ **This is a demonstration MVP and should not be used for actual medical purposes without proper HIPAA compliance review, security audits, and clinical validation.**

### Current Limitations
- Mock drug interaction database (not comprehensive)
- Simplified patient verification
- Basic audio quality optimization
- Single-instance session storage
- Limited error recovery scenarios

### Not Included
- HIPAA compliance certification
- Clinical decision support validation
- Comprehensive drug interaction database
- Multi-language support
- Advanced fraud detection

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run `make lint` and `make test`
5. Submit a pull request

## License

MIT License - See LICENSE file for details.

## Support

For issues and questions:
1. Check the [docs/](docs/) directory
2. Review test cases in [tests/](tests/)
3. Open an issue with:
   - Call logs (with PHI redacted)
   - Error messages
   - Steps to reproduce
