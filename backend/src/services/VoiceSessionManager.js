import { DeepgramService } from './DeepgramService.js';
import { ElevenLabsService } from './ElevenLabsService.js';
import { GeminiService } from './GeminiService.js';
import { ConversationStateMachine } from './ConversationStateMachine.js';
import { getDatabase } from '../database/init.js';
import { checkDrugInteractions } from './DrugInteractionService.js';
import { v4 as uuidv4 } from 'uuid';

export class VoiceSessionManager {
  constructor() {
    this.sessions = new Map();
    this.deepgram = new DeepgramService();
    this.elevenlabs = new ElevenLabsService();
    this.gemini = new GeminiService();
    this.stateMachine = new ConversationStateMachine();
    
    // Session timeout (5 minutes)
    this.sessionTimeout = parseInt(process.env.SESSION_TIMEOUT) || 300000;
    
    // Start cleanup interval
    this.startCleanupInterval();
  }

  async handleMessage(ws, data) {
    try {
      const { type, sessionId, payload } = data;

      switch (type) {
        case 'start_session':
          return await this.startSession(ws, sessionId);
          
        case 'audio_chunk':
          return await this.handleAudioChunk(ws, sessionId, payload);
          
        case 'end_audio':
          return await this.handleEndAudio(ws, sessionId);
          
        case 'text_input':
          return await this.handleTextInput(ws, sessionId, payload);
          
        case 'interrupt':
          return await this.handleInterrupt(ws, sessionId);
          
        case 'end_session':
          return await this.endSession(ws, sessionId);
          
        default:
          throw new Error(`Unknown message type: ${type}`);
      }
    } catch (error) {
      console.error('Voice session error:', error);
      this.sendError(ws, error.message);
    }
  }

  async startSession(ws, sessionId) {
    const session = {
      id: sessionId || uuidv4(),
      ws,
      startTime: Date.now(),
      lastActivity: Date.now(),
      state: this.stateMachine.states.GREETING,
      context: {
        patient: null,
        prescriptions: null,
        selectedPrescription: null,
        audioBuffer: Buffer.alloc(0),
        isRecording: false,
        isSpeaking: false,
        history: []
      }
    };

    this.sessions.set(session.id, session);

    // Send initial greeting
    const greeting = "Hello! I'm RxVoice Assistant, your pharmacy helper. I can help you refill prescriptions or answer basic medication questions. How can I assist you today?";
    
    await this.synthesizeAndSendAudio(session, greeting);
    
    this.sendMessage(ws, {
      type: 'session_started',
      sessionId: session.id,
      message: greeting
    });

    return session;
  }

  async handleAudioChunk(ws, sessionId, audioData) {
    const session = this.sessions.get(sessionId);
    if (!session) {
      throw new Error('Session not found');
    }

    session.lastActivity = Date.now();

    // If agent is speaking, handle interruption
    if (session.context.isSpeaking) {
      await this.handleInterrupt(ws, sessionId);
    }

    // Accumulate audio data
    const audioBuffer = Buffer.from(audioData, 'base64');
    session.context.audioBuffer = Buffer.concat([session.context.audioBuffer, audioBuffer]);
    session.context.isRecording = true;

    // Send recording status
    this.sendMessage(ws, {
      type: 'recording_status',
      isRecording: true
    });
  }

  async handleEndAudio(ws, sessionId) {
    const session = this.sessions.get(sessionId);
    if (!session) {
      throw new Error('Session not found');
    }

    session.context.isRecording = false;
    
    try {
      // Transcribe accumulated audio
      if (session.context.audioBuffer.length > 0) {
        this.sendMessage(ws, {
          type: 'processing',
          message: 'Processing your message...'
        });

        const transcription = await this.deepgram.transcribeAudio(session.context.audioBuffer);
        
        if (transcription.transcript && transcription.transcript.length > 0) {
          // Process the transcribed text
          await this.processUserInput(session, transcription.transcript);
        } else {
          await this.handleNoTranscription(session);
        }
      }
    } catch (error) {
      console.error('Audio processing error:', error);
      await this.handleTranscriptionError(session);
    } finally {
      // Clear audio buffer
      session.context.audioBuffer = Buffer.alloc(0);
      
      this.sendMessage(ws, {
        type: 'recording_status',
        isRecording: false
      });
    }
  }

  async handleTextInput(ws, sessionId, text) {
    const session = this.sessions.get(sessionId);
    if (!session) {
      throw new Error('Session not found');
    }

    session.lastActivity = Date.now();
    await this.processUserInput(session, text);
  }

