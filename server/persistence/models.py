"""SQLAlchemy models for the pharmacy voice agent."""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class CallSession(Base):
    """Track active phone call sessions."""
    __tablename__ = "call_sessions"
    
    id = Column(String, primary_key=True)  # Twilio CallSid
    phone_number = Column(String, nullable=False)
    start_time = Column(DateTime, default=func.now())
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default="active")  # active, completed, failed
    identity_verified = Column(Boolean, default=False)
    patient_name = Column(String, nullable=True)
    patient_dob = Column(String, nullable=True)  # Stored as YYYY-MM-DD string
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Patient(Base):
    """Mock patient data for testing."""
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String, nullable=False)
    date_of_birth = Column(String, nullable=False)  # YYYY-MM-DD
    phone_number = Column(String, nullable=True)
    pharmacy_preference = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    prescriptions = relationship("Prescription", back_populates="patient")
    refill_events = relationship("RefillEvent", back_populates="patient")


class Prescription(Base):
    """Mock prescription data."""
    __tablename__ = "prescriptions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    medication_name = Column(String, nullable=False)
    dosage = Column(String, nullable=False)  # e.g., "20 mg"
    quantity = Column(Integer, nullable=False)
    refills_remaining = Column(Integer, default=0)
    prescriber = Column(String, nullable=False)
    pharmacy = Column(String, nullable=True)
    date_prescribed = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    patient = relationship("Patient", back_populates="prescriptions")
    refill_events = relationship("RefillEvent", back_populates="prescription")


class RefillEvent(Base):
    """Track refill requests and their status."""
    __tablename__ = "refill_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_session_id = Column(String, ForeignKey("call_sessions.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=True)
    medication_name = Column(String, nullable=False)
    dosage = Column(String, nullable=False)
    quantity_requested = Column(Integer, nullable=False)
    pharmacy = Column(String, nullable=False)
    status = Column(String, nullable=False)  # placed, no_refills, not_found, needs_provider
    eta_minutes = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    patient = relationship("Patient", back_populates="refill_events")
    prescription = relationship("Prescription", back_populates="refill_events")


class InteractionCheck(Base):
    """Track drug interaction checks."""
    __tablename__ = "interaction_checks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_session_id = Column(String, ForeignKey("call_sessions.id"), nullable=False)
    medications = Column(Text, nullable=False)  # JSON string of medication list
    conditions = Column(Text, nullable=True)  # JSON string of conditions
    alerts_found = Column(Text, nullable=True)  # JSON string of alerts
    severity_level = Column(String, nullable=True)  # high, medium, low
    created_at = Column(DateTime, default=func.now())


class AuditLog(Base):
    """Audit log for PHI access and system events."""
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_session_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)  # identity_verify, refill_request, interaction_check, etc.
    event_data = Column(Text, nullable=True)  # Redacted JSON data
    phone_number_masked = Column(String, nullable=True)  # Last 4 digits only
    patient_dob_masked = Column(String, nullable=True)  # Month/day only
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


class TtsFile(Base):
    """Track generated TTS files for cleanup."""
    __tablename__ = "tts_files"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_session_id = Column(String, ForeignKey("call_sessions.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    text_content = Column(Text, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    played = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True)  # For cleanup
