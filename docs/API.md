# API Documentation

## Twilio Webhook Endpoints

### POST /twilio/voice
Handles incoming voice calls from Twilio.

**Request Body (form-encoded):**
```
CallSid: string          # Unique call identifier
From: string             # Caller's phone number
To: string               # Called phone number (your Twilio number)
CallStatus: string       # Call status (ringing, in-progress, etc.)
```

**Response:**
- Content-Type: `application/xml`
- Body: TwiML response with Media Stream setup

**Example Response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Start>
        <Stream url="wss://your-host.com/twilio/media?callSid=CA123&token=abc123"/>
    </Start>
    <Gather input="speech" action="/twilio/gather" bargeIn="true" language="en-US">
        <Say voice="Polly.Joanna-Neural">Welcome message...</Say>
    </Gather>
</Response>
```

### POST /twilio/gather
Handles speech recognition results from Twilio.

**Request Body (form-encoded):**
```
CallSid: string          # Call identifier
SpeechResult: string     # Recognized speech text
Confidence: float        # Recognition confidence (0.0-1.0)
```

**Response:**
- Content-Type: `application/xml`
- Body: TwiML response with next action

### POST /twilio/status
Handles call status updates from Twilio.

**Request Body (form-encoded):**
```
CallSid: string          # Call identifier
CallStatus: string       # New call status
CallDuration: string     # Call duration in seconds
```

**Response:**
```json
{
    "status": "ok"
}
```

## WebSocket Endpoints

### WS /twilio/media
Handles Twilio Media Streams for real-time audio.

**Query Parameters:**
- `callSid`: Call identifier
- `token`: Session authentication token

**Message Types:**

#### Start Message
```json
{
    "event": "start",
    "sequenceNumber": "1",
    "start": {
        "streamSid": "MZ123...",
        "accountSid": "AC123...",
        "callSid": "CA123..."
    }
}
```

#### Media Message
```json
{
    "event": "media",
    "sequenceNumber": "2",
    "media": {
        "track": "inbound",
        "chunk": "1",
        "timestamp": "1234567890",
        "payload": "base64-encoded-audio"
    },
    "streamSid": "MZ123..."
}
```

#### Stop Message
```json
{
    "event": "stop",
    "sequenceNumber": "3",
    "stop": {
        "streamSid": "MZ123..."
    }
}
```

## Static File Endpoints

### GET /static/tts/{call_sid}/{filename}
Serves generated TTS audio files.

**Query Parameters (if signed URLs enabled):**
- `expires`: Unix timestamp expiration
- `signature`: HMAC signature

**Response:**
- Content-Type: `audio/wav` or `audio/mpeg`
- Body: Audio file content

## Health Check

### GET /health
System health check endpoint.

**Response:**
```json
{
    "status": "healthy",
    "timestamp": "2024-01-01T12:00:00Z",
    "active_sessions": 3,
    "version": "1.0.0"
}
```

## Internal Data Models

### Session State
```json
{
    "call_sid": "CA123...",
    "phone_number": "+1234567890",
    "state": "active",
    "identity_verified": false,
    "patient_name": null,
    "patient_dob": null,
    "conversation_history": [
        {
            "timestamp": "2024-01-01T12:00:00Z",
            "speaker": "user",
            "text": "I need a refill",
            "confidence": 0.95
        }
    ],
    "barge_in_flag": false,
    "currently_playing": null
}
```

### LLM Tool Calls

#### place_refill
```json
{
    "function": "place_refill",
    "arguments": {
        "name": "John Doe",
        "dob": "1980-01-01",
        "med": "atorvastatin",
        "dose": "20 mg",
        "qty": 30,
        "pharmacy": "CVS Main Street"
    }
}
```

#### check_interactions
```json
{
    "function": "check_interactions",
    "arguments": {
        "meds": ["atorvastatin", "lisinopril"],
        "conditions": ["diabetes"]
    }
}
```

#### get_administration_guide
```json
{
    "function": "get_administration_guide",
    "arguments": {
        "med": "atorvastatin"
    }
}
```

### Database Models

#### CallSession
```sql
CREATE TABLE call_sessions (
    id VARCHAR PRIMARY KEY,           -- Twilio CallSid
    phone_number VARCHAR NOT NULL,
    start_time DATETIME DEFAULT NOW(),
    end_time DATETIME,
    status VARCHAR DEFAULT 'active',
    identity_verified BOOLEAN DEFAULT FALSE,
    patient_name VARCHAR,
    patient_dob VARCHAR,
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW()
);
```

#### Patient
```sql
CREATE TABLE patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name VARCHAR NOT NULL,
    date_of_birth VARCHAR NOT NULL,    -- YYYY-MM-DD
    phone_number VARCHAR,
    pharmacy_preference VARCHAR,
    created_at DATETIME DEFAULT NOW()
);
```

#### Prescription
```sql
CREATE TABLE prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER REFERENCES patients(id),
    medication_name VARCHAR NOT NULL,
    dosage VARCHAR NOT NULL,
    quantity INTEGER NOT NULL,
    refills_remaining INTEGER DEFAULT 0,
    prescriber VARCHAR NOT NULL,
    pharmacy VARCHAR,
    date_prescribed DATETIME DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT NOW()
);
```

#### RefillEvent
```sql
CREATE TABLE refill_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_session_id VARCHAR REFERENCES call_sessions(id),
    patient_id INTEGER REFERENCES patients(id),
    prescription_id INTEGER REFERENCES prescriptions(id),
    medication_name VARCHAR NOT NULL,
    dosage VARCHAR NOT NULL,
    quantity_requested INTEGER NOT NULL,
    pharmacy VARCHAR NOT NULL,
    status VARCHAR NOT NULL,           -- placed, no_refills, not_found, needs_provider
    eta_minutes INTEGER,
    notes TEXT,
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW()
);
```

#### AuditLog
```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_session_id VARCHAR,
    event_type VARCHAR NOT NULL,
    event_data TEXT,                   -- JSON, PHI-redacted
    phone_number_masked VARCHAR,       -- Last 4 digits only
    patient_dob_masked VARCHAR,        -- Month/day only
    ip_address VARCHAR,
    user_agent VARCHAR,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at DATETIME DEFAULT NOW()
);
```

## Error Responses

### HTTP Errors
- `400 Bad Request`: Invalid request parameters
- `403 Forbidden`: Invalid Twilio signature or unauthorized access
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

### TwiML Error Responses
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna-Neural">
        I'm sorry, there's a technical issue. Please call back later.
    </Say>
    <Hangup/>
</Response>
```

### WebSocket Errors
- Code `1008`: Invalid token
- Code `1011`: Service unavailable
- Code `1000`: Normal closure

## Rate Limits and Quotas

### Current Limits
- No explicit rate limiting implemented
- Concurrent sessions limited by server resources
- TTS file cleanup after 2 hours
- Session cleanup after 60 minutes of inactivity

### Recommended Production Limits
- 100 concurrent calls per instance
- 1000 requests per minute per IP
- 10MB max TTS file size
- 30-minute max call duration

## Security Headers

All responses include:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
```

Webhook requests are validated using Twilio's signature validation.
