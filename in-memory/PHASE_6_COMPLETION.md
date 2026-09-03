**Phase 6: Exception-Specific Handlers — COMPLETE**

## Overview
Implemented 4 specialized exception workflow handlers that analyze driver situations, collect required data points, recommend resolution actions, and guide escalation decisions.

## Handler Architecture

### Core Components

**1. exception_handlers.py (485 lines)**
- Master handlers module with 4 exception-specific analyzers
- Includes data models (ResolutionAction enum, HandlerContext, HandlerResponse)
- Handler factory for dynamic handler instantiation
- Location: `app/exception_handlers.py`

**2. handler_integration.py (310 lines)**
- Integration pipeline connecting exception detection → handler analysis → logging
- Orchestrates full workflow from message detection through recommendation
- Generates agent prompt enhancements based on handler analysis
- Location: `app/handler_integration.py`

**3. agent.py (Enhanced)**
- Modified run_agent() to call handler integration after exception detection
- Incorporates handler recommendations into dynamic system prompt
- Modified: `app/agent.py` (Step 3.5 added)

---

## The 4 Exception Handlers

### 1. MechanicalFailureHandler
**Purpose**: Analyze vehicle mechanical failures and breakdowns

**Aspects Collected**:
- repair_symptom (engine, brake, suspension, tire, electrical, etc)
- repair_duration_estimate_min (0-240 minutes)
- cargo_type (food, temperature-sensitive, fragile, etc)

**Severity Classification**:
- CRITICAL: Engine, brake, steering failures → vehicle replacement
- HIGH: Transmission, suspension issues → tow to facility
- MEDIUM: Tire, electrical → repair on site with backup plan
- LOW: Cosmetic damage → continue

**Recommended Actions**:
- REPAIR_ON_SITE (minor issues, <30 min)
- TOW_TO_FACILITY (moderate, 30-120 min)
- VEHICLE_REPLACEMENT (critical, >2 hours or high-value cargo)

**Escalation Triggers**:
- Repair time > 120 minutes
- CRITICAL severity classification
- Perishable/time-sensitive cargo

**Next Steps Examples**:
- CRITICAL: "Initiate vehicle replacement immediately" + "Arrange emergency tow if perishable"
- HIGH: "Await repair estimate" + "Monitor cargo conditions"
- MEDIUM: "Continue journey once repair confirmed"

---

### 2. DriverSicknessHandler
**Purpose**: Evaluate driver health and manage health-related delays

**Aspects Collected**:
- symptom_description (fever, chest pain, dizzy, nausea, etc)
- symptom_severity (mild, moderate, severe, emergency)
- current_location (in vehicle or warehouse_id)
- medical_history (if critical)

**Severity Classification**:
- CRITICAL: Chest pain, severe symptoms, emergency keywords → medical escalation
- HIGH: Fever, vomiting, dizzy → driver replacement + rest
- MEDIUM: Headache, mild symptoms → rest at warehouse
- LOW: Fatigue, minor cold → monitor

**Recommended Actions**:
- DRIVER_REST_AT_WAREHOUSE (mild symptoms, 60-min rest)
- DRIVER_REPLACEMENT (moderate/high symptoms)
- MEDICAL_ESCALATION (critical condition → dial 112)

**Escalation Triggers**:
- Emergency keywords detected (chest pain, ambulance, hospital)
- Severe symptom classification
- Self-reported emergency

**Next Steps Examples**:
- CRITICAL: "Contact emergency services (112)" + "Provide location to dispatch" + "Initiate replacement"
- HIGH: "Dispatch replacement driver" + "Arrange warehouse rest"
- MEDIUM: "Proceed to nearest warehouse" + "Rest 30-60 minutes"

**Time Estimates**:
- LOW: 60 min (1-hour rest)
- MEDIUM: 120 min (2-hour rest + replacement prep)
- CRITICAL: Varies (medical dependent)

---

### 3. TrafficCongestionHandler
**Purpose**: Manage traffic delays and routing adjustments

**Aspects Collected**:
- traffic_location (highway, road, city, checkpoint)
- estimated_delay_min (0-360 minutes)
- current_speed (km/h for progress estimation)
- cargo_time_sensitive (yes/no/perishable)
- alternate_routes_available (yes/no)