  async processUserInput(session, userInput) {
    try {
      // Add user input to history
      session.context.history.push({
        role: 'user',
        message: userInput,
        timestamp: Date.now()
      });

      // Send transcript to frontend
      this.sendMessage(session.ws, {
        type: 'transcript',
        role: 'user',
        message: userInput
      });

      // Analyze intent and determine next action
      const intent = await this.gemini.analyzeIntent(userInput);
      const transition = this.stateMachine.transition(session.state, intent.intent, session.context);
      
      // Update session state
      session.state = transition.state;
      session.context = { ...session.context, ...transition.context };

      // Execute the action
      await this.executeAction(session, transition.action, userInput, intent);

    } catch (error) {
      console.error('Input processing error:', error);
      await this.handleProcessingError(session);
    }
  }

  async executeAction(session, action, userInput, intent) {
    switch (action) {
      case 'request_name':
        await this.requestPatientName(session);
        break;
        
      case 'request_dob':
        await this.requestDateOfBirth(session, userInput);
        break;
        
      case 'verify_patient':
        await this.verifyPatient(session, userInput);
        break;
        
      case 'list_prescriptions':
        await this.listPrescriptions(session);
        break;
        
      case 'check_interactions':
        await this.checkInteractions(session, userInput);
        break;
        
      case 'process_refill':
        await this.processRefill(session);
        break;
        
      case 'complete_refill':
        await this.completeRefill(session);
        break;
        
      case 'continue':
        await this.generateContextualResponse(session, userInput);
        break;
        
      default:
        await this.generateContextualResponse(session, userInput);
    }
  }

  async requestPatientName(session) {
    const response = "I'd be happy to help you with your prescription refill. To get started, could you please tell me your full name?";
    await this.sendResponse(session, response);
  }

  async requestDateOfBirth(session, userInput) {
    // Extract name from user input
    const patientInfo = await this.gemini.extractPatientInfo(userInput);
    
    if (patientInfo.firstName && patientInfo.lastName) {
      session.context.patientName = {
        firstName: patientInfo.firstName,
        lastName: patientInfo.lastName
      };
      
      const response = `Thank you, ${patientInfo.firstName}. Now, could you please provide your date of birth for verification? Please say it in month, day, year format.`;
      await this.sendResponse(session, response);
    } else {
      const response = "I didn't catch your full name clearly. Could you please tell me your first and last name?";
      await this.sendResponse(session, response);
    }
  }

  async verifyPatient(session, userInput) {
    try {
      const patientInfo = await this.gemini.extractPatientInfo(userInput);
      
      // Use existing name if not provided in this input
      const firstName = patientInfo.firstName || session.context.patientName?.firstName;
      const lastName = patientInfo.lastName || session.context.patientName?.lastName;
      const dateOfBirth = patientInfo.dateOfBirth;

      if (!firstName || !lastName || !dateOfBirth) {
        const response = "I need your complete information to verify your identity. Could you please provide your full name and date of birth?";
        await this.sendResponse(session, response);
        return;
      }

      // Verify patient in database
      const db = getDatabase();
      const patient = await new Promise((resolve, reject) => {
        db.get(
          `SELECT id, first_name, last_name, date_of_birth, phone 
           FROM patients 
           WHERE LOWER(first_name) = LOWER(?) 
           AND LOWER(last_name) = LOWER(?) 
           AND date_of_birth = ?`,
          [firstName, lastName, dateOfBirth],
          (err, row) => {
            if (err) reject(err);
            else resolve(row);
          }
        );
      });

      if (patient) {
        session.context.patient = {
          id: patient.id,
          firstName: patient.first_name,
          lastName: patient.last_name,
          dateOfBirth: patient.date_of_birth,
          phone: patient.phone
        };

        const response = `Perfect! I found your account, ${patient.first_name}. Let me look up your available prescriptions.`;
        await this.sendResponse(session, response);
        
        // Automatically transition to prescription review
        const transition = this.stateMachine.transition(session.state, 'patient_verified', session.context);
        session.state = transition.state;
        await this.listPrescriptions(session);
        
      } else {
        const response = "I couldn't find a patient with that information in our system. Could you please double-check your name and date of birth?";
        await this.sendResponse(session, response);
        
        // Transition to error state
        const transition = this.stateMachine.transition(session.state, 'patient_not_found', session.context);
        session.state = transition.state;
      }

    } catch (error) {
      console.error('Patient verification error:', error);
      const response = "I'm having trouble verifying your information right now. Could you please try again?";
      await this.sendResponse(session, response);
    }
  }

