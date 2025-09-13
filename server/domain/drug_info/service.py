"""Drug information service interface and implementation."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum


class AlertSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DrugAlert(BaseModel):
    severity: AlertSeverity
    summary: str
    guidance: str
    affected_medications: List[str]


class AdministrationGuide(BaseModel):
    medication: str
    instructions: str
    common_side_effects: List[str]
    when_to_seek_help: str
    food_interactions: Optional[str] = None
    timing_guidance: Optional[str] = None


class InteractionCheckResult(BaseModel):
    alerts: List[DrugAlert]
    total_interactions: int
    highest_severity: Optional[AlertSeverity] = None


class DrugInfoService(ABC):
    """Abstract interface for drug information services."""
    
    @abstractmethod
    async def check_interactions(
        self, 
        medications: List[str], 
        conditions: Optional[List[str]] = None
    ) -> InteractionCheckResult:
        """Check for drug-drug and drug-condition interactions."""
        pass
    
    @abstractmethod
    async def get_administration_guide(self, medication: str) -> Optional[AdministrationGuide]:
        """Get administration instructions and safety information."""
        pass
    
    @abstractmethod
    async def search_medication(self, query: str) -> List[str]:
        """Search for medications by name (fuzzy matching)."""
        pass


class MockDrugInfoService(DrugInfoService):
    """Mock implementation with hardcoded drug data for testing."""
    
    def __init__(self):
        self._load_mock_data()
    
    def _load_mock_data(self):
        """Load mock drug interaction rules and administration guides."""
        
        # Drug interaction rules (simplified)
        self.interaction_rules = [
            {
                "drugs": ["sertraline", "fluoxetine", "paroxetine"],  # SSRIs
                "contraindicated_with": ["phenelzine", "tranylcypromine"],  # MAOIs
                "severity": AlertSeverity.HIGH,
                "summary": "SSRI-MAOI interaction risk",
                "guidance": "Do not combine SSRIs with MAOIs. Risk of serotonin syndrome. Consult prescriber immediately."
            },
            {
                "drugs": ["ibuprofen", "naproxen", "diclofenac"],  # NSAIDs
                "contraindicated_with": ["lisinopril", "enalapril", "losartan"],  # ACE inhibitors/ARBs
                "severity": AlertSeverity.MEDIUM,
                "summary": "NSAID-ACE inhibitor interaction",
                "guidance": "NSAIDs may reduce effectiveness of blood pressure medications and increase kidney risk. Monitor blood pressure and kidney function."
            },
            {
                "drugs": ["atorvastatin", "simvastatin", "lovastatin"],  # Statins
                "contraindicated_with": ["clarithromycin", "erythromycin", "ketoconazole"],  # CYP3A4 inhibitors
                "severity": AlertSeverity.MEDIUM,
                "summary": "Statin-CYP3A4 inhibitor interaction",
                "guidance": "Strong CYP3A4 inhibitors may increase statin levels, raising risk of muscle problems. Consider dose adjustment."
            },
            {
                "drugs": ["metformin"],
                "conditions": ["contrast_dye", "kidney_disease"],
                "severity": AlertSeverity.HIGH,
                "summary": "Metformin contraindication warning",
                "guidance": "Stop metformin before contrast procedures or if kidney function is impaired. Risk of lactic acidosis."
            }
        ]
        
        # Administration guides
        self.admin_guides = {
            "amoxicillin": AdministrationGuide(
                medication="amoxicillin",
                instructions="Take with or without food. Complete the full course even if feeling better.",
                common_side_effects=["nausea", "diarrhea", "stomach upset", "rash"],
                when_to_seek_help="Severe rash, difficulty breathing, severe diarrhea, or signs of allergic reaction",
                timing_guidance="Take every 8 hours at evenly spaced intervals"
            ),
            "atorvastatin": AdministrationGuide(
                medication="atorvastatin",
                instructions="Take once daily, preferably in the evening. Can be taken with or without food.",
                common_side_effects=["muscle aches", "headache", "nausea", "constipation"],
                when_to_seek_help="Unexplained muscle pain, weakness, or dark urine. Signs of liver problems.",
                food_interactions="Avoid grapefruit and grapefruit juice"
            ),
            "lisinopril": AdministrationGuide(
                medication="lisinopril",
                instructions="Take once daily at the same time each day. Can be taken with or without food.",
                common_side_effects=["dry cough", "dizziness", "headache", "fatigue"],
                when_to_seek_help="Swelling of face/lips/tongue, severe dizziness, or persistent cough",
                timing_guidance="Best taken in the morning"
            ),
            "metformin": AdministrationGuide(
                medication="metformin",
                instructions="Take with meals to reduce stomach upset. Drink plenty of fluids.",
                common_side_effects=["nausea", "diarrhea", "stomach upset", "metallic taste"],
                when_to_seek_help="Severe stomach pain, muscle pain, trouble breathing, or unusual tiredness",
                food_interactions="Take with food to minimize GI effects"
            ),
            "ibuprofen": AdministrationGuide(
                medication="ibuprofen",
                instructions="Take with food or milk to reduce stomach irritation. Use lowest effective dose.",
                common_side_effects=["stomach upset", "heartburn", "dizziness", "headache"],
                when_to_seek_help="Black stools, stomach pain, chest pain, or signs of allergic reaction",
                food_interactions="Take with food or milk"
            ),
            "sertraline": AdministrationGuide(
                medication="sertraline",
                instructions="Take once daily, preferably in the morning. Can be taken with or without food.",
                common_side_effects=["nausea", "diarrhea", "insomnia", "dizziness", "sexual side effects"],
                when_to_seek_help="Thoughts of self-harm, severe mood changes, or serotonin syndrome symptoms",
                timing_guidance="Take at the same time each day, preferably morning"
            )
        }
        
        # Medication name variations for search
        self.medication_variants = {
            "amoxicillin": ["amoxil", "trimox"],
            "atorvastatin": ["lipitor"],
            "lisinopril": ["prinivil", "zestril"],
            "metformin": ["glucophage", "fortamet"],
            "ibuprofen": ["advil", "motrin"],
            "sertraline": ["zoloft"]
        }
    
    async def check_interactions(
        self, 
        medications: List[str], 
        conditions: Optional[List[str]] = None
    ) -> InteractionCheckResult:
        """Check for interactions between medications and conditions."""
        
        alerts = []
        medications_lower = [med.lower().strip() for med in medications]
        conditions_lower = [cond.lower().strip() for cond in (conditions or [])]
        
        for rule in self.interaction_rules:
            # Check drug-drug interactions
            if "contraindicated_with" in rule:
                rule_drugs = [drug.lower() for drug in rule["drugs"]]
                contraindicated = [drug.lower() for drug in rule["contraindicated_with"]]
                
                matching_drugs = [drug for drug in medications_lower if drug in rule_drugs]
                matching_contraindicated = [drug for drug in medications_lower if drug in contraindicated]
                
                if matching_drugs and matching_contraindicated:
                    alerts.append(DrugAlert(
                        severity=rule["severity"],
                        summary=rule["summary"],
                        guidance=rule["guidance"],
                        affected_medications=matching_drugs + matching_contraindicated
                    ))
            
            # Check drug-condition interactions
            if "conditions" in rule:
                rule_drugs = [drug.lower() for drug in rule["drugs"]]
                rule_conditions = [cond.lower() for cond in rule["conditions"]]
                
                matching_drugs = [drug for drug in medications_lower if drug in rule_drugs]
                matching_conditions = [cond for cond in conditions_lower if cond in rule_conditions]
                
                if matching_drugs and matching_conditions:
                    alerts.append(DrugAlert(
                        severity=rule["severity"],
                        summary=rule["summary"],
                        guidance=rule["guidance"],
                        affected_medications=matching_drugs
                    ))
        
        # Determine highest severity
        highest_severity = None
        if alerts:
            severity_order = {AlertSeverity.HIGH: 3, AlertSeverity.MEDIUM: 2, AlertSeverity.LOW: 1}
            highest_severity = max(alerts, key=lambda x: severity_order[x.severity]).severity
        
        return InteractionCheckResult(
            alerts=alerts,
            total_interactions=len(alerts),
            highest_severity=highest_severity
        )
    
    async def get_administration_guide(self, medication: str) -> Optional[AdministrationGuide]:
        """Get administration guide for a medication."""
        med_lower = medication.lower().strip()
        
        # Direct match
        if med_lower in self.admin_guides:
            return self.admin_guides[med_lower]
        
        # Check variants
        for canonical_name, variants in self.medication_variants.items():
            if med_lower in [v.lower() for v in variants]:
                return self.admin_guides.get(canonical_name)
        
        return None
    
    async def search_medication(self, query: str) -> List[str]:
        """Search for medications by name."""
        query_lower = query.lower().strip()
        matches = []
        
        # Check all medications and their variants
        all_medications = set(self.admin_guides.keys())
        for canonical_name, variants in self.medication_variants.items():
            all_medications.update([v.lower() for v in variants])
        
        # Simple substring matching
        for med in all_medications:
            if query_lower in med.lower() or med.lower().startswith(query_lower):
                matches.append(med)
        
        return sorted(matches)[:5]  # Limit to top 5 matches
