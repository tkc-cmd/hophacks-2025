import express from 'express';
import { v4 as uuidv4 } from 'uuid';

const router = express.Router();

// Start a new voice session
router.post('/start-session', async (req, res) => {
  try {
    const sessionId = uuidv4();
    const timestamp = new Date().toISOString();

    // Initialize session data
    const sessionData = {
      id: sessionId,
      startTime: timestamp,
      state: 'greeting',
      patient: null,
      context: {},
      isActive: true
    };

    // In a production app, you'd store this in Redis or a database
    // For now, we'll rely on the WebSocket connection to manage state

    res.json({
      success: true,
      sessionId,
      message: 'Voice session started successfully'
    });
  } catch (error) {
    console.error('Start session error:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to start voice session'
    });
  }
});

// Health check for voice services
router.get('/health', async (req, res) => {
  try {
    // Check if all voice services are available
    const services = {
      deepgram: !!process.env.DEEPGRAM_API_KEY,
      gemini: !!process.env.GEMINI_API_KEY,
      elevenlabs: !!process.env.ELEVENLABS_API_KEY
    };

    const allServicesReady = Object.values(services).every(Boolean);

    res.json({
      success: true,
      services,
      ready: allServicesReady,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('Voice health check error:', error);
    res.status(500).json({
      success: false,
      message: 'Voice services health check failed'
    });
  }
});

export default router;