**Severity Classification**:
- CRITICAL: >3 hours delay + time-sensitive cargo
- HIGH: 2-3 hours delay
- MEDIUM: <2 hours delay
- LOW: <30 min delay

**Recommended Actions**:
- REROUTE_DRIVER (explore alternate routes)
- REVISE_ETA (accept delay, notify warehouse)
- REBOOKING_SLOT (if delay >180 min, need new slot)

**Escalation Triggers**:
- Delay > 180 minutes (automatic rebooking needed)
- Time-sensitive cargo + >90 min delay
- Major highway congestion

**Next Steps Examples**:
- CRITICAL: "Check alternate routes immediately" + "Contact warehouse for rebooking" + "Assess cargo condition"
- HIGH: "Evaluate alternate routes" + "Update ETA" + "Prepare for rebooking"
- MEDIUM: "Monitor traffic" + "Keep dispatch updated"

**Time Estimates**:
- Returned directly as estimated_delay_min from conversation

---

### 4. PoliceCheckpointHandler
**Purpose**: Handle police checkpoints and regulatory stops

**Aspects Collected**:
- checkpoint_location (highway/road/city)
- checkpoint_reason (license check, cargo inspection, document verification, goods valuation)
- queue_wait_time_min (0-120 minutes)
- documents_status (valid/invalid/missing)
- cargo_documentation (complete/incomplete)

**Severity Classification**:
- CRITICAL: Invalid/missing documents
- HIGH: Long queue (>45 min) + thorough inspection expected
- MEDIUM: Standard checkpoint, expected 15-30 min wait
- LOW: Quick license check, <15 min wait

**Recommended Actions**:
- CHECKPOINT_WAIT (standard procedure, sit tight)
- DOCUMENT_VERIFICATION (ensure all papers valid)
- ALTERNATE_ROUTE (if available, for non-mandatory stops)

**Escalation Triggers**:
- Invalid or missing documents → CRITICAL
- Queue wait >45 minutes → escalate for monitoring
- Cargo inspection fails validation

**Next Steps Examples**:
- CRITICAL: "Check document validity" + "Contact dispatch for guidance" + "Do not proceed until verified"
- HIGH: "Checkpoint has long wait" + "Have documents ready" + "Be cooperative"
- MEDIUM: "Follow official instructions" + "Keep cargo accessible" + "Typical 15-30 min clearance"

**Time Estimates**:
- Returns max(queue_wait_time, 15) = typical checkpoint duration

---

## Data Flow Architecture

```
Driver Message
    ↓
Intent Detector (Phase 2)
    ↓ [Detects: MECHANICAL_FAILURE, DRIVER_SICKNESS, etc]
    ↓
Exception Handler (Phase 6)
    ├─ Analyzes situation
    ├─ Collects missing aspects
    ├─ Determines severity
    ├─ Recommends actions
    └─ Identifies escalations
    ↓
Handler Integration Pipeline
    ├─ Serializes handler response
    ├─ Generates agent prompt enhancement
    └─ Logs to decision audit
    ↓
Agent (Enhanced System Prompt)
    ├─ Receives handler recommendations
    ├─ Executes suggested actions via tools
    └─ Provides conversational guidance
    ↓
Database Audit Trail
    ├─ decision_audit (handler analysis logged)
    ├─ driver_exceptions (escalations tracked)
    └─ system_events (actions recorded)
```

## API Usage

### Running Handler Pipeline
```python
from app.handler_integration import get_integration_pipeline

pipeline = get_integration_pipeline()

result = pipeline.run_pipeline(
    driver_id="DRV-001",
    message="My truck broke down, need help",
    conversation_id="CONV-001",
    shipment_id="SHP-2026-00042",
    warehouse_id="FAC-001",
    conversation_state={
        "repair_symptom": "engine not starting",
        "repair_duration_estimate": "90 minutes",
        "cargo_type": "food items"
    },
    driver_lat=18.52,
    driver_lng=73.85
)

# result contains:
# - exception_type: MECHANICAL_FAILURE
# - handler_name: MechanicalFailureHandler
# - severity: HIGH
# - recommended_actions: [REPAIR_ON_SITE, TOW_TO_FACILITY]
# - follow_up_questions: ["What's the cargo type?", ...]
# - escalation_required: True
# - escalation_reason: "Repair time 90min exceeds threshold"
# - next_steps: ["Await repair estimate", "Monitor cargo", ...]
```

