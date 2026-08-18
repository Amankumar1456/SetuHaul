"""
Exception-Specific Handlers for SetuHaul TMS

Phase 6: Workflow handlers for specific driver exceptions with targeted
resolution logic, data collection, and escalation criteria.

Handlers:
1. MechanicalFailureHandler - Vehicle breakdown, repair time estimation, replacement
2. DriverSicknessHandler - Health evaluation, warehouse location, replacement
3. TrafficCongestionHandler - Current location, ETA revision, slot rebooking
4. PoliceCheckpointHandler - Location, estimated duration, checkpoint-specific routing
"""

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone, timedelta
from enum import Enum

# ─────────────────────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────────────────────

class ResolutionAction(str, Enum):
    """Recommended resolution actions for each handler."""
    # Mechanical
    REPAIR_ON_SITE = "REPAIR_ON_SITE"
    TOW_TO_FACILITY = "TOW_TO_FACILITY"
    VEHICLE_REPLACEMENT = "VEHICLE_REPLACEMENT"
    
    # Sickness
    DRIVER_REST_AT_WAREHOUSE = "DRIVER_REST_AT_WAREHOUSE"
    DRIVER_REPLACEMENT = "DRIVER_REPLACEMENT"
    MEDICAL_ESCALATION = "MEDICAL_ESCALATION"
    
    # Traffic
    REROUTE_DRIVER = "REROUTE_DRIVER"
    REVISE_ETA = "REVISE_ETA"
    REBOOKING_SLOT = "REBOOKING_SLOT"
    
    # Checkpoint
    CHECKPOINT_WAIT = "CHECKPOINT_WAIT"
    ALTERNATE_ROUTE = "ALTERNATE_ROUTE"
    DOCUMENT_VERIFICATION = "DOCUMENT_VERIFICATION"


@dataclass
class HandlerContext:
    """Context data passed to exception handlers."""
    driver_id: str
    shipment_id: str
    conversation_id: str
    warehouse_id: str
    exception_type: str
    initial_message: str
    current_timestamp: str
    driver_location_lat: Optional[float] = None
    driver_location_lng: Optional[float] = None


@dataclass
class HandlerResponse:
    """Response from exception handler."""
    handler_name: str
    exception_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    detected_aspects: Dict[str, Any]  # Collected data points
    recommended_actions: List[ResolutionAction]
    follow_up_questions: List[str]
    escalation_required: bool
    escalation_reason: Optional[str]
    estimated_resolution_time_min: Optional[int]
    next_steps: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# Exception Handlers
# ─────────────────────────────────────────────────────────────────────────────

