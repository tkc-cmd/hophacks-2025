"""PHI (Protected Health Information) protection utilities."""

import re
from typing import Optional, Dict, Any
import json
from datetime import datetime


def mask_phone_number(phone: str) -> str:
    """Mask phone number, showing only last 4 digits."""
    if not phone:
        return "****"
    
    # Remove non-digits
    digits = re.sub(r'\D', '', phone)
    
    if len(digits) >= 4:
        return "****" + digits[-4:]
    else:
        return "****"


def mask_date_of_birth(dob: str) -> str:
    """Mask date of birth, showing only month and day."""
    if not dob:
        return "**/**"
    
    try:
        # Parse date in YYYY-MM-DD format
        date_obj = datetime.strptime(dob, "%Y-%m-%d")
        return f"**/{date_obj.month:02d}/{date_obj.day:02d}"
    except ValueError:
        return "**/**"


def mask_name(name: str) -> str:
    """Mask name, showing only first letter of first and last name."""
    if not name:
        return "****"
    
    parts = name.split()
    if len(parts) == 1:
        return parts[0][0] + "****"
    elif len(parts) >= 2:
        return parts[0][0] + "**** " + parts[-1][0] + "****"
    else:
        return "****"


def redact_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive data from a dictionary."""
    redacted = data.copy()
    
    # Common PHI field patterns to redact
    phi_patterns = {
        'phone': mask_phone_number,
        'phone_number': mask_phone_number,
        'dob': mask_date_of_birth,
        'date_of_birth': mask_date_of_birth,
        'birth_date': mask_date_of_birth,
        'name': mask_name,
        'full_name': mask_name,
        'patient_name': mask_name,
        'first_name': lambda x: x[0] + "****" if x else "****",
        'last_name': lambda x: x[0] + "****" if x else "****"
    }
    
    for key, value in redacted.items():
        if isinstance(value, str):
            key_lower = key.lower()
            for pattern, mask_func in phi_patterns.items():
                if pattern in key_lower:
                    redacted[key] = mask_func(value)
                    break
            else:
                # Check for SSN pattern
                if re.match(r'\d{3}-\d{2}-\d{4}', value):
                    redacted[key] = "***-**-" + value[-4:]
                # Check for credit card pattern
                elif re.match(r'\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}', value):
                    redacted[key] = "****-****-****-" + value[-4:]
    
    return redacted


def sanitize_log_message(message: str) -> str:
    """Sanitize log message to remove potential PHI."""
    # Remove potential phone numbers
    message = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '***-***-****', message)
    
    # Remove potential SSNs
    message = re.sub(r'\b\d{3}[-.]?\d{2}[-.]?\d{4}\b', '***-**-****', message)
    
    # Remove potential dates (basic pattern)
    message = re.sub(r'\b\d{1,2}/\d{1,2}/\d{4}\b', '**/**/****', message)
    message = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', '****-**-**', message)
    
    # Remove potential email addresses
    message = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '****@****.***', message)
    
    return message


def create_audit_log_entry(
    event_type: str,
    call_session_id: Optional[str] = None,
    event_data: Optional[Dict[str, Any]] = None,
    phone_number: Optional[str] = None,
    patient_dob: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, Any]:
    """Create a properly redacted audit log entry."""
    
    log_entry = {
        "event_type": event_type,
        "call_session_id": call_session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "success": success
    }
    
    # Redact and add PHI fields
    if phone_number:
        log_entry["phone_number_masked"] = mask_phone_number(phone_number)
    
    if patient_dob:
        log_entry["patient_dob_masked"] = mask_date_of_birth(patient_dob)
    
    # Redact event data
    if event_data:
        log_entry["event_data"] = json.dumps(redact_sensitive_data(event_data))
    
    # Add error information if present
    if error_message:
        log_entry["error_message"] = sanitize_log_message(error_message)
    
    # Add request metadata (for web requests)
    if ip_address:
        log_entry["ip_address"] = ip_address
    
    if user_agent:
        log_entry["user_agent"] = user_agent[:100]  # Truncate long user agents
    
    return log_entry


class PHIGuardMiddleware:
    """Middleware to protect PHI in logs and responses."""
    
    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
    
    def sanitize_request_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize request data before logging."""
        if self.debug_mode:
            return data  # Don't sanitize in debug mode
        
        return redact_sensitive_data(data)
    
    def sanitize_response_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize response data before logging."""
        if self.debug_mode:
            return data
        
        return redact_sensitive_data(data)
    
    def should_log_audio(self) -> bool:
        """Determine if raw audio should be logged."""
        return self.debug_mode
    
    def create_session_log(
        self, 
        call_sid: str, 
        action: str, 
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a session-related log entry."""
        return create_audit_log_entry(
            event_type=f"session_{action}",
            call_session_id=call_sid,
            event_data=details or {}
        )
