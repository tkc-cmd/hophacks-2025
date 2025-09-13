"""Gemini LLM client with tool functions for pharmacy operations."""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from server.config import settings
from server.domain.refill.service import RefillService, RefillRequest
from server.domain.drug_info.service import MockDrugInfoService
from server.domain.sessions.store import CallSessionData

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from the LLM."""
    text: str
    tool_calls: List[Dict[str, Any]]
    confidence: float = 1.0
    finish_reason: str = "stop"
    usage: Optional[Dict[str, int]] = None


class PharmacyAssistantLLM:
    """Gemini-based pharmacy assistant with tool calling."""
    
    def __init__(self):
        # Configure Gemini
        genai.configure(api_key=settings.google_api_key)
        
        self.model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            tools=[
                self._get_refill_tool_spec(),
                self._get_interaction_check_tool_spec(),
                self._get_administration_guide_tool_spec()
            ],
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        )
        
        # Initialize domain services
        self.drug_info_service = MockDrugInfoService()
        
        # System prompt
        self.system_prompt = self._load_system_prompt()
        
        # Tool dispatch map
        self.tool_dispatch = {
            "place_refill": self._handle_refill_request,
            "check_interactions": self._handle_interaction_check,
            "get_administration_guide": self._handle_administration_guide
        }
    
    def _load_system_prompt(self) -> str:
        """Load the system prompt for the pharmacy assistant."""
        return """You are an automated pharmacy voice assistant for refills, interaction checks, and administration guidance. You are not a doctor or pharmacist.

IMPORTANT SAFETY DISCLAIMER: Start your very first response with: "I'm an automated pharmacy assistant and can't provide medical diagnoses. In emergencies call your local emergency number."

CORE PRINCIPLES:
- Be concise, polite, and proactive about safety
- Keep responses under 120 words per turn
- Use simple, clear language
- Always verify identity before discussing PHI (ask for full name and date of birth)
- Decline requests for diagnosis, new prescriptions, or controlled substances
- Route complex medical questions to a licensed professional

IDENTITY VERIFICATION:
Before discussing any prescription information, you must verify the caller's identity by asking for:
1. Full name (first and last)
2. Date of birth (month, day, and year)

SERVICES YOU PROVIDE:
1. PRESCRIPTION REFILLS: Gather medication name, dosage, quantity, pharmacy location
2. DRUG INTERACTIONS: Check current medications and conditions for safety alerts
3. ADMINISTRATION GUIDANCE: Provide dosing instructions and safety information

SERVICES YOU DO NOT PROVIDE:
- Medical diagnoses
- New prescriptions
- Controlled substance information
- Medical advice beyond basic administration guidance
- Emergency medical assistance

EMERGENCY PROTOCOL:
If someone mentions emergency symptoms, chest pain, difficulty breathing, severe allergic reactions, or suicidal thoughts, immediately instruct them to call 911 or their local emergency number.

CONVERSATION FLOW:
1. Greet with disclaimer (first interaction only)
2. Ask how you can help
3. Verify identity if discussing PHI
4. Use appropriate tools to fulfill requests
5. Provide clear, actionable information
6. Offer to help with anything else

