import express from 'express';
import { getDatabase } from '../database/init.js';
import { checkDrugInteractions } from '../services/DrugInteractionService.js';

const router = express.Router();

// Verify patient identity
router.post('/verify', async (req, res) => {
  try {
    const { firstName, lastName, dateOfBirth } = req.body;

    if (!firstName || !lastName || !dateOfBirth) {
      return res.status(400).json({
        success: false,
        message: 'First name, last name, and date of birth are required'
      });
    }

    const db = getDatabase();
    
    db.get(
      `SELECT id, first_name, last_name, date_of_birth, phone 
       FROM patients 
       WHERE LOWER(first_name) = LOWER(?) 
       AND LOWER(last_name) = LOWER(?) 
       AND date_of_birth = ?`,
      [firstName, lastName, dateOfBirth],
      (err, patient) => {
        if (err) {
          console.error('Database error:', err);
          return res.status(500).json({
            success: false,
            message: 'Database error occurred'
          });
        }

        if (!patient) {
          return res.status(404).json({
            success: false,
            message: 'Patient not found. Please verify your information.'
          });
        }

        res.json({
          success: true,
          patient: {
            id: patient.id,
            firstName: patient.first_name,
            lastName: patient.last_name,
            dateOfBirth: patient.date_of_birth,
            phone: patient.phone
          }
        });
      }
    );
  } catch (error) {
    console.error('Verification error:', error);
    res.status(500).json({
      success: false,
      message: 'Internal server error'
    });
  }
});

// Get patient's prescriptions
router.get('/:patientId', async (req, res) => {
  try {
    const { patientId } = req.params;

    if (!patientId || isNaN(patientId)) {
      return res.status(400).json({
        success: false,
        message: 'Valid patient ID is required'
      });
    }

    const db = getDatabase();
    
    db.all(
      `SELECT p.*, pt.first_name, pt.last_name 
       FROM prescriptions p
       JOIN patients pt ON p.patient_id = pt.id
       WHERE p.patient_id = ?
       ORDER BY p.medication_name`,
      [patientId],
      (err, prescriptions) => {
        if (err) {
          console.error('Database error:', err);
          return res.status(500).json({
            success: false,
            message: 'Database error occurred'
          });
        }

        // Filter and categorize prescriptions
        const now = new Date();
        const categorizedPrescriptions = {
          available: [],
          noRefills: [],
          expired: []
        };

        prescriptions.forEach(prescription => {
          const expiresDate = new Date(prescription.expires_date);
          
          if (expiresDate < now) {
            categorizedPrescriptions.expired.push(prescription);
          } else if (prescription.refills_remaining <= 0) {
            categorizedPrescriptions.noRefills.push(prescription);
          } else {
            categorizedPrescriptions.available.push(prescription);
          }
        });

        res.json({
          success: true,
          prescriptions: categorizedPrescriptions,
          patientName: prescriptions.length > 0 ? 
            `${prescriptions[0].first_name} ${prescriptions[0].last_name}` : null
        });
      }
    );
  } catch (error) {
    console.error('Get prescriptions error:', error);
    res.status(500).json({
      success: false,
      message: 'Internal server error'
    });
  }
});

// Process refill request
router.post('/refill', async (req, res) => {
  try {
    const { prescriptionId, patientId, quantity } = req.body;

    if (!prescriptionId || !patientId) {
      return res.status(400).json({
        success: false,
        message: 'Prescription ID and patient ID are required'
      });
    }

    const db = getDatabase();
    
    // First, get the prescription details
    db.get(
      `SELECT p.*, pt.first_name, pt.last_name 
       FROM prescriptions p
       JOIN patients pt ON p.patient_id = pt.id
       WHERE p.id = ? AND p.patient_id = ?`,
      [prescriptionId, patientId],
      async (err, prescription) => {
        if (err) {
          console.error('Database error:', err);
          return res.status(500).json({
            success: false,
            message: 'Database error occurred'
          });
        }

        if (!prescription) {
          return res.status(404).json({
            success: false,
            message: 'Prescription not found'
          });
        }

        // Check if prescription is expired
        const now = new Date();
        const expiresDate = new Date(prescription.expires_date);
        
        if (expiresDate < now) {
          return res.status(400).json({
            success: false,
            message: 'This prescription has expired. Please contact your doctor for a new prescription.'
          });
        }

        // Check if refills are available
        if (prescription.refills_remaining <= 0) {
          return res.status(400).json({
            success: false,
            message: 'No refills remaining for this prescription. Please contact your doctor.'
          });
        }

        // Check for drug interactions with patient's other medications
        try {
          const interactionCheck = await checkDrugInteractions(patientId, prescription.medication_name);
          
          if (interactionCheck.hasInteractions) {
            return res.status(400).json({
              success: false,
              message: `Potential drug interaction detected: ${interactionCheck.warning}. Please consult with your pharmacist or doctor.`,
              interactions: interactionCheck.interactions
            });
          }
        } catch (interactionError) {
          console.error('Drug interaction check failed:', interactionError);
          // Continue with refill but log the error
        }

        // Process the refill
        const refillQuantity = quantity || prescription.quantity;
        const confirmationNumber = generateConfirmationNumber();
        const pickupTime = getEstimatedPickupTime();

        // Update prescription (decrease refills, update last_filled)
        db.run(
          `UPDATE prescriptions 
           SET refills_remaining = refills_remaining - 1, 
               last_filled = DATE('now')
           WHERE id = ?`,
          [prescriptionId],
          function(updateErr) {
            if (updateErr) {
              console.error('Update error:', updateErr);
              return res.status(500).json({
                success: false,
                message: 'Failed to process refill'
              });
            }

            res.json({
              success: true,
              message: 'Refill processed successfully',
              refill: {
                confirmationNumber,
                medicationName: prescription.medication_name,
                dosage: prescription.dosage,
                quantity: refillQuantity,
                pickupTime,
                refillsRemaining: prescription.refills_remaining - 1,
                patientName: `${prescription.first_name} ${prescription.last_name}`
              }
            });
          }
        );
      }
    );
  } catch (error) {
    console.error('Refill error:', error);
    res.status(500).json({
      success: false,
      message: 'Internal server error'
    });
  }
});

// Check for drug interactions
router.post('/check-interactions', async (req, res) => {
  try {
    const { patientId, medicationName } = req.body;

    if (!patientId || !medicationName) {
      return res.status(400).json({
        success: false,
        message: 'Patient ID and medication name are required'
      });
    }

    const interactionCheck = await checkDrugInteractions(patientId, medicationName);
    
    res.json({
      success: true,
      ...interactionCheck
    });
  } catch (error) {
    console.error('Drug interaction check error:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to check drug interactions'
    });
  }
});

// Helper functions
function generateConfirmationNumber() {
  const timestamp = Date.now().toString().slice(-6);
  const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0');
  return `RX${timestamp}${random}`;
}

function getEstimatedPickupTime() {
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

export default router;