  async listPrescriptions(session) {
    try {
      const db = getDatabase();
      const prescriptions = await new Promise((resolve, reject) => {
        db.all(
          `SELECT * FROM prescriptions 
           WHERE patient_id = ? 
           ORDER BY medication_name`,
          [session.context.patient.id],
          (err, rows) => {
            if (err) reject(err);
            else resolve(rows);
          }
        );
      });

      // Filter available prescriptions
      const now = new Date();
      const availablePrescriptions = prescriptions.filter(rx => {
        const expiresDate = new Date(rx.expires_date);
        return expiresDate > now && rx.refills_remaining > 0;
      });

      if (availablePrescriptions.length === 0) {
        const response = "I don't see any prescriptions available for refill at this time. You may need to contact your doctor for new prescriptions.";
        await this.sendResponse(session, response);
        return;
      }

      session.context.prescriptions = availablePrescriptions;

      let response = `I found ${availablePrescriptions.length} prescription${availablePrescriptions.length > 1 ? 's' : ''} available for refill: `;
      
      availablePrescriptions.forEach((rx, index) => {
        response += `${rx.medication_name} ${rx.dosage}`;
        if (index < availablePrescriptions.length - 1) {
          response += ', ';
        }
      });

      response += '. Which medication would you like to refill today?';
      
      await this.sendResponse(session, response);

    } catch (error) {
      console.error('Prescription listing error:', error);
      const response = "I'm having trouble accessing your prescription information. Please try again.";
      await this.sendResponse(session, response);
    }
  }

  async checkInteractions(session, userInput) {
    try {
      // Find selected prescription
      const selectedMedication = userInput.toLowerCase();
      const prescription = session.context.prescriptions.find(rx => 
        rx.medication_name.toLowerCase().includes(selectedMedication) ||
        selectedMedication.includes(rx.medication_name.toLowerCase())
      );

      if (!prescription) {
        const response = "I didn't find that medication in your available prescriptions. Could you please tell me which one you'd like to refill?";
        await this.sendResponse(session, response);
        return;
      }

      session.context.selectedPrescription = prescription;

      // Check for drug interactions
      const interactionCheck = await checkDrugInteractions(
        session.context.patient.id, 
        prescription.medication_name
      );

      if (interactionCheck.hasInteractions) {
        const response = `I found a potential drug interaction with ${prescription.medication_name}. ${interactionCheck.warning} Would you like me to contact your pharmacist for review?`;
        await this.sendResponse(session, response);
        
        session.context.interactionWarning = interactionCheck.warning;
        session.state = this.stateMachine.states.ERROR;
      } else {
        const response = `Great! I've checked for interactions and ${prescription.medication_name} ${prescription.dosage} is safe to refill. Let me process that for you now.`;
        await this.sendResponse(session, response);
        
        // Automatically proceed to confirmation
        const transition = this.stateMachine.transition(session.state, 'no_interactions', session.context);
        session.state = transition.state;
        await this.processRefill(session);
      }

    } catch (error) {
      console.error('Interaction check error:', error);
      const response = "I'm having trouble checking for drug interactions. Let me proceed with caution and process your refill.";
      await this.sendResponse(session, response);
      
      // Proceed to confirmation despite error
      const transition = this.stateMachine.transition(session.state, 'check_complete', session.context);
      session.state = transition.state;
      await this.processRefill(session);
    }
  }

  async processRefill(session) {
    try {
      const prescription = session.context.selectedPrescription;
      const confirmationNumber = this.generateConfirmationNumber();
      const pickupTime = this.getEstimatedPickupTime();

      // Update prescription in database
      const db = getDatabase();
      await new Promise((resolve, reject) => {
        db.run(
          `UPDATE prescriptions 
           SET refills_remaining = refills_remaining - 1, 
               last_filled = DATE('now')
           WHERE id = ?`,
          [prescription.id],
          function(err) {
            if (err) reject(err);
            else resolve();
          }
        );
      });

      session.context.refillDetails = {
        confirmationNumber,
        pickupTime,
        medication: prescription.medication_name,
        dosage: prescription.dosage,
        quantity: prescription.quantity
      };

      const response = `Perfect! Your refill for ${prescription.medication_name} ${prescription.dosage} has been processed. Your confirmation number is ${confirmationNumber}. Your prescription will be ready for pickup ${pickupTime.time} on ${pickupTime.date}. Is there anything else I can help you with today?`;
      
      await this.sendResponse(session, response);
      
      // Transition to completed state
      const transition = this.stateMachine.transition(session.state, 'confirmed', session.context);
      session.state = transition.state;

    } catch (error) {
      console.error('Refill processing error:', error);
      const response = "I'm sorry, I encountered an issue processing your refill. Please contact the pharmacy directly or try again later.";
      await this.sendResponse(session, response);
    }
  }

