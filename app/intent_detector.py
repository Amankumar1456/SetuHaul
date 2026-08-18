"""
Intent Detection Module for SetuHaul
Classifies driver exceptions and determines required follow-up data collection.

Detects exception types:
1. MECHANICAL_FAILURE: Breakdown, tyre damage, engine issues
2. DRIVER_SICKNESS: Health issue, fatigue, emergency
3. TRAFFIC_CONGESTION: Traffic, congestion, accident-related delay
4. POLICE_CHECKPOINT: Police stop, inspection, checkpost
5. FACILITY_BLOCKED: Facility full, closed, unavailable
"""

from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ExceptionType(Enum):
    """Supported exception types."""
    MECHANICAL_FAILURE = "MECHANICAL_FAILURE"
    DRIVER_SICKNESS = "DRIVER_SICKNESS"
    TRAFFIC_CONGESTION = "TRAFFIC_CONGESTION"
    POLICE_CHECKPOINT = "POLICE_CHECKPOINT"
    FACILITY_BLOCKED = "FACILITY_BLOCKED"
    GENERIC_DELAY = "GENERIC_DELAY"


@dataclass
class ExceptionContext:
    """Context extracted from a driver message."""
    exception_type: ExceptionType
    confidence: float  # 0.0 to 1.0
    aspects_collected: dict  # {aspect_name: value}
    aspects_needed: list[str]  # Which aspects still need collection
    follow_up_questions: list[str]  # Questions to ask the driver
    reasoning: str  # Why we classified this way


