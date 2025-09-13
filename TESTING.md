# Testing Guide for RxVoice Assistant

This document provides comprehensive testing scenarios and instructions for the RxVoice Assistant application.

## 🧪 Setup Testing

### 1. Run Setup Verification
```bash
node test-setup.js
```

This script checks:
- ✅ All required files exist
- ✅ Dependencies are installed
- ✅ Environment configuration
- ✅ API keys are configured

## 🎭 Mock Data Testing

### Available Test Patients

| Name | DOB | Available Prescriptions |
|------|-----|------------------------|
| John Smith | 1965-05-15 | Metformin 500mg (3 refills), Lisinopril 10mg (2 refills), Atorvastatin 20mg (1 refill) |
| Mary Johnson | 1972-08-22 | Levothyroxine 75mcg (5 refills), Amlodipine 5mg (4 refills), Omeprazole 20mg (0 refills) |
| Robert Williams | 1958-12-03 | Warfarin 5mg (2 refills), Furosemide 40mg (3 refills) |
| Patricia Brown | 1980-03-17 | Sertraline 50mg (5 refills), Ibuprofen 600mg (1 refill) |
| Michael Davis | 1945-09-28 | Insulin Glargine (2 refills), Metoprolol 50mg (4 refills), Aspirin 81mg (0 refills) |

## 🗣️ Voice Interaction Testing

### Test Scenario 1: Successful Refill
**Patient**: John Smith
**DOB**: 05/15/1965

**Conversation Flow**:
1. Say: "Hello, I need to refill my prescription"
2. Say: "My name is John Smith"
3. Say: "My date of birth is May 15th, 1965"
4. Say: "I want to refill my Metformin"
5. Confirm the refill

**Expected Result**: 
- Successful refill with confirmation number
- Pickup time provided
- Refill count decremented

### Test Scenario 2: Patient Not Found
**Patient**: Invalid Name
**DOB**: 01/01/1990

**Conversation Flow**:
1. Say: "I need a refill"
2. Say: "My name is Jane Doe"
3. Say: "January 1st, 1990"

**Expected Result**: 
- Error message about patient not found
- Request to verify information
- Option to try again

### Test Scenario 3: No Refills Remaining
**Patient**: Mary Johnson
**DOB**: 08/22/1972

**Conversation Flow**:
1. Say: "Hello, I need to refill my prescription"
2. Say: "Mary Johnson"
3. Say: "August 22nd, 1972"
4. Say: "I want to refill my Omeprazole"

**Expected Result**: 
- Error message about no refills remaining
- Suggestion to contact doctor
- List of other available prescriptions

### Test Scenario 4: Drug Interaction Detection
**Patient**: Robert Williams
**DOB**: 12/03/1958

**Conversation Flow**:
1. Say: "I need to refill my Warfarin"
2. Provide patient details
3. Select Warfarin for refill

**Expected Result**: 
- Potential interaction warning (if other medications present)
- Safety recommendation
- Option to consult pharmacist

### Test Scenario 5: Voice Interruption
**Any Patient**

**Test Steps**:
1. Start conversation
2. While agent is speaking, start talking
3. Observe interruption handling

**Expected Result**: 
- Agent stops speaking immediately
- Audio queue clears
- Returns to listening mode
- No audio overlap

## 🔧 Technical Testing

### WebSocket Connection Testing

1. **Connection Establishment**
   - Open application
   - Verify "Connected" status
   - Check browser console for WebSocket connection

2. **Connection Recovery**
   - Stop backend server
   - Observe "Disconnected" status
   - Restart server
   - Verify automatic reconnection

3. **Message Handling**
   - Send text messages
   - Verify transcript updates
   - Check audio responses

### Audio System Testing

1. **Microphone Permissions**
   - Grant microphone access
   - Verify "Ready" status
   - Test recording functionality

2. **Audio Recording**
   - Click microphone button
   - Verify "Listening" state
   - Speak and check transcription

3. **Audio Playback**
   - Ensure speakers/headphones work
   - Test voice responses
   - Verify audio interruption

### Database Testing

1. **Patient Verification**
   - Test valid patient credentials
   - Test invalid combinations
   - Verify case-insensitive matching

2. **Prescription Queries**
   - Check available prescriptions
   - Verify refill counts
   - Test expiration date logic

3. **Refill Processing**
   - Process successful refills
   - Verify database updates
   - Check confirmation generation

## 🐛 Error Scenario Testing

### API Service Failures

1. **Deepgram API Failure**
   - Use invalid API key
   - Test fallback behavior
   - Verify error messages

2. **Gemini API Failure**
   - Simulate API timeout
   - Check fallback responses
   - Test conversation continuity

3. **ElevenLabs API Failure**
   - Test without audio output
   - Verify text-only mode
   - Check error handling