class MechanicalFailureHandler:
    """
    Handler for vehicle mechanical failures and breakdowns.
    
    Aspects to collect:
    - Symptom description (engine, brake, suspension, etc)
    - Repair duration estimate
    - Current location
    - Cargo status (perishable, temperature-sensitive, fragile)
    
    Resolution options:
    1. Repair on site (if minor, quick)
    2. Tow to facility (if severe)
    3. Vehicle replacement (if critical, time-sensitive cargo)
    """
    
    def __init__(self):
        self.name = "MechanicalFailureHandler"
        self.exception_type = "MECHANICAL_FAILURE"
        self.min_repair_time = 30  # minutes
        self.max_repair_time = 240  # minutes
        self.escalation_threshold_min = 120  # escalate if repair > 2 hours
    
    def analyze(self, context: HandlerContext, conversation_state: Dict) -> HandlerResponse:
        """Analyze mechanical failure and recommend actions."""
        
        detected_aspects = {}
        follow_ups = []
        actions = []
        severity = "MEDIUM"
        escalation_required = False
        escalation_reason = None
        
        # Extract available data from conversation state
        repair_symptom = conversation_state.get("repair_symptom")
        repair_duration_estimate = conversation_state.get("repair_duration_estimate")
        cargo_type = conversation_state.get("cargo_type")
        
        # 1. Determine symptom severity
        if repair_symptom:
            detected_aspects["repair_symptom"] = repair_symptom
            severity_keywords = {
                "engine": "CRITICAL",
                "brake": "CRITICAL",
                "steering": "CRITICAL",
                "transmission": "HIGH",
                "suspension": "HIGH",
                "tire": "MEDIUM",
                "electrical": "MEDIUM",
                "cosmetic": "LOW"
            }
            for keyword, sev in severity_keywords.items():
                if keyword.lower() in repair_symptom.lower():
                    severity = sev
                    break
        else:
            follow_ups.append("What specific symptom is the vehicle experiencing? (e.g., engine, brake, suspension)")
        
        # 2. Estimate repair time
        if repair_duration_estimate:
            try:
                minutes = int(repair_duration_estimate.replace("min", "").replace("minutes", "").strip())
                detected_aspects["repair_duration_estimate_min"] = minutes
                
                if minutes > self.escalation_threshold_min:
                    escalation_required = True
                    escalation_reason = f"Estimated repair time {minutes}min exceeds threshold {self.escalation_threshold_min}min"
            except:
                follow_ups.append("How long will the repair take (estimated in minutes)?")
        else:
            follow_ups.append("How long will the repair take (estimated in minutes)?")
        
        # 3. Check cargo requirements
        if cargo_type:
            detected_aspects["cargo_type"] = cargo_type
            perishable_keywords = ["food", "dairy", "meat", "fresh", "perishable", "temperature"]
            if any(kw in cargo_type.lower() for kw in perishable_keywords):
                severity = "CRITICAL" if severity != "CRITICAL" else severity
                follow_ups.append(f"Your cargo is {cargo_type}. Current temperature if temperature-controlled?")
        else:
            follow_ups.append("What type of cargo are you carrying? (perishable, temperature-sensitive, fragile, etc)")
        
        # 4. Recommend actions based on severity and repair time
        if severity == "CRITICAL":
            actions.append(ResolutionAction.VEHICLE_REPLACEMENT)
            actions.append(ResolutionAction.TOW_TO_FACILITY)
        elif detected_aspects.get("repair_duration_estimate_min", 999) > 90:
            actions.append(ResolutionAction.TOW_TO_FACILITY)
            actions.append(ResolutionAction.VEHICLE_REPLACEMENT)
        else:
            actions.append(ResolutionAction.REPAIR_ON_SITE)
            actions.append(ResolutionAction.TOW_TO_FACILITY)
        
        # 5. Build next steps
        next_steps = []
        if severity == "CRITICAL":
            next_steps.append("URGENT: Initiate vehicle replacement immediately")
            next_steps.append("Arrange emergency tow if cargo is perishable")
            next_steps.append("Notify destination warehouse of cargo reroute")
        else:
            next_steps.append("Await repair estimate from mechanic")
            next_steps.append("Monitor cargo conditions during repair")
            next_steps.append("Update ETA once repair timeline confirmed")
        
        return HandlerResponse(
            handler_name=self.name,
            exception_type=self.exception_type,
            severity=severity,
            detected_aspects=detected_aspects,
            recommended_actions=actions,
            follow_up_questions=follow_ups,
            escalation_required=escalation_required,
            escalation_reason=escalation_reason,
            estimated_resolution_time_min=detected_aspects.get("repair_duration_estimate_min"),
            next_steps=next_steps
        )


