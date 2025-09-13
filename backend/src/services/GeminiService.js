import { GoogleGenerativeAI } from '@google/generative-ai';

export class GeminiService {
  constructor() {
    this.apiKey = process.env.GEMINI_API_KEY;
    
    if (!this.apiKey) {
      throw new Error('GEMINI_API_KEY environment variable is required');
    }

    this.genAI = new GoogleGenerativeAI(this.apiKey);
    this.model = this.genAI.getGenerativeModel({ model: "gemini-pro" });
    
    this.systemPrompt = `You are RxVoice Assistant, a professional and friendly AI pharmacist assistant. Your role is to help patients with prescription refills and provide basic pharmaceutical guidance.

IMPORTANT GUIDELINES:
- Always maintain a professional, caring, and reassuring tone
- Be concise but thorough in your responses
- Never provide medical advice or diagnose conditions
- Always recommend consulting healthcare providers for medical concerns
- Focus on prescription refill processes and basic medication information
- Be patient and understanding with elderly or confused patients
- Use clear, simple language avoiding complex medical jargon
- Always verify patient identity before discussing prescriptions
- Follow HIPAA guidelines for patient privacy

CONVERSATION FLOW:
1. Greeting - Welcome the patient warmly
2. Intent Recognition - Understand if they want refills or have questions
3. Identity Verification - Get full name and date of birth
4. Prescription Review - List available prescriptions
5. Selection - Help patient choose which medications to refill
6. Safety Check - Verify no contraindications or interactions
7. Confirmation - Provide refill confirmation and pickup details

RESPONSE FORMAT:
- Keep responses conversational and natural
- Ask one question at a time
- Provide clear next steps
- Use empathetic language when dealing with issues
- Always end with a question or clear direction for the patient

Remember: You are helping real patients with their healthcare needs. Be compassionate, accurate, and professional at all times.`;
  }

  async generateResponse(userInput, conversationState, context = {}) {
    try {
      const prompt = this.buildPrompt(userInput, conversationState, context);
      
      const result = await this.model.generateContent(prompt);
      const response = await result.response;
      const text = response.text();

      return {
        response: text.trim(),
        confidence: 0.9, // Gemini doesn't provide confidence scores
        usage: {
          promptTokens: prompt.length / 4, // Rough estimate
          completionTokens: text.length / 4,
          totalTokens: (prompt.length + text.length) / 4
        }
      };

    } catch (error) {
      console.error('Gemini generation error:', error);
      
      // Provide fallback responses based on conversation state
      return this.getFallbackResponse(conversationState, userInput);
    }
  }

  buildPrompt(userInput, conversationState, context) {
    let prompt = this.systemPrompt + '\n\n';
    
    // Add conversation context
    prompt += `CURRENT CONVERSATION STATE: ${conversationState.state}\n`;
    
    if (conversationState.patient) {
      prompt += `PATIENT: ${conversationState.patient.firstName} ${conversationState.patient.lastName}\n`;
    }

    if (context.prescriptions) {
      prompt += `AVAILABLE PRESCRIPTIONS:\n`;
      context.prescriptions.forEach((rx, index) => {
        prompt += `${index + 1}. ${rx.medication_name} ${rx.dosage} - ${rx.refills_remaining} refills remaining\n`;
      });
    }

    if (context.selectedPrescription) {
      prompt += `SELECTED PRESCRIPTION: ${context.selectedPrescription.medication_name} ${context.selectedPrescription.dosage}\n`;
    }

    if (context.interactionWarning) {
      prompt += `DRUG INTERACTION WARNING: ${context.interactionWarning}\n`;
    }

    // Add conversation history
    if (conversationState.history && conversationState.history.length > 0) {
      prompt += '\nCONVERSATION HISTORY:\n';
      conversationState.history.slice(-6).forEach(entry => {
        prompt += `${entry.role}: ${entry.message}\n`;
      });
    }

    prompt += `\nUSER INPUT: "${userInput}"\n\n`;
    prompt += `Please provide an appropriate response based on the current state and context. Keep it conversational and under 100 words.`;

    return prompt;
  }

