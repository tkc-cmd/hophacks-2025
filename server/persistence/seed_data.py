"""Seed database with test data."""

import sys
import os
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy.orm import Session
from server.persistence import SessionLocal
from server.persistence.models import Patient, Prescription


def seed_patients_and_prescriptions():
    """Seed mock patients and prescriptions."""
    db: Session = SessionLocal()
    
    try:
        # Clear existing data
        db.query(Prescription).delete()
        db.query(Patient).delete()
        
        # Create test patients
        patients_data = [
            {
                "full_name": "Jane Smith",
                "date_of_birth": "1975-01-02",
                "phone_number": "+15551234567",
                "pharmacy_preference": "CVS Pharmacy Main St"
            },
            {
                "full_name": "John Doe",
                "date_of_birth": "1980-06-15",
                "phone_number": "+15559876543",
                "pharmacy_preference": "Walgreens Downtown"
            },
            {
                "full_name": "Mary Johnson",
                "date_of_birth": "1965-03-20",
                "phone_number": "+15555555555",
                "pharmacy_preference": "Rite Aid Plaza"
            }
        ]
        
        patients = []
        for data in patients_data:
            patient = Patient(**data)
            db.add(patient)
            patients.append(patient)
        
        db.commit()
        
        # Refresh to get IDs
        for patient in patients:
            db.refresh(patient)
        
        # Create prescriptions
        prescriptions_data = [
            # Jane Smith prescriptions
            {
                "patient_id": patients[0].id,
                "medication_name": "atorvastatin",
                "dosage": "20 mg",
                "quantity": 30,
                "refills_remaining": 2,
                "prescriber": "Dr. Williams",
                "pharmacy": "CVS Pharmacy Main St"
            },
            {
                "patient_id": patients[0].id,
                "medication_name": "lisinopril",
                "dosage": "10 mg",
                "quantity": 30,
                "refills_remaining": 1,
                "prescriber": "Dr. Williams",
                "pharmacy": "CVS Pharmacy Main St"
            },
            # John Doe prescriptions
            {
                "patient_id": patients[1].id,
                "medication_name": "metformin",
                "dosage": "500 mg",
                "quantity": 60,
                "refills_remaining": 3,
                "prescriber": "Dr. Garcia",
                "pharmacy": "Walgreens Downtown"
            },
            {
                "patient_id": patients[1].id,
                "medication_name": "sertraline",
                "dosage": "50 mg",
                "quantity": 30,
                "refills_remaining": 0,  # No refills left
                "prescriber": "Dr. Chen",
                "pharmacy": "Walgreens Downtown"
            },
            # Mary Johnson prescriptions
            {
                "patient_id": patients[2].id,
                "medication_name": "amoxicillin",
                "dosage": "500 mg",
                "quantity": 21,
                "refills_remaining": 0,
                "prescriber": "Dr. Brown",
                "pharmacy": "Rite Aid Plaza",
                "date_prescribed": datetime.now() - timedelta(days=5)
            },
            {
                "patient_id": patients[2].id,
                "medication_name": "ibuprofen",
                "dosage": "200 mg",
                "quantity": 100,
                "refills_remaining": 2,
                "prescriber": "Dr. Brown",
                "pharmacy": "Rite Aid Plaza"
            }
        ]
        
        for data in prescriptions_data:
            prescription = Prescription(**data)
            db.add(prescription)
        
        db.commit()
        
        print("✅ Successfully seeded database with test patients and prescriptions!")
        print(f"   - Created {len(patients)} patients")
        print(f"   - Created {len(prescriptions_data)} prescriptions")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    """Main seeding function."""
    print("Seeding database with test data...")
    seed_patients_and_prescriptions()


if __name__ == "__main__":
    main()