class IntentDetector:
    """
    Detects exception types from driver messages.
    Maintains state of collected aspects across conversation turns.
    """
    
    # Exception type keywords for classification
    KEYWORDS = {
        ExceptionType.MECHANICAL_FAILURE: [
            "breakdown", "broke", "broken", "tyre", "tire", "puncture",
            "engine", "damage", "damaged", "repair", "mechanical", "stuck",
            "malfunction", "fail", "failed", "issue", "problem", "overheating"
        ],
        ExceptionType.DRIVER_SICKNESS: [
            "sick", "sickness", "unwell", "ill", "health", "fever", "headache",
            "fatigue", "tired", "sick leave", "medical", "hospital", "doctor",
            "emergency", "accident", "injury", "hurt", "pain", "dizzy", "faint"
        ],
        ExceptionType.TRAFFIC_CONGESTION: [
            "traffic", "congestion", "congested", "jam", "blocked", "congestion",
            "accident", "delay", "slow", "crawling", "bumper", "queue", "stuck"
        ],
        ExceptionType.POLICE_CHECKPOINT: [
            "police", "checkpoint", "checkpost", "stop", "stopped", "officer",
            "inspection", "check", "patrol", "traffic", "fine", "violation"
        ],
        ExceptionType.FACILITY_BLOCKED: [
            "full", "capacity", "closed", "block", "blocked", "available",
            "no slots", "warehouse", "facility", "gate", "dock", "unable",
            "cannot", "can't"
        ],
    }
    
    # Aspects needed per exception type
    ASPECTS_REQUIRED = {
        ExceptionType.MECHANICAL_FAILURE: [
            "repair_duration",  # How long will repair take?
            "current_location"  # Where is driver now?
        ],
        ExceptionType.DRIVER_SICKNESS: [
            "current_warehouse",  # Which warehouse is driver at?
            "severity"  # How serious is the illness?
        ],
        ExceptionType.TRAFFIC_CONGESTION: [
            "current_location",  # Where is driver stuck?
            "estimated_delay"  # How much delay estimated?
        ],
        ExceptionType.POLICE_CHECKPOINT: [
            "current_location",  # Current location
            "estimated_delay"  # Estimated delay
        ],
        ExceptionType.FACILITY_BLOCKED: [
            "destination_facility"  # Which facility?
        ],
        ExceptionType.GENERIC_DELAY: [
            "new_eta"  # Updated ETA?
        ],
    }
    
    # Follow-up questions per exception type
    FOLLOW_UP_QUESTIONS = {
        ExceptionType.MECHANICAL_FAILURE: [
            "How long do you expect the repair to take? (e.g., 1 hour, 2 hours)",
            "What is your current location or nearest landmark?",
            "Once repaired, what's your estimated arrival time at the warehouse?"
        ],
        ExceptionType.DRIVER_SICKNESS: [
            "Which warehouse are you currently at?",
            "How serious is the issue? Can you reach the nearest facility?",
            "Do you need us to arrange a replacement driver?"
        ],
        ExceptionType.TRAFFIC_CONGESTION: [
            "What is your current location?",
            "How much delay are you expecting? (e.g., 30 mins, 1 hour)",
            "What's your revised ETA at the destination warehouse?"
        ],
        ExceptionType.POLICE_CHECKPOINT: [
            "What is your current location?",
            "How long do you expect to be delayed?",
            "Can you proceed after the checkpoint or are there other issues?"
        ],
        ExceptionType.FACILITY_BLOCKED: [
            "Which warehouse are you headed to?",
            "Can we rebook you for a later slot?"
        ],
        ExceptionType.GENERIC_DELAY: [
            "What is your revised ETA?",
            "Can you describe why you're delayed?"
        ],
    }
    
    def __init__(self):
        """Initialize the detector."""
        self.conversation_state = {}
    
    def detect_exception_type(
        self,
        message: str,
        conversation_id: str = None
    ) -> ExceptionContext:
        """
        Detect exception type from driver message.
        
        Returns ExceptionContext with:
        - Detected exception type
        - Confidence score
        - Aspects already collected
        - Aspects still needed
        - Follow-up questions to ask
        """
        
        # Normalize message for keyword matching
        normalized = message.lower()
        
        # Score each exception type based on keyword matches
        scores = {}
        for exc_type, keywords in self.KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in normalized)
            score = matches / len(keywords) if matches > 0 else 0
            scores[exc_type] = score
        
        # Find the best match
        detected_type = max(scores, key=scores.get)
        confidence = scores[detected_type]
        
        # If confidence too low, mark as GENERIC_DELAY
        if confidence < 0.15:
            detected_type = ExceptionType.GENERIC_DELAY
            confidence = 0.5
        
        # Get aspects needed and collected so far
        aspects_needed = self.ASPECTS_REQUIRED.get(detected_type, [])
        aspects_collected = self._get_collected_aspects(conversation_id, detected_type)
        aspects_still_needed = [a for a in aspects_needed if a not in aspects_collected]
        
        # Generate follow-up questions for missing aspects
        follow_up_qs = self._generate_follow_up_questions(
            detected_type,
            aspects_still_needed
        )
        
        # Store in conversation state
        if conversation_id:
            self.conversation_state[conversation_id] = {
                "exception_type": detected_type,
                "aspects_collected": aspects_collected,
                "questions_asked": follow_up_qs
            }
        
        reasoning = self._build_reasoning(detected_type, confidence, keywords)
        
        return ExceptionContext(
            exception_type=detected_type,
            confidence=confidence,
            aspects_collected=aspects_collected,
            aspects_needed=aspects_still_needed,
            follow_up_questions=follow_up_qs,
            reasoning=reasoning
        )
    
    def _get_collected_aspects(
        self,
        conversation_id: str,
        exception_type: ExceptionType
    ) -> dict:
        """Get aspects already collected in this conversation."""
        if not conversation_id or conversation_id not in self.conversation_state:
            return {}
        
        return self.conversation_state[conversation_id].get("aspects_collected", {})
    
    def _generate_follow_up_questions(
        self,
        exception_type: ExceptionType,
        missing_aspects: list[str]
    ) -> list[str]:
        """Generate follow-up questions for missing aspects."""
        if not missing_aspects:
            return []
        
        all_questions = self.FOLLOW_UP_QUESTIONS.get(exception_type, [])
        
        # Return questions proportional to missing aspects
        num_questions = min(len(all_questions), len(missing_aspects) + 1)
        return all_questions[:num_questions]
    
    def _build_reasoning(
        self,
        exc_type: ExceptionType,
        confidence: float,
        keywords: list[str]
    ) -> str:
        """Build human-readable reasoning for the classification."""
        if exc_type == ExceptionType.MECHANICAL_FAILURE:
            return "Detected mechanical issue. Needs: repair duration + current location."
        elif exc_type == ExceptionType.DRIVER_SICKNESS:
            return "Driver health issue detected. Needs: warehouse location + replacement assessment."
        elif exc_type == ExceptionType.TRAFFIC_CONGESTION:
            return "Traffic delay detected. Needs: current location + revised ETA."
        elif exc_type == ExceptionType.POLICE_CHECKPOINT:
            return "Police checkpoint delay. Needs: location + estimated duration."
        elif exc_type == ExceptionType.FACILITY_BLOCKED:
            return "Facility issue detected. Needs: destination warehouse + rebooking options."
        else:
            return "Generic delay. Needs: revised ETA + reason."
    
    def record_aspect(
        self,
        conversation_id: str,
        aspect_name: str,
        aspect_value: str
    ) -> None:
        """Record a collected aspect for the conversation."""
        if conversation_id not in self.conversation_state:
            self.conversation_state[conversation_id] = {
                "exception_type": None,
                "aspects_collected": {},
                "questions_asked": []
            }
        
        self.conversation_state[conversation_id]["aspects_collected"][aspect_name] = aspect_value
    
    def get_conversation_state(self, conversation_id: str) -> dict:
        """Get the current state of a conversation."""
        return self.conversation_state.get(conversation_id, {})
    
    def clear_conversation(self, conversation_id: str) -> None:
        """Clear conversation state when done."""
        if conversation_id in self.conversation_state:
            del self.conversation_state[conversation_id]


# Singleton instance for use throughout the app
_detector = None

def get_detector() -> IntentDetector:
    """Get or create the detector singleton."""
    global _detector
    if _detector is None:
        _detector = IntentDetector()
    return _detector