  getFallbackResponse(conversationState, userInput) {
    const fallbackResponses = {
      greeting: {
        response: "Hello! I'm RxVoice Assistant, your pharmacy helper. I can help you refill prescriptions or answer basic medication questions. How can I assist you today?",
        confidence: 0.8
      },
      identity_verification: {
        response: "I'd be happy to help you with your prescription refill. To get started, could you please tell me your full name?",
        confidence: 0.8
      },
      date_of_birth: {
        response: "Thank you. Now, could you please provide your date of birth for verification? Please say it in month, day, year format.",
        confidence: 0.8
      },
      prescription_selection: {
        response: "I can see your available prescriptions. Which medication would you like to refill today? You can tell me the name of the medication.",
        confidence: 0.8
      },
      confirmation: {
        response: "Perfect! I'm processing your refill request now. Please hold on just a moment while I check for any interactions and prepare your confirmation.",
        confidence: 0.8
      },
      error: {
        response: "I apologize, but I'm having trouble processing your request right now. Could you please repeat what you need help with?",
        confidence: 0.7
      }
    };

    const stateResponse = fallbackResponses[conversationState.state] || fallbackResponses.error;
    
    return {
      ...stateResponse,
      usage: {
        promptTokens: 0,
        completionTokens: stateResponse.response.length / 4,
        totalTokens: stateResponse.response.length / 4
      }
    };
  }

  async analyzeIntent(userInput) {
    try {
      const prompt = `
Analyze the following user input and determine their intent. Respond with a JSON object containing:
- intent: one of ["refill", "question", "greeting", "confirmation", "cancellation", "unclear"]
- confidence: number between 0 and 1
- entities: any specific medications, names, or dates mentioned

User input: "${userInput}"

Example response:
{
  "intent": "refill",
  "confidence": 0.9,
  "entities": {
    "medication": "metformin",
    "action": "refill"
  }
}
`;

      const result = await this.model.generateContent(prompt);
      const response = await result.response;
      const text = response.text();

      try {
        return JSON.parse(text);
      } catch (parseError) {
        // Fallback intent analysis
        return this.basicIntentAnalysis(userInput);
      }

    } catch (error) {
      console.error('Intent analysis error:', error);
      return this.basicIntentAnalysis(userInput);
    }
  }

  basicIntentAnalysis(userInput) {
    const input = userInput.toLowerCase();
    
    if (input.includes('refill') || input.includes('prescription') || input.includes('medication')) {
      return { intent: 'refill', confidence: 0.8, entities: {} };
    }
    
    if (input.includes('hello') || input.includes('hi') || input.includes('help')) {
      return { intent: 'greeting', confidence: 0.9, entities: {} };
    }
    
    if (input.includes('yes') || input.includes('confirm') || input.includes('correct')) {
      return { intent: 'confirmation', confidence: 0.8, entities: {} };
    }
    
    if (input.includes('no') || input.includes('cancel') || input.includes('stop')) {
      return { intent: 'cancellation', confidence: 0.8, entities: {} };
    }
    
    return { intent: 'unclear', confidence: 0.5, entities: {} };
  }

  async extractPatientInfo(userInput) {
    try {
      const prompt = `
Extract patient information from the following input. Look for:
- First name
- Last name  
- Date of birth (in various formats)

User input: "${userInput}"

Respond with JSON:
{
  "firstName": "extracted first name or null",
  "lastName": "extracted last name or null", 
  "dateOfBirth": "extracted date in YYYY-MM-DD format or null"
}
`;

      const result = await this.model.generateContent(prompt);
      const response = await result.response;
      const text = response.text();

      try {
        return JSON.parse(text);
      } catch (parseError) {
        return this.basicPatientInfoExtraction(userInput);
      }

    } catch (error) {
      console.error('Patient info extraction error:', error);
      return this.basicPatientInfoExtraction(userInput);
    }
  }

  basicPatientInfoExtraction(userInput) {
    // Basic regex patterns for common name and date formats
    const namePattern = /(?:my name is|i'm|i am)\s+([a-zA-Z]+)\s+([a-zA-Z]+)/i;
    const datePattern = /(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/;
    
    const nameMatch = userInput.match(namePattern);
    const dateMatch = userInput.match(datePattern);
    
    let dateOfBirth = null;
    if (dateMatch) {
      const [, month, day, year] = dateMatch;
      dateOfBirth = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
    }
    
    return {
      firstName: nameMatch ? nameMatch[1] : null,
      lastName: nameMatch ? nameMatch[2] : null,
      dateOfBirth
    };
  }

  // Method to check if response is appropriate for voice
  optimizeForVoice(text) {
    // Remove markdown formatting
    let optimized = text.replace(/[*_`]/g, '');
    
    // Replace abbreviations with full words
    optimized = optimized.replace(/\bDr\./g, 'Doctor');
    optimized = optimized.replace(/\bmg\b/g, 'milligrams');
    optimized = optimized.replace(/\bmcg\b/g, 'micrograms');
    optimized = optimized.replace(/\bml\b/g, 'milliliters');
    
    // Add pauses for better speech flow
    optimized = optimized.replace(/\. /g, '. ');
    optimized = optimized.replace(/\? /g, '? ');
    optimized = optimized.replace(/! /g, '! ');
    
    return optimized;
  }
}

