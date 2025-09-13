"""Test prescription refill flow."""

import pytest
import asyncio
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.persistence.models import Base, Patient, Prescription, RefillEvent
from server.domain.refill.service import RefillService, RefillRequest, RefillStatus


@pytest.fixture
def db_session():
    """Create test database session."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    # Create test patient
    patient = Patient(
        full_name="Jane Smith",
        date_of_birth="1975-01-02",
        phone_number="+15551234567",
        pharmacy_preference="CVS Pharmacy Main St"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    
    # Create test prescription
    prescription = Prescription(
        patient_id=patient.id,
        medication_name="atorvastatin",
        dosage="20 mg",
        quantity=30,
        refills_remaining=2,
        prescriber="Dr. Williams",
        pharmacy="CVS Pharmacy Main St"
    )
    session.add(prescription)
    session.commit()
    
    yield session
    session.close()


@pytest.mark.asyncio
async def test_successful_refill(db_session):
    """Test successful prescription refill."""
    refill_service = RefillService(db_session)
    
    request = RefillRequest(
        name="Jane Smith",
        date_of_birth="1975-01-02",
        medication="atorvastatin",
        dosage="20 mg",
        quantity=30,
        pharmacy="CVS Pharmacy Main St"
    )
    
    result = await refill_service.place_refill(request, "test_call_123")
    
    assert result.status == RefillStatus.PLACED
    assert result.eta_minutes is not None
    assert result.eta_minutes > 0
    assert "successfully" in result.message.lower()
    assert result.prescription_id is not None
    assert result.refills_remaining == 1  # Should be decremented
    
    # Check that refill event was created
    refill_event = db_session.query(RefillEvent).filter(
        RefillEvent.call_session_id == "test_call_123"
    ).first()
    
    assert refill_event is not None
    assert refill_event.status == RefillStatus.PLACED.value
    assert refill_event.medication_name == "atorvastatin"
    assert refill_event.eta_minutes is not None


@pytest.mark.asyncio
async def test_patient_not_found(db_session):
    """Test refill request for non-existent patient."""
    refill_service = RefillService(db_session)
    
    request = RefillRequest(
        name="John Nonexistent",
        date_of_birth="1990-01-01",
        medication="atorvastatin",
        dosage="20 mg",
        quantity=30,
        pharmacy="CVS Pharmacy Main St"
    )
    
    result = await refill_service.place_refill(request, "test_call_456")
    
    assert result.status == RefillStatus.NOT_FOUND
    assert "no patient found" in result.message.lower()
    assert result.eta_minutes is None


@pytest.mark.asyncio
async def test_prescription_not_found(db_session):
    """Test refill request for non-existent prescription."""
    refill_service = RefillService(db_session)
    
    request = RefillRequest(
        name="Jane Smith",
        date_of_birth="1975-01-02",
        medication="nonexistent_drug",
        dosage="10 mg",
        quantity=30,
        pharmacy="CVS Pharmacy Main St"
    )
    
    result = await refill_service.place_refill(request, "test_call_789")
    
    assert result.status == RefillStatus.NOT_FOUND
    assert "no active prescription found" in result.message.lower()
    
    # Check that refill event was still logged
    refill_event = db_session.query(RefillEvent).filter(
        RefillEvent.call_session_id == "test_call_789"
    ).first()
    
    assert refill_event is not None
    assert refill_event.status == RefillStatus.NOT_FOUND.value


@pytest.mark.asyncio
async def test_no_refills_remaining(db_session):
    """Test refill request when no refills are left."""
    # Create prescription with no refills
    patient = db_session.query(Patient).first()
    
    prescription_no_refills = Prescription(
        patient_id=patient.id,
        medication_name="sertraline",
        dosage="50 mg",
        quantity=30,
        refills_remaining=0,  # No refills left
        prescriber="Dr. Chen",
        pharmacy="CVS Pharmacy Main St"
    )
    db_session.add(prescription_no_refills)
    db_session.commit()
    
    refill_service = RefillService(db_session)
    
    request = RefillRequest(
        name="Jane Smith",
        date_of_birth="1975-01-02",
        medication="sertraline",
        dosage="50 mg",
        quantity=30,
        pharmacy="CVS Pharmacy Main St"
    )
    
    result = await refill_service.place_refill(request, "test_call_no_refills")
    
    assert result.status == RefillStatus.NO_REFILLS
    assert "no refills remaining" in result.message.lower()
    assert "dr. chen" in result.message.lower()
    assert result.refills_remaining == 0


@pytest.mark.asyncio
async def test_multiple_refills_decrement(db_session):
    """Test that refills are properly decremented with multiple requests."""
    refill_service = RefillService(db_session)
    
    # First refill
    request1 = RefillRequest(
        name="Jane Smith",
        date_of_birth="1975-01-02",
        medication="atorvastatin",
        dosage="20 mg",
        quantity=30,
        pharmacy="CVS Pharmacy Main St"
    )
    
    result1 = await refill_service.place_refill(request1, "test_call_first")
    assert result1.status == RefillStatus.PLACED
    assert result1.refills_remaining == 1
    
    # Second refill
    request2 = RefillRequest(
        name="Jane Smith",
        date_of_birth="1975-01-02",
        medication="atorvastatin",
        dosage="20 mg",
        quantity=30,
        pharmacy="CVS Pharmacy Main St"
    )
    
    result2 = await refill_service.place_refill(request2, "test_call_second")
    assert result2.status == RefillStatus.PLACED
    assert result2.refills_remaining == 0
    
    # Third refill should fail
    request3 = RefillRequest(
        name="Jane Smith",
        date_of_birth="1975-01-02",
        medication="atorvastatin",
        dosage="20 mg",
        quantity=30,
        pharmacy="CVS Pharmacy Main St"
    )
    
    result3 = await refill_service.place_refill(request3, "test_call_third")
    assert result3.status == RefillStatus.NO_REFILLS


@pytest.mark.asyncio
async def test_eta_calculation(db_session):
    """Test ETA calculation logic."""
    refill_service = RefillService(db_session)
    
    # Test different pharmacy types
    pharmacies = [
        "CVS Pharmacy Main St",
        "Walgreens Downtown", 
        "Rite Aid Plaza"
    ]
    
    for pharmacy in pharmacies:
        request = RefillRequest(
            name="Jane Smith",
            date_of_birth="1975-01-02",
            medication="atorvastatin",
            dosage="20 mg",
            quantity=30,
            pharmacy=pharmacy
        )
        
        # Create new prescription for each test
        patient = db_session.query(Patient).first()
        new_prescription = Prescription(
            patient_id=patient.id,
            medication_name="test_med",
            dosage="10 mg",
            quantity=30,
            refills_remaining=1,
            prescriber="Dr. Test",
            pharmacy=pharmacy
        )
        db_session.add(new_prescription)
        db_session.commit()
        
        request.medication = "test_med"
        request.dosage = "10 mg"
        
        result = await refill_service.place_refill(request, f"test_call_{pharmacy}")
        
        assert result.status == RefillStatus.PLACED
        assert result.eta_minutes is not None
        assert 15 <= result.eta_minutes <= 90  # Should be in reasonable range


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