class DriverSicknessHandler:
    """
    Handler for driver sickness and health emergencies.
    
    Aspects to collect:
    - Symptom description (fever, pain, nausea, etc)
    - Severity level (mild, moderate, severe, emergency)
    - Current location (in vehicle or at warehouse)
    - Nearest warehouse
    
    Resolution options:
    1. Rest at warehouse (if mild)
    2. Driver replacement (if moderate)
    3. Medical escalation (if severe/emergency)
    """
    
    def __init__(self):
        self.name = "DriverSicknessHandler"
        self.exception_type = "DRIVER_SICKNESS"
        self.emergency_keywords = ["chest pain", "severe", "emergency", "ambulance", "hospital"]
        self.urgent_keywords = ["fever", "vomiting", "dizzy", "unconscious"]
        self.mild_keywords = ["headache", "mild", "fatigue", "cold"]
    
    def analyze(self, context: HandlerContext, conversation_state: Dict) -> HandlerResponse:
        """Analyze driver sickness and recommend actions."""
        
        detected_aspects = {}
        follow_ups = []
        actions = []
        severity = "MEDIUM"
        escalation_required = False
        escalation_reason = None
        
        # Extract data from conversation
        symptom_description = conversation_state.get("symptom_description")
        symptom_severity = conversation_state.get("symptom_severity")
        current_location = conversation_state.get("current_location")  # "vehicle" or warehouse_id
        
        # 1. Classify symptom severity
        if symptom_description:
            detected_aspects["symptom_description"] = symptom_description
            symptom_lower = symptom_description.lower()
            
            # Check emergency
            if any(kw in symptom_lower for kw in self.emergency_keywords):
                severity = "CRITICAL"
                escalation_required = True
                escalation_reason = "Emergency medical condition detected"
            # Check urgent
            elif any(kw in symptom_lower for kw in self.urgent_keywords):
                severity = "HIGH"
            # Check mild
            elif any(kw in symptom_lower for kw in self.mild_keywords):
                severity = "MEDIUM"
        else:
            follow_ups.append("Can you describe your symptoms in detail?")
        
        # 2. Confirm severity level
        if symptom_severity:
            detected_aspects["symptom_severity"] = symptom_severity
            severity_map = {"mild": "LOW", "moderate": "MEDIUM", "severe": "HIGH", "emergency": "CRITICAL"}
            severity = severity_map.get(symptom_severity.lower(), severity)
            
            if symptom_severity.lower() == "emergency":
                escalation_required = True
                escalation_reason = "Driver self-reported emergency condition"
        else:
            follow_ups.append("On a scale of 1-5 (1=mild, 5=emergency), how severe is your condition?")
        
        # 3. Determine current location
        if current_location:
            detected_aspects["current_location"] = current_location
        else:
            follow_ups.append("Are you currently in your vehicle or at a warehouse? If vehicle, which road/location?")
        
        # 4. Recommend actions
        if severity == "CRITICAL":
            actions.append(ResolutionAction.MEDICAL_ESCALATION)
            actions.append(ResolutionAction.DRIVER_REPLACEMENT)
        elif severity == "HIGH":
            actions.append(ResolutionAction.DRIVER_REPLACEMENT)
            actions.append(ResolutionAction.DRIVER_REST_AT_WAREHOUSE)
        else:
            actions.append(ResolutionAction.DRIVER_REST_AT_WAREHOUSE)
            actions.append(ResolutionAction.DRIVER_REPLACEMENT)
        
        # 5. Build next steps
        next_steps = []
        if severity == "CRITICAL":
            next_steps.append("EMERGENCY: Contact local emergency services (dial 112)")
            next_steps.append("Provide driver's current location to dispatch")
            next_steps.append("Initiate replacement driver dispatch immediately")
            next_steps.append("Notify destination warehouse of delay")
        elif severity == "HIGH":
            next_steps.append("Dispatch replacement driver to current location")
            next_steps.append("Arrange rest period at nearest warehouse")
            next_steps.append("Provide medical support if available")
            next_steps.append("Update shipment ETA")
        else:
            next_steps.append("Proceed to nearest warehouse for rest")
            next_steps.append("Refresh with water and rest for 30-60 minutes")
            next_steps.append("Reassess condition before continuing journey")
        
        estimated_resolution_time = None
        if severity == "LOW":
            estimated_resolution_time = 60  # 1 hour rest
        elif severity == "MEDIUM":
            estimated_resolution_time = 120  # 2 hours (rest + replacement if needed)
        else:
            estimated_resolution_time = None  # Varies based on medical response
        
        return HandlerResponse(
            handler_name=self.name,
            exception_type=self.exception_type,
            severity=severity,
            detected_aspects=detected_aspects,
            recommended_actions=actions,
            follow_up_questions=follow_ups,
            escalation_required=escalation_required,
            escalation_reason=escalation_reason,
            estimated_resolution_time_min=estimated_resolution_time,
            next_steps=next_steps
        )