  async completeRefill(session) {
    const response = "Thank you for using RxVoice Assistant! Have a great day and remember to take your medications as prescribed.";
    await this.sendResponse(session, response);
    
    // Session will be cleaned up automatically
  }

  async generateContextualResponse(session, userInput) {
    try {
      const response = await this.gemini.generateResponse(
        userInput, 
        { state: session.state, history: session.context.history },
        session.context
      );
      
      await this.sendResponse(session, response.response);
      
    } catch (error) {
      console.error('Response generation error:', error);
      const fallbackResponse = "I'm sorry, I didn't understand that. Could you please repeat your request?";
      await this.sendResponse(session, fallbackResponse);
    }
  }

  async sendResponse(session, text) {
    // Add response to history
    session.context.history.push({
      role: 'assistant',
      message: text,
      timestamp: Date.now()
    });

    // Send transcript to frontend
    this.sendMessage(session.ws, {
      type: 'transcript',
      role: 'assistant',
      message: text
    });

    // Synthesize and send audio
    await this.synthesizeAndSendAudio(session, text);
  }

  async synthesizeAndSendAudio(session, text) {
    try {
      session.context.isSpeaking = true;
      
      this.sendMessage(session.ws, {
        type: 'speaking_status',
        isSpeaking: true
      });

      const optimizedText = this.gemini.optimizeForVoice(text);
      const audioResult = await this.elevenlabs.synthesizeSpeech(optimizedText);
      
      this.sendMessage(session.ws, {
        type: 'audio_response',
        audio: audioResult.audio.toString('base64'),
        contentType: audioResult.contentType
      });

    } catch (error) {
      console.error('Audio synthesis error:', error);
      // Continue without audio
    } finally {
      session.context.isSpeaking = false;
      
      this.sendMessage(session.ws, {
        type: 'speaking_status',
        isSpeaking: false
      });
    }
  }

  async handleInterrupt(ws, sessionId) {
    const session = this.sessions.get(sessionId);
    if (!session) return;

    session.context.isSpeaking = false;
    
    this.sendMessage(ws, {
      type: 'interrupted',
      message: 'Audio interrupted'
    });
  }

  async handleNoTranscription(session) {
    const response = "I didn't catch that. Could you please speak a bit louder or repeat what you said?";
    await this.sendResponse(session, response);
  }

  async handleTranscriptionError(session) {
    const response = "I'm having trouble hearing you clearly. Could you please try speaking again?";
    await this.sendResponse(session, response);
  }

  async handleProcessingError(session) {
    const response = "I apologize, I'm having some technical difficulties. Could you please try again?";
    await this.sendResponse(session, response);
  }

  sendMessage(ws, message) {
    if (ws.readyState === ws.OPEN) {
      ws.send(JSON.stringify(message));
    }
  }

  sendError(ws, error) {
    this.sendMessage(ws, {
      type: 'error',
      message: error
    });
  }

  async endSession(ws, sessionId) {
    const session = this.sessions.get(sessionId);
    if (session) {
      this.sessions.delete(sessionId);
      
      this.sendMessage(ws, {
        type: 'session_ended',
        sessionId
      });
    }
  }

  cleanup(ws) {
    // Find and remove sessions associated with this WebSocket
    for (const [sessionId, session] of this.sessions.entries()) {
      if (session.ws === ws) {
        this.sessions.delete(sessionId);
        console.log(`Cleaned up session: ${sessionId}`);
      }
    }
  }

  startCleanupInterval() {
    setInterval(() => {
      const now = Date.now();
      for (const [sessionId, session] of this.sessions.entries()) {
        if (now - session.lastActivity > this.sessionTimeout) {
          this.sessions.delete(sessionId);
          console.log(`Session timeout: ${sessionId}`);
        }
      }
    }, 60000); // Check every minute
  }

  generateConfirmationNumber() {
    const timestamp = Date.now().toString().slice(-6);
    const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0');
    return `RX${timestamp}${random}`;
  }

  getEstimatedPickupTime() {
    const now = new Date();
    const pickupTime = new Date(now.getTime() + (2 * 60 * 60 * 1000)); // 2 hours from now
    
    return {
      time: pickupTime.toLocaleTimeString('en-US', { 
        hour: 'numeric', 
        minute: '2-digit',
        hour12: true 
      }),
      date: pickupTime.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      })
    };
  }
}