### Getting Individual Handler
```python
from app.exception_handlers import get_handler_factory

factory = get_handler_factory()
handler = factory.get_handler("MECHANICAL_FAILURE")

response = handler.analyze(context, conversation_state)
```

---

## Files Created/Modified

**Created (2 files)**:
1. `app/exception_handlers.py` (485 lines)
   - MechanicalFailureHandler (150 lines)
   - DriverSicknessHandler (140 lines)
   - TrafficCongestionHandler (130 lines)
   - PoliceCheckpointHandler (120 lines)
   - ExceptionHandlerFactory (20 lines)

2. `app/handler_integration.py` (310 lines)
   - HandlerIntegrationPipeline (280 lines)
   - Helper methods for context creation, serialization, logging
   - Agent prompt enhancement generation

**Modified (1 file)**:
1. `app/agent.py`
   - Added Step 3.5: Handler integration after exception detection
   - Calls pipeline.run_pipeline() with conversation context
   - Appends handler_enhancement to system_prompt

---

## Type Safety & Interfaces

All handlers use strongly-typed interfaces:

```python
@dataclass
class HandlerContext:
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
    handler_name: str
    exception_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    detected_aspects: Dict[str, Any]
    recommended_actions: List[ResolutionAction]
    follow_up_questions: List[str]
    escalation_required: bool
    escalation_reason: Optional[str]
    estimated_resolution_time_min: Optional[int]
    next_steps: List[str]
```

---

## Escalation Decision Matrix

| Exception Type | Severity | Auto-Escalate? | Reason |
|---|---|---|---|
| MECHANICAL | CRITICAL | YES | Vehicle safety, cargo protection |
| MECHANICAL | HIGH | YES | Repair >120 min or perishable cargo |
| MECHANICAL | MEDIUM | NO | Repair likely <90 min |
| SICKNESS | CRITICAL | YES | Emergency medical condition |
| SICKNESS | HIGH | YES | Driver unable to continue safely |
| SICKNESS | MEDIUM | NO | Rest at warehouse sufficient |
| TRAFFIC | CRITICAL | YES | >3 hours delay, rebooking required |
| TRAFFIC | HIGH | MAYBE | >2 hours, assess cargo sensitivity |
| TRAFFIC | MEDIUM | NO | Monitor, non-critical delay |
| CHECKPOINT | CRITICAL | YES | Invalid documents, regulatory risk |
| CHECKPOINT | HIGH | YES | Long wait, potential hold-up |
| CHECKPOINT | MEDIUM | NO | Standard procedure, routine wait |

---

## Testing Recommendations

1. **Unit Tests per Handler**:
   - Test MECHANICAL handler with engine/brake/suspension symptoms
   - Test SICKNESS with emergency/urgent/mild keywords
   - Test TRAFFIC with various delay thresholds
   - Test CHECKPOINT with valid/invalid documents

2. **Integration Tests**:
   - Test pipeline with full message flow
   - Verify conversation_state properly passed to handlers
   - Verify handler response serialization
   - Verify agent prompt enhancement applied

3. **Edge Cases**:
   - Empty conversation_state (handler should ask follow-ups)
   - Multiple exceptions in one message (handler should prioritize)
   - Borderline severity (e.g., 89 min repair time)
   - Missing driver location data

4. **Escalation Tests**:
   - Verify escalation_required flag set correctly
   - Verify escalation_reason populated
   - Verify decisions logged to audit trail

---

## Phase 6 Status: ✅ COMPLETE

All 4 exception handlers implemented with:
- ✅ Aspect detection and data collection
- ✅ Severity classification logic
- ✅ Recommended action generation
- ✅ Escalation trigger identification
- ✅ Follow-up question generation
- ✅ Pipeline integration with agent
- ✅ Decision audit logging

## Next: Phase 7 — Add Unit Tests & Integration Tests
Ready to implement comprehensive test coverage for all phases 1-6.