class TrafficCongestionHandler:
    """
    Handler for traffic delays and routing issues.
    
    Aspects to collect:
    - Traffic location/highway
    - Estimated delay duration
    - Current vehicle speed
    - Cargo sensitivity to delay
    
    Resolution options:
    1. Reroute driver (alternative route)
    2. Revise ETA (accept delay, update all systems)
    3. Rebooking slot (if delay too large, find new delivery window)
    """
    
    def __init__(self):
        self.name = "TrafficCongestionHandler"
        self.exception_type = "TRAFFIC_CONGESTION"
        self.critical_delay_min = 120  # escalate if delay > 2 hours
        self.rebooking_delay_min = 180  # rebooking needed if > 3 hours delay
    
    def analyze(self, context: HandlerContext, conversation_state: Dict) -> HandlerResponse:
        """Analyze traffic situation and recommend routing/timing changes."""
        
        detected_aspects = {}
        follow_ups = []
        actions = []
        severity = "MEDIUM"
        escalation_required = False
        escalation_reason = None
        
        # Extract data
        traffic_location = conversation_state.get("traffic_location")
        estimated_delay_min = conversation_state.get("estimated_delay_min")
        current_speed = conversation_state.get("current_speed")
        cargo_time_sensitive = conversation_state.get("cargo_time_sensitive")
        
        # 1. Identify traffic hotspot
        if traffic_location:
            detected_aspects["traffic_location"] = traffic_location
            # Common highways that need rerouting options
            major_routes = ["nh48", "nh44", "nh52", "mumbai", "delhi", "bangalore"]
            if any(route in traffic_location.lower() for route in major_routes):
                follow_ups.append("Would you like to consider an alternate route?")
        else:
            follow_ups.append("Which highway or road location are you currently stuck in?")
        
        # 2. Quantify delay
        if estimated_delay_min:
            try:
                delay_min = int(str(estimated_delay_min).replace("min", "").replace("minutes", "").split()[0])
                detected_aspects["estimated_delay_min"] = delay_min
                
                if delay_min > self.critical_delay_min:
                    severity = "HIGH"
                    if delay_min > self.rebooking_delay_min:
                        escalation_required = True
                        escalation_reason = f"Traffic delay {delay_min}min exceeds rebooking threshold"
                else:
                    severity = "MEDIUM"
            except:
                follow_ups.append("What's your estimated delay in minutes?")
        else:
            follow_ups.append("What's your estimated delay in minutes?")
        
        # 3. Check speed progress
        if current_speed:
            detected_aspects["current_speed_kmh"] = current_speed
        else:
            follow_ups.append("What's your current speed (km/h)? This helps estimate recovery time.")
        
        # 4. Check cargo sensitivity
        if cargo_time_sensitive:
            detected_aspects["cargo_time_sensitive"] = cargo_time_sensitive
            if cargo_time_sensitive.lower() in ["yes", "true", "perishable", "time-critical"]:
                severity = "CRITICAL" if detected_aspects.get("estimated_delay_min", 0) > 90 else "HIGH"
        else:
            follow_ups.append("Is your cargo time-sensitive or perishable?")
        
        # 5. Recommend actions
        actions.append(ResolutionAction.REROUTE_DRIVER)
        actions.append(ResolutionAction.REVISE_ETA)
        
        if detected_aspects.get("estimated_delay_min", 0) > self.rebooking_delay_min:
            actions.append(ResolutionAction.REBOOKING_SLOT)
        
        # 6. Build next steps
        next_steps = []
        if severity == "CRITICAL":
            next_steps.append("URGENT: Check alternate routes immediately")
            next_steps.append("Consider fast-track delivery or express options")
            next_steps.append("Contact destination warehouse to rebooking slot")
            next_steps.append("Assess cargo condition for perishable items")
        elif severity == "HIGH":
            next_steps.append("Evaluate alternate routes (Maps/Navigation app)")
            next_steps.append("Update ETA with warehouse and dispatch")
            next_steps.append("Prepare for potential slot rebooking")
        else:
            next_steps.append("Monitor traffic and keep dispatch updated")
            next_steps.append("Adjust ETA if congestion continues")
        
        estimated_resolution_time = detected_aspects.get("estimated_delay_min")
        
        return HandlerResponse(
            handler_name=self.name,
            exception_type=self.exception_type,
            severity=severity,
            detected_aspects=detected_aspects,
            recommended_actions=actions,
            follow_up_questions=follow_ups,
            escalation_required=escalation_required,
            escalation_reason=escalation_reason,
            estimated_resolution_time_min=estimated_resolution_time,
            next_steps=next_steps
        )