Remember: You're a helpful assistant, but safety comes first. When in doubt, refer to a pharmacist or healthcare provider."""
    
    async def generate_response(
        self, 
        user_message: str, 
        session: CallSessionData,
        refill_service: Optional[RefillService] = None
    ) -> LLMResponse:
        """Generate a response to user input."""
        
        try:
            # Build conversation history
            messages = self._build_conversation_history(session, user_message)
            
            # Start chat with system prompt and history
            chat = self.model.start_chat(history=messages[:-1])  # Exclude the current message
            
            # Generate response
            response = await self._generate_with_retry(chat, messages[-1]['parts'][0])
            
            # Process response
            return await self._process_response(response, session, refill_service)
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return LLMResponse(
                text="I apologize, but I'm experiencing technical difficulties. Please try again or call your pharmacy directly.",
                tool_calls=[],
                finish_reason="error"
            )
    
    def _build_conversation_history(self, session: CallSessionData, current_message: str) -> List[Dict[str, Any]]:
        """Build conversation history for Gemini."""
        messages = []
        
        # Add system prompt as first user message (Gemini doesn't have system role)
        messages.append({
            "role": "user",
            "parts": [self.system_prompt]
        })
        messages.append({
            "role": "model",
            "parts": ["I understand. I'm ready to assist with pharmacy services while following all safety protocols."]
        })
        
        # Add conversation history
        recent_history = session.get_recent_history(max_turns=settings.max_conversation_history)
        
        for turn in recent_history:
            if turn.speaker == "user":
                messages.append({
                    "role": "user",
                    "parts": [turn.text]
                })
            elif turn.speaker == "assistant":
                messages.append({
                    "role": "model",
                    "parts": [turn.text]
                })
        
        # Add current message
        messages.append({
            "role": "user",
            "parts": [current_message]
        })
        
        return messages
    
    async def _generate_with_retry(self, chat, message: str, max_retries: int = 3):
        """Generate response with retry logic."""
        for attempt in range(max_retries):
            try:
                response = chat.send_message(message)
                return response
            except Exception as e:
                logger.warning(f"LLM generation attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1)
    
    async def _process_response(
        self, 
        response, 
        session: CallSessionData,
        refill_service: Optional[RefillService]
    ) -> LLMResponse:
        """Process the raw LLM response."""
        
        response_text = ""
        tool_calls = []
        
        for part in response.parts:
            if part.text:
                response_text += part.text
            elif part.function_call:
                # Handle tool call
                tool_result = await self._execute_tool_call(
                    part.function_call, 
                    session, 
                    refill_service
                )
                tool_calls.append(tool_result)
        
        # If we executed tool calls, we might need to incorporate their results
        if tool_calls:
            # Add tool results to response text if not already included
            for tool_call in tool_calls:
                if tool_call.get('result') and tool_call['result'] not in response_text:
                    response_text += f" {tool_call['result']}"
        
        return LLMResponse(
            text=response_text.strip(),
            tool_calls=tool_calls,
            finish_reason=response.candidates[0].finish_reason if response.candidates else "stop"
        )
    
    async def _execute_tool_call(
        self, 
        function_call, 
        session: CallSessionData,
        refill_service: Optional[RefillService]
    ) -> Dict[str, Any]:
        """Execute a tool function call."""
        
        function_name = function_call.name
        args = dict(function_call.args)
        
        logger.info(f"Executing tool call: {function_name} with args: {args}")
        
        try:
            if function_name in self.tool_dispatch:
                handler = self.tool_dispatch[function_name]
                
                # Add session and refill_service to args if needed
                if function_name == "place_refill" and refill_service:
                    result = await handler(args, session.call_sid, refill_service)
                else:
                    result = await handler(args)
                
                return {
                    "function": function_name,
                    "args": args,
                    "result": result,
                    "success": True
                }
            else:
                logger.error(f"Unknown tool function: {function_name}")
                return {
                    "function": function_name,
                    "args": args,
                    "result": "Error: Unknown function",
                    "success": False
                }
                
        except Exception as e:
            logger.error(f"Error executing tool {function_name}: {e}")
            return {
                "function": function_name,
                "args": args,
                "result": f"Error: {str(e)}",
                "success": False
            }
    
    # Tool specifications
    def _get_refill_tool_spec(self) -> Dict[str, Any]:
        """Get the refill tool specification."""
        return {
            "function_declarations": [{
                "name": "place_refill",
                "description": "Place a prescription refill request for a verified patient",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Patient's full name"
                        },
                        "dob": {
                            "type": "string",
                            "description": "Patient's date of birth in YYYY-MM-DD format"
                        },
                        "med": {
                            "type": "string",
                            "description": "Medication name"
                        },
                        "dose": {
                            "type": "string",
                            "description": "Medication dosage (e.g., '20 mg')"
                        },
                        "qty": {
                            "type": "integer",
                            "description": "Quantity requested"
                        },
                        "pharmacy": {
                            "type": "string",
                            "description": "Pharmacy name and location"
                        }
                    },
                    "required": ["name", "dob", "med", "dose", "qty", "pharmacy"]
                }
            }]
        }
    
    def _get_interaction_check_tool_spec(self) -> Dict[str, Any]:
        """Get the interaction check tool specification."""
        return {
            "function_declarations": [{
                "name": "check_interactions",
                "description": "Check for drug interactions and contraindications",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meds": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of current medications"
                        },
                        "conditions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of medical conditions (optional)"
                        }
                    },
                    "required": ["meds"]
                }
            }]
        }
    
    def _get_administration_guide_tool_spec(self) -> Dict[str, Any]:
        """Get the administration guide tool specification."""
        return {
            "function_declarations": [{
                "name": "get_administration_guide",
                "description": "Get administration instructions and safety information for a medication",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "med": {
                            "type": "string",
                            "description": "Medication name"
                        }
                    },
                    "required": ["med"]
                }
            }]
        }
    
    # Tool handlers
    async def _handle_refill_request(
        self, 
        args: Dict[str, Any], 
        call_sid: str, 
        refill_service: RefillService
    ) -> str:
        """Handle prescription refill request."""
        
        try:
            request = RefillRequest(
                name=args["name"],
                date_of_birth=args["dob"],
                medication=args["med"],
                dosage=args["dose"],
                quantity=args["qty"],
                pharmacy=args["pharmacy"]
            )
            
            result = await refill_service.place_refill(request, call_sid)
            return result.message
            
        except Exception as e:
            logger.error(f"Error handling refill request: {e}")
            return "I'm sorry, there was an error processing your refill request. Please try again."
    
    async def _handle_interaction_check(self, args: Dict[str, Any]) -> str:
        """Handle drug interaction check."""
        
        try:
            medications = args["meds"]
            conditions = args.get("conditions", [])
            
            result = await self.drug_info_service.check_interactions(medications, conditions)
            
            if not result.alerts:
                return "I didn't find any major interactions between those medications."
            
            # Format alerts
            response = f"I found {len(result.alerts)} potential interaction(s):\n"
            
            for alert in result.alerts:
                severity_text = "⚠️ HIGH PRIORITY" if alert.severity == "high" else "⚠️ CAUTION"
                response += f"\n{severity_text}: {alert.summary}\n{alert.guidance}\n"
            
            response += "\nPlease discuss these with your pharmacist or prescriber."
            return response
            
        except Exception as e:
            logger.error(f"Error checking interactions: {e}")
            return "I'm sorry, I couldn't check for interactions right now. Please consult your pharmacist."
    
    async def _handle_administration_guide(self, args: Dict[str, Any]) -> str:
        """Handle administration guide request."""
        
        try:
            medication = args["med"]
            
            guide = await self.drug_info_service.get_administration_guide(medication)
            
            if not guide:
                return f"I don't have specific administration information for {medication}. Please consult your pharmacist or the medication label."
            
            response = f"For {guide.medication}:\n\n"
            response += f"Instructions: {guide.instructions}\n\n"
            
            if guide.common_side_effects:
                response += f"Common side effects: {', '.join(guide.common_side_effects)}\n\n"
            
            response += f"Seek help if: {guide.when_to_seek_help}\n"
            
            if guide.food_interactions:
                response += f"\nFood guidance: {guide.food_interactions}"
            
            if guide.timing_guidance:
                response += f"\nTiming: {guide.timing_guidance}"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting administration guide: {e}")
            return "I'm sorry, I couldn't retrieve administration information right now. Please check with your pharmacist."


# Global LLM client instance
pharmacy_llm = PharmacyAssistantLLM()