### Network Issues

1. **Slow Connection**
   - Throttle network speed
   - Test audio streaming
   - Verify timeout handling

2. **Connection Loss**
   - Disconnect internet
   - Test reconnection logic
   - Verify session recovery

### Browser Compatibility

1. **Chrome/Chromium**
   - Test all features
   - Verify WebRTC support
   - Check audio permissions

2. **Firefox**
   - Test WebSocket connection
   - Verify audio recording
   - Check compatibility issues

3. **Safari**
   - Test iOS Safari
   - Verify audio constraints
   - Check permission handling

## 📱 Mobile Testing

### Responsive Design
- Test on various screen sizes
- Verify touch interactions
- Check mobile audio handling

### Mobile Audio
- Test microphone on mobile
- Verify audio playback
- Check iOS/Android differences

## 🔒 Security Testing

### Input Validation
- Test SQL injection attempts
- Verify XSS protection
- Check input sanitization

### Session Management
- Test session timeouts
- Verify session cleanup
- Check concurrent sessions

### Data Protection
- Verify no audio storage
- Check transcript handling
- Test data encryption

## 📊 Performance Testing

### Load Testing
- Multiple concurrent users
- WebSocket connection limits
- Database query performance

### Audio Latency
- Measure speech-to-text delay
- Test text-to-speech speed
- Verify end-to-end latency

### Memory Usage
- Monitor browser memory
- Check for memory leaks
- Test long conversations

## 🎯 Acceptance Criteria

### Core Functionality
- ✅ Voice recording and transcription
- ✅ Natural conversation flow
- ✅ Patient identity verification
- ✅ Prescription refill processing
- ✅ Drug interaction checking
- ✅ Audio response generation

### User Experience
- ✅ Intuitive interface design
- ✅ Clear visual feedback
- ✅ Smooth voice interactions
- ✅ Error recovery mechanisms
- ✅ Mobile responsiveness

### Technical Requirements
- ✅ WebSocket real-time communication
- ✅ Audio streaming performance
- ✅ Database integration
- ✅ API service integration
- ✅ Error handling and logging

## 📝 Test Reporting

### Bug Report Template
```
**Bug Title**: Brief description
**Severity**: Critical/High/Medium/Low
**Steps to Reproduce**:
1. Step one
2. Step two
3. Step three

**Expected Result**: What should happen
**Actual Result**: What actually happened
**Browser/Device**: Chrome 119, Windows 11
**Additional Info**: Screenshots, console logs
```

### Test Results Template
```
**Test Case**: Scenario name
**Status**: Pass/Fail/Blocked
**Execution Date**: YYYY-MM-DD
**Tester**: Name
**Notes**: Additional observations
**Evidence**: Screenshots/recordings
```

## 🚀 Automated Testing

### Unit Tests
```bash
# Backend tests
cd backend && npm test

# Frontend tests
cd frontend && npm test
```

### Integration Tests
```bash
# Run full integration test suite
npm run test:integration
```

### End-to-End Tests
```bash
# Run E2E tests with Cypress/Playwright
npm run test:e2e
```

## 📋 Testing Checklist

### Pre-Release Testing
- [ ] All API keys configured
- [ ] Database seeded with mock data
- [ ] WebSocket connection stable
- [ ] Audio permissions working
- [ ] All test scenarios pass
- [ ] Error handling verified
- [ ] Performance benchmarks met
- [ ] Security checks completed
- [ ] Mobile compatibility confirmed
- [ ] Browser compatibility verified

### Demo Preparation
- [ ] Test environment setup
- [ ] Demo script prepared
- [ ] Backup scenarios ready
- [ ] Error recovery tested
- [ ] Audience interaction planned
- [ ] Technical setup verified

---

## 🎪 Demo Script

### 5-Minute Demo Flow

1. **Introduction** (30 seconds)
   - "Welcome to RxVoice Assistant"
   - Show clean, professional interface
   - Highlight voice-first interaction

2. **Happy Path Demo** (2 minutes)
   - Use John Smith test case
   - Show natural conversation
   - Demonstrate voice interruption
   - Complete successful refill

3. **Error Handling** (1 minute)
   - Show patient not found scenario
   - Demonstrate graceful error recovery
   - Highlight safety features

4. **Technical Features** (1 minute)
   - Show real-time transcription
   - Demonstrate drug interaction checking
   - Highlight WebSocket connectivity

5. **Wrap-up** (30 seconds)
   - Emphasize healthcare innovation
   - Mention scalability potential
   - Thank audience

### Backup Scenarios
- Text input if voice fails
- Pre-recorded audio if live demo issues
- Static screenshots for worst-case scenario

Remember: This is a demo with mock data - always emphasize the prototype nature and real-world implementation considerations.