class PoliceCheckpointHandler:
    """
    Handler for police checkpoints and regulatory stops.
    
    Aspects to collect:
    - Checkpoint location
    - Reason for stop (license, documents, cargo inspection)
    - Current queue/wait time
    - Document status (all papers in order?)
    
    Resolution options:
    1. Checkpoint wait (follow procedure, release once cleared)
    2. Alternate route (if available and faster)
    3. Document verification (ensure all papers valid)
    """
    
    def __init__(self):
        self.name = "PoliceCheckpointHandler"
        self.exception_type = "POLICE_CHECKPOINT"
        self.typical_checkpoint_wait_min = 15  # average
        self.critical_checkpoint_wait_min = 45  # escalate if > 45 min
    
    def analyze(self, context: HandlerContext, conversation_state: Dict) -> HandlerResponse:
        """Analyze checkpoint situation and recommend procedures."""
        
        detected_aspects = {}
        follow_ups = []
        actions = []
        severity = "MEDIUM"
        escalation_required = False
        escalation_reason = None
        
        # Extract data
        checkpoint_location = conversation_state.get("checkpoint_location")
        checkpoint_reason = conversation_state.get("checkpoint_reason")
        queue_wait_time_min = conversation_state.get("queue_wait_time_min")
        documents_status = conversation_state.get("documents_status")
        
        # 1. Record checkpoint location
        if checkpoint_location:
            detected_aspects["checkpoint_location"] = checkpoint_location
        else:
            follow_ups.append("Which location/highway is the checkpoint at?")
        
        # 2. Understand stop reason
        if checkpoint_reason:
            detected_aspects["checkpoint_reason"] = checkpoint_reason
            if "cargo inspection" in checkpoint_reason.lower() or "inspection" in checkpoint_reason.lower():
                severity = "MEDIUM"
                follow_ups.append("Is your cargo documentation complete and accurate?")
            elif "document" in checkpoint_reason.lower() or "license" in checkpoint_reason.lower():
                severity = "MEDIUM"
                follow_ups.append("Are all your vehicle documents (license, registration, permits) valid and present?")
            elif "goods" in checkpoint_reason.lower() or "valuation" in checkpoint_reason.lower():
                severity = "HIGH"
                follow_ups.append("Do you have proper goods declaration and tax documents?")
        else:
            follow_ups.append("Why did they stop you? (License check, cargo inspection, document verification, etc)")
        
        # 3. Assess current wait time
        if queue_wait_time_min:
            try:
                wait_min = int(str(queue_wait_time_min).replace("min", "").split()[0])
                detected_aspects["queue_wait_time_min"] = wait_min
                
                if wait_min > self.critical_checkpoint_wait_min:
                    severity = "HIGH"
                    escalation_required = True
                    escalation_reason = f"Checkpoint wait {wait_min}min exceeds typical duration"
            except:
                follow_ups.append("How long is the queue? Estimated wait in minutes?")
        else:
            follow_ups.append("How many vehicles are ahead? Estimated wait time?")
        
        # 4. Verify document status
        if documents_status:
            detected_aspects["documents_status"] = documents_status
            if "invalid" in documents_status.lower() or "missing" in documents_status.lower():
                severity = "HIGH"
                escalation_required = True
                escalation_reason = "Missing or invalid documents detected"
        else:
            follow_ups.append("Are all your documents (permit, license, cargo declaration) present and valid?")
        
        # 5. Recommend actions
        actions.append(ResolutionAction.CHECKPOINT_WAIT)
        actions.append(ResolutionAction.DOCUMENT_VERIFICATION)
        
        # Can suggest alternate route only if checkpoint is for non-mandatory stops
        if "cargo inspection" not in checkpoint_reason.lower():
            actions.append(ResolutionAction.ALTERNATE_ROUTE)
        
        # 6. Build next steps
        next_steps = []
        if severity == "HIGH" and escalation_required:
            next_steps.append("ALERT: Check document validity immediately")
            next_steps.append("Contact dispatch for document support/guidance")
            next_steps.append("Do not proceed until documents verified")
            next_steps.append("Escalate to legal/compliance if documents invalid")
        elif detected_aspects.get("queue_wait_time_min", 0) > 30:
            next_steps.append("Checkpoint has longer wait - this is normal for inspections")
            next_steps.append("Have all documents ready and visible")
            next_steps.append("Be cooperative with checkpoint officials")
            next_steps.append("Continue journey once cleared")
        else:
            next_steps.append("Follow checkpoint official instructions")
            next_steps.append("Have documents ready (license, registration, permits)")
            next_steps.append("Keep cargo declaration accessible")
            next_steps.append("Checkpoint typically clears in 15-30 minutes")
        
        estimated_resolution_time = max(
            detected_aspects.get("queue_wait_time_min", self.typical_checkpoint_wait_min),
            self.typical_checkpoint_wait_min
        )
        
        return HandlerResponse(
            handler_name=self.name,
            exception_type=self.exception_type,
            severity=severity,
            detected_aspects=detected_aspects,
            recommended_actions=actions,
            follow_up_questions=follow_ups,
            escalation_required=escalation_required,
            escalation_reason=escalation_reason,
            estimated_resolution_time_min=estimated_resolution_time,
            next_steps=next_steps
        )


