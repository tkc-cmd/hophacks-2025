import { GoogleGenerativeAI } from '@google/generative-ai';
import { getDatabase } from '../database/init.js';

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

export async function checkDrugInteractions(patientId, newMedication) {
  try {
    const db = getDatabase();
    
    // Get patient's current medications
    const currentMedications = await new Promise((resolve, reject) => {
      db.all(
        `SELECT medication_name, dosage 
         FROM prescriptions 
         WHERE patient_id = ? AND refills_remaining > 0 
         AND date(expires_date) > date('now')`,
        [patientId],
        (err, medications) => {
          if (err) reject(err);
          else resolve(medications);
        }
      );
    });

    if (currentMedications.length === 0) {
      return {
        hasInteractions: false,
        interactions: [],
        warning: null
      };
    }

    // Create medication list for AI analysis
    const medicationList = currentMedications.map(med => 
      `${med.medication_name} ${med.dosage}`
    ).join(', ');

    // Use Gemini Pro to check for interactions
    const model = genAI.getGenerativeModel({ model: "gemini-pro" });
    
    const prompt = `
As a clinical pharmacist, analyze potential drug interactions between the new medication "${newMedication}" and the patient's current medications: ${medicationList}.

Please provide:
1. Whether there are any significant drug interactions (YES/NO)
2. If YES, list the specific interactions and their severity (Major, Moderate, Minor)
3. A brief clinical recommendation

Format your response as JSON:
{
  "hasInteractions": boolean,
  "interactions": [
    {
      "medication1": "drug name",
      "medication2": "drug name", 
      "severity": "Major|Moderate|Minor",
      "description": "brief description of interaction"
    }
  ],
  "recommendation": "clinical recommendation"
}

Focus only on clinically significant interactions. Be conservative and flag potential issues.
`;

    const result = await model.generateContent(prompt);
    const response = await result.response;
    const text = response.text();

    try {
      const analysis = JSON.parse(text);
      
      return {
        hasInteractions: analysis.hasInteractions,
        interactions: analysis.interactions || [],
        warning: analysis.hasInteractions ? analysis.recommendation : null
      };
    } catch (parseError) {
      console.error('Failed to parse AI response:', parseError);
      
      // Fallback: check for known high-risk combinations
      return checkKnownInteractions(newMedication, currentMedications);
    }

  } catch (error) {
    console.error('Drug interaction check error:', error);
    
    // Fallback to basic known interactions check
    return checkKnownInteractions(newMedication, currentMedications);
  }
}

function checkKnownInteractions(newMedication, currentMedications) {
  // Basic known interaction patterns (simplified for demo)
  const knownInteractions = {
    'Warfarin': ['Aspirin', 'Ibuprofen', 'Simvastatin'],
    'Metformin': ['Furosemide'],
    'Digoxin': ['Furosemide', 'Amiodarone'],
    'Tramadol': ['Sertraline', 'Fluoxetine'],
    'Prednisone': ['Warfarin', 'Aspirin']
  };

  const newMedLower = newMedication.toLowerCase();
  const interactions = [];

  currentMedications.forEach(currentMed => {
    const currentMedName = currentMed.medication_name;
    
    // Check if new medication has known interactions with current medication
    Object.entries(knownInteractions).forEach(([drug, interactsWith]) => {
      if (newMedLower.includes(drug.toLowerCase())) {
        if (interactsWith.some(interactDrug => 
          currentMedName.toLowerCase().includes(interactDrug.toLowerCase())
        )) {
          interactions.push({
            medication1: newMedication,
            medication2: currentMedName,
            severity: 'Moderate',
            description: `Potential interaction between ${newMedication} and ${currentMedName}`
          });
        }
      }
      
      // Check reverse interaction
      if (currentMedName.toLowerCase().includes(drug.toLowerCase())) {
        if (interactsWith.some(interactDrug => 
          newMedLower.includes(interactDrug.toLowerCase())
        )) {
          interactions.push({
            medication1: currentMedName,
            medication2: newMedication,
            severity: 'Moderate',
            description: `Potential interaction between ${currentMedName} and ${newMedication}`
          });
        }
      }
    });
  });

  return {
    hasInteractions: interactions.length > 0,
    interactions,
    warning: interactions.length > 0 ? 
      'Potential drug interactions detected. Please consult with your pharmacist.' : null
  };
}

