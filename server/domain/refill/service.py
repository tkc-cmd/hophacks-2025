"""Prescription refill service."""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import and_

from server.persistence.models import Patient, Prescription, RefillEvent, CallSession, AuditLog
from server.middleware.phi_guard import mask_phone_number, mask_date_of_birth


class RefillStatus(str, Enum):
    PLACED = "placed"
    NO_REFILLS = "no_refills"
    NOT_FOUND = "not_found"
    NEEDS_PROVIDER = "needs_provider"
    ERROR = "error"


class RefillRequest(BaseModel):
    name: str
    date_of_birth: str  # YYYY-MM-DD format
    medication: str
    dosage: str
    quantity: int
    pharmacy: str


class RefillResult(BaseModel):
    status: RefillStatus
    eta_minutes: Optional[int] = None
    message: str
    prescription_id: Optional[int] = None
    refills_remaining: Optional[int] = None


class RefillService:
    """Service for handling prescription refill requests."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def place_refill(
        self, 
        request: RefillRequest, 
        call_session_id: str
    ) -> RefillResult:
        """Process a prescription refill request."""
        
        try:
            # Log the refill attempt
            await self._log_refill_attempt(request, call_session_id)
            
            # Find patient by name and DOB
            patient = self._find_patient(request.name, request.date_of_birth)
            if not patient:
                return RefillResult(
                    status=RefillStatus.NOT_FOUND,
                    message=f"No patient found with name {request.name} and the provided date of birth."
                )
            
            # Find matching prescription
            prescription = self._find_prescription(
                patient.id, 
                request.medication, 
                request.dosage
            )
            
            if not prescription:
                # Log the refill event as not found
                refill_event = RefillEvent(
                    call_session_id=call_session_id,
                    patient_id=patient.id,
                    prescription_id=None,
                    medication_name=request.medication,
                    dosage=request.dosage,
                    quantity_requested=request.quantity,
                    pharmacy=request.pharmacy,
                    status=RefillStatus.NOT_FOUND.value,
                    notes=f"No active prescription found for {request.medication} {request.dosage}"
                )
                self.db.add(refill_event)
                self.db.commit()
                
                return RefillResult(
                    status=RefillStatus.NOT_FOUND,
                    message=f"No active prescription found for {request.medication} {request.dosage}. Please contact your prescriber."
                )
            
            # Check if refills are available
            if prescription.refills_remaining <= 0:
                # Log the refill event as no refills
                refill_event = RefillEvent(
                    call_session_id=call_session_id,
                    patient_id=patient.id,
                    prescription_id=prescription.id,
                    medication_name=request.medication,
                    dosage=request.dosage,
                    quantity_requested=request.quantity,
                    pharmacy=request.pharmacy,
                    status=RefillStatus.NO_REFILLS.value,
                    notes="No refills remaining on prescription"
                )
                self.db.add(refill_event)
                self.db.commit()
                
                return RefillResult(
                    status=RefillStatus.NO_REFILLS,
                    message=f"No refills remaining for {request.medication}. Please contact {prescription.prescriber} for a new prescription.",
                    prescription_id=prescription.id,
                    refills_remaining=0
                )
            
            # Calculate ETA based on pharmacy and time of day
            eta_minutes = self._calculate_eta(request.pharmacy)
            
            # Create successful refill event
            refill_event = RefillEvent(
                call_session_id=call_session_id,
                patient_id=patient.id,
                prescription_id=prescription.id,
                medication_name=request.medication,
                dosage=request.dosage,
                quantity_requested=request.quantity,
                pharmacy=request.pharmacy,
                status=RefillStatus.PLACED.value,
                eta_minutes=eta_minutes,
                notes=f"Refill placed successfully. ETA: {eta_minutes} minutes"
            )
            self.db.add(refill_event)
            
            # Update prescription refills remaining
            prescription.refills_remaining -= 1
            
            self.db.commit()
            
            return RefillResult(
                status=RefillStatus.PLACED,
                eta_minutes=eta_minutes,
                message=f"Refill placed successfully! Your {request.medication} will be ready in approximately {eta_minutes} minutes at {request.pharmacy}.",
                prescription_id=prescription.id,
                refills_remaining=prescription.refills_remaining
            )
            
        except Exception as e:
            self.db.rollback()
            
            # Log the error
            audit_log = AuditLog(
                call_session_id=call_session_id,
                event_type="refill_error",
                event_data=f"Error processing refill: {str(e)}",
                phone_number_masked="****",
                success=False,
                error_message=str(e)
            )
            self.db.add(audit_log)
            self.db.commit()
            
            return RefillResult(
                status=RefillStatus.ERROR,
                message="I'm sorry, there was an error processing your refill request. Please try again or call the pharmacy directly."
            )
    
    def _find_patient(self, name: str, date_of_birth: str) -> Optional[Patient]:
        """Find patient by name and date of birth."""
        return self.db.query(Patient).filter(
            and_(
                Patient.full_name.ilike(f"%{name}%"),
                Patient.date_of_birth == date_of_birth
            )
        ).first()
    
    def _find_prescription(
        self, 
        patient_id: int, 
        medication: str, 
        dosage: str
    ) -> Optional[Prescription]:
        """Find active prescription for patient."""
        return self.db.query(Prescription).filter(
            and_(
                Prescription.patient_id == patient_id,
                Prescription.medication_name.ilike(f"%{medication}%"),
                Prescription.dosage.ilike(f"%{dosage}%"),
                Prescription.is_active == True
            )
        ).first()
    
    def _calculate_eta(self, pharmacy: str) -> int:
        """Calculate estimated time for prescription to be ready."""
        # Simple ETA calculation based on pharmacy and current time
        current_hour = datetime.now().hour
        
        # Base ETA
        base_eta = 30
        
        # Adjust for time of day (busier during certain hours)
        if 9 <= current_hour <= 11 or 17 <= current_hour <= 19:  # Peak hours
            base_eta += 15
        elif 12 <= current_hour <= 14:  # Lunch rush
            base_eta += 10
        
        # Adjust for pharmacy type (simplified)
        if "cvs" in pharmacy.lower():
            base_eta += 5
        elif "walgreens" in pharmacy.lower():
            base_eta += 0
        elif "rite aid" in pharmacy.lower():
            base_eta -= 5
        
        return max(15, min(base_eta, 90))  # Between 15-90 minutes
    
    async def _log_refill_attempt(self, request: RefillRequest, call_session_id: str):
        """Log refill attempt with PHI protection."""
        audit_log = AuditLog(
            call_session_id=call_session_id,
            event_type="refill_attempt",
            event_data=f"Refill request for {request.medication} {request.dosage}",
            patient_dob_masked=mask_date_of_birth(request.date_of_birth),
            success=True
        )
        self.db.add(audit_log)
        self.db.commit()
    
    async def get_patient_prescriptions(
        self, 
        name: str, 
        date_of_birth: str
    ) -> List[Prescription]:
        """Get all active prescriptions for a patient."""
        patient = self._find_patient(name, date_of_birth)
        if not patient:
            return []
        
        return self.db.query(Prescription).filter(
            and_(
                Prescription.patient_id == patient.id,
                Prescription.is_active == True
            )
        ).all()
    
    async def get_refill_history(
        self, 
        call_session_id: str
    ) -> List[RefillEvent]:
        """Get refill history for current call session."""
        return self.db.query(RefillEvent).filter(
            RefillEvent.call_session_id == call_session_id
        ).order_by(RefillEvent.created_at.desc()).all()