# ─────────────────────────────────────────────────────────────────────────────
# Handler Factory
# ─────────────────────────────────────────────────────────────────────────────

class ExceptionHandlerFactory:
    """Factory to instantiate appropriate handler by exception type."""
    
    def __init__(self):
        self.handlers = {
            "MECHANICAL_FAILURE": MechanicalFailureHandler(),
            "DRIVER_SICKNESS": DriverSicknessHandler(),
            "TRAFFIC_CONGESTION": TrafficCongestionHandler(),
            "POLICE_CHECKPOINT": PoliceCheckpointHandler(),
        }
    
    def get_handler(self, exception_type: str):
        """Get handler for specific exception type."""
        return self.handlers.get(exception_type)
    
    def analyze(
        self,
        exception_type: str,
        context: HandlerContext,
        conversation_state: Dict
    ) -> Optional[HandlerResponse]:
        """Analyze exception with appropriate handler."""
        handler = self.get_handler(exception_type)
        if handler:
            return handler.analyze(context, conversation_state)
        return None
    
    def get_all_handlers(self):
        """Get all registered handlers."""
        return self.handlers


# Singleton instance
_handler_factory = None

def get_handler_factory() -> ExceptionHandlerFactory:
    """Get singleton handler factory instance."""
    global _handler_factory
    if _handler_factory is None:
        _handler_factory = ExceptionHandlerFactory()
    return _handler_factory
