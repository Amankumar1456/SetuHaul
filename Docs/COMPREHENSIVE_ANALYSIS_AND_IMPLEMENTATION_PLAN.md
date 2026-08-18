# SetuHaul: Comprehensive Codebase Analysis & Implementation Plan

**Date**: 2026-08-18  
**Status**: Strategic Planning Phase  
**Scope**: Full system architecture review + phased implementation roadmap

---

## EXECUTIVE SUMMARY

SetuHaul is a **Transit Management System (TMS)** designed to intelligently manage driver exceptions, dock slot allocations, and warehouse operations across 6 facilities (WH-A through WH-F) in North and West India.

### Current State
- **Backend**: FastAPI-based agent using LLM (OpenRouter) + LangGraph for reactive decision-making
- **Database**: Supabase (PostgreSQL) with modular schema
- **Frontend**: React with TanStack Router for Driver Portal and Operations Dashboard
- **Integration**: Real-time chat, slot booking, escalation workflows

### Gap Analysis vs. Strategy Requirements
The strategy document introduces a **prescriptive, event-driven architecture** that requires:
1. **10 Application Layers** (currently missing formal architecture)
2. **Context-aware follow-up questions** in the LLM system prompt
3. **Location-based triggering** for slot availability queries
4. **Enhanced UI/UX** (typing animations, text highlighting, location sharing)
5. **Warehouse-centric dashboard** with real-time resource tracking and escalation management

---

## PART 1: CURRENT ARCHITECTURE ANALYSIS

### 1.1 Backend Structure

#### Core Modules
| Module | Purpose | Status |
|--------|---------|--------|
| `agent.py` | LangGraph-based conversational AI agent | ✅ Complete |
| `tools.py` | Deterministic tools (slot lookup, booking, escalation) | ✅ Complete |
| `database.py` | Supabase ORM layer | ✅ Complete |
| `allocation.py` | Deterministic slot ranking policy | ✅ Complete |
| `feasibility.py` | Slot validation logic | ✅ Complete |
| `redis_client.py` | Session state, hold management | ✅ Complete |
| `main.py` | FastAPI entry point | ✅ Complete |

#### LLM Architecture (agent.py)
```
System Prompt (Comprehensive rule set)
    ↓
    ├─ Explicit boundaries (YOU CAN DO / YOU MUST NOT)
    ├─ Operational rules (slot lookup, confirmation flow)
    ├─ Tool descriptions & responsibility matrix
    └─ Tone & language guidelines
    ↓
LLM (OpenRouter) selects which tool to call
    ↓
Tools execute deterministically (no AI inside)
    ↓
Results fed back to LLM for next turn
```

**Strengths**:
- Clean tool/responsibility separation
- Comprehensive system prompt with clear boundaries
- Tool-level determinism (ranking, feasibility checks)
- Proper idempotency patterns in booking

**Weaknesses**:
- No **context extraction** for follow-up questions (strategy gap)
- No **location-triggered prompting** for ETA calculations
- No **event-driven re-evaluation** of shipment states
- System prompt is static; doesn't adapt to exception type

---

### 1.2 Database Schema (Supabase)

**Key Tables**:
- `drivers`: Driver identity, carrier, status
- `shipments`: Cargo, destination facility, priority, current status
- `facilities`: Warehouse info (gates, hours, capacity)
- `appointment_slots`: Available dock slots (facility, gate, dock_type, status)
- `appointments`: Confirmed bookings (slot_id, shipment_id, status)
- `eta_updates`: Driver-declared ETA history
- `facility_checkins`: Gate entry records
- `escalations`: Exception tickets for human review

**Current Gaps**:
- ❌ No formal **Application Layers** (missing Warehouse, Resource, Scheduling, Yard, Tracking, Notification, Reporting layers)
- ❌ No **location coordinates** (Lat/Long) stored for distance calculations
- ❌ No **driver current location** snapshot (only declared ETA)
- ❌ No **yard state tracking** (Expected → Arrived → Docked → Departed)
- ❌ No **resource pool tracking** (drivers, trucks, staff, machinery per warehouse)
- ❌ No **gate-level occupancy** calendar
- ❌ No **escalation severity/contextual routing** (currently flat structure)

---

### 1.3 Frontend Architecture

#### Driver Workspace (`driver-workspace.tsx`)
```
Message Input
    ↓
POST /chat (driver_id, message)
    ↓
Agent processes (calls tools, LLM reasoning)
    ↓
Response displayed as single text message
    ↓
Shipments refreshed (if state changed)
```

**Current Features**:
- Basic chat interface
- Quick action buttons
- Shipment list display
- Single message flow

**Gaps**:
- ❌ No **typing animation** while response is being generated
- ❌ No **message highlighting** (important data points)
- ❌ No **location sharing button** (required for ETA calculations)
- ❌ No **follow-up questions** display
- ❌ No **slot options** presented as rich UI (ranked, visual comparison)

#### Operations Dashboard (`dashboard.tsx` + `ops-assistant.tsx`)
```
Dashboard Layout
    ├─ OpsAssistant (chat for ops team)
    └─ Outlet (warehouse-specific views)
```

**Current State**: Minimal implementation
- Basic layout structure only
- No warehouse cards
- No resource summaries
- No escalation panel
- No gate-level occupancy visualization

**Strategy Requirements**:
- ✅ Modular warehouse sections (A-F)
- ✅ Resource summary per warehouse
- ✅ Slot timeline with gate occupancy
- ✅ Yard snapshot (live truck states)
- ✅ Integrated escalation panel
- ✅ Contextual routing (Warehouse ID + Urgency tags)
- ✅ Actionable tickets with thread links
- ✅ Manual override capability

---

### 1.4 Exception Handling Pipeline

**Current Flow**:
```
Driver Message
    ↓
LLM analyzes intent
    ↓
Call lookup_driver_context (fetch facts)
    ↓
If slot change needed → call get_feasible_slots
    ↓
Present ranked options
    ↓
Driver confirms → call confirm_booking_tool
    ↓
If unsolvable → call escalate_to_human
```

**Limitations**:
- No **exception-type-specific follow-up logic** (mechanical failure asks different questions than driver sickness)
- No **location-based conditional prompting** (doesn't automatically ask for location when needed)
- No **facility state re-evaluation** (doesn't detect if facility closed/at capacity)
- No **batch escalation** (can't mass-update shipments when facility blocked)

---

## PART 2: STRATEGY REQUIREMENTS DETAILED BREAKDOWN

### 2.1 System Prompt Enhancements

**Requirement**: "Change the system prompt such that when the driver query is received if these data is not present it asks follow-up questions based on the aspect and the logic"

#### Exception-Specific Follow-up Logic

| Exception Type | Aspect Needed | Follow-up Questions | Trigger Condition |
|---|---|---|---|
| **Mechanical Failure** | Repair Duration + Current Location | "How long will repairs take?" "What's your current location?" | Driver mentions "breakdown", "tyre", "engine", "damage" |
| **Driver Sickness** | Current Warehouse (of replacement driver pool) | "Are you at your home warehouse?" "Can you reach [nearest warehouse]?" | Driver mentions "sick", "unwell", "health", "substitute" |
| **Police Checkpoint** | Location Snapshot freshness + GPS verification | "What's your current location?" "Any estimated delay from the checkpoint?" | Driver mentions "police", "checkpoint", "stopped" |
| **Traffic Congestion** | Current Location + Real-time routing data | "Where are you now?" "Do you have GPS data we can use?" | Driver mentions "traffic", "congestion", "slow", "delay" |
| **Facility Capacity** | Facility capacity status + shipment priority | [No driver questions - system evaluates and escalates] | Facility reports "at capacity" or no slots within 3 hours |

#### Implementation Approach

1. **Intent Detection Layer** (add to agent.py):
   - Keywords → exception type mapping
   - Confidence scoring (what type of exception is this?)
   - Multi-turn conversation state (did we already ask for location?)

2. **Context-Aware Prompting**:
   ```python
   # Pseudo-code for system prompt injection
   if detected_exception_type == "MECHANICAL_FAILURE":
       system_prompt += """
       For mechanical failures, always ask:
       1. Repair duration (in minutes or hours)
       2. Current location (or permission to fetch from GPS)
       If driver cannot provide repair duration, escalate as CRITICAL.
       """
   elif detected_exception_type == "DRIVER_SICKNESS":
       system_prompt += """
       For driver sickness, check if a replacement driver is available at
       the same warehouse. Query Resource Management to find Home-Base drivers
       at driver's current warehouse.
       """
   ```

3. **Multi-turn State Management**:
   - Track which follow-up questions have been asked in current conversation
   - Don't repeat questions
   - Escalate if driver cannot provide required data after 2 attempts

---

### 2.2 Location-Based Help System

**Requirement**: "When the driver sends a message and we send it to the LLM to process, include in the system prompt that we will need the current location of the driver as per the required parameters of resolution. If yes it should show a button on the driver chat interface to send one time location."

#### Database Schema Changes (Location Layer)

```sql
-- Add to drivers table
ALTER TABLE drivers ADD COLUMN (
  current_lat DECIMAL(10, 8),
  current_lng DECIMAL(11, 8),
  location_updated_at TIMESTAMPTZ,
  location_source VARCHAR(50)  -- 'GPS', 'MANUAL', 'ETA_CALC'
);

-- Add to facilities table
ALTER TABLE facilities ADD COLUMN (
  facility_lat DECIMAL(10, 8),
  facility_lng DECIMAL(11, 8),
  gates_config JSONB  -- {A1: {lat, lng}, A2: {lat, lng}, ...}
);

-- Add to eta_updates table
ALTER TABLE eta_updates ADD COLUMN (
  driver_lat DECIMAL(10, 8),
  driver_lng DECIMAL(11, 8),
  calculated_distance_km DECIMAL(8, 2),
  calculated_duration_min INTEGER
);
```

#### Frontend Changes (`driver-workspace.tsx`)

1. **Location Sharing Button**:
   ```typescript
   // Show conditionally when system prompt indicates location is needed
   if (message.includes("LOCATION_REQUIRED")) {
     showLocationButton = true;
   }
   
   // One-click location capture
   const sendLocation = async () => {
     if (navigator.geolocation) {
       navigator.geolocation.getCurrentPosition((position) => {
         const { latitude, longitude } = position.coords;
         // Send to backend with new endpoint
         await fetch(`${API_BASE}/driver/location`, {
           method: "POST",
           body: JSON.stringify({
             driver_id,
             latitude,
             longitude,
             source: 'GPS'
           })
         });
       });
     }
   };
   ```

2. **Static Location Fallback** (for testing):
   ```typescript
   // If GPS unavailable, use static locations between WH-A and WH-B
   const STATIC_LOCATIONS = {
     "WH_A_TO_WH_B_MID": { lat: 18.5204, lng: 73.8567 },
     "NEAR_WH_A": { lat: 18.5190, lng: 73.8550 },
     "NEAR_WH_B": { lat: 18.5220, lng: 73.8585 }
   };
   ```

3. **UI Indicator**:
   ```typescript
   // Show when location is being used for calculation
   <LocationIndicator 
     location={currentLocation}
     status="Using current location for ETA"
   />
   ```

#### Backend Changes (tools.py)

```python
@tool
@traceable(name="calculate_eta_with_location", run_type="tool")
def calculate_eta_with_location(
    driver_id: str,
    current_lat: float,
    current_lng: float,
    destination_facility_id: str
) -> dict:
    """
    Use Geoapify Routing API to calculate distance and ETA.
    1. Fetch facility coordinates
    2. Call Geoapify with current location → facility
    3. Return distance_km, duration_min, optimized_eta_ts
    """
    facility = get_facility(destination_facility_id)
    
    # Call Geoapify API (requires API key)
    route = geoapify_routing(
        start=(current_lat, current_lng),
        end=(facility["facility_lat"], facility["facility_lng"])
    )
    
    return {
        "distance_km": route["distance_km"],
        "duration_min": route["duration_min"],
        "optimized_eta_ts": calculate_eta_timestamp(route["duration_min"]),
        "confidence": "HIGH"  # Based on GPS + routing
    }
```

---

### 2.3 Chat Interface UX Enhancements

#### Requirement 1: Typing Animation

**Current State**: Response appears instantly after API call.

**Target State**: Show streaming typing indicator while LLM is processing.

**Implementation**:

1. **Backend** (`main.py`):
   ```python
   # Change from simple JSON response to streaming
   @app.post("/chat")
   async def chat(request: ChatRequest):
       driver_id = request.driver_id
       message = request.message
       
       # Stream response chunks instead of waiting for full response
       async def response_generator():
           async for chunk in run_agent_stream(driver_id, message):
               yield f"data: {json.dumps(chunk)}\n\n"
       
       return StreamingResponse(
           response_generator(),
           media_type="text/event-stream"
       )
   ```

2. **Frontend** (`driver-workspace.tsx`):
   ```typescript
   // Use EventSource for streaming
   const handle = async (text: string) => {
       push({ role: "driver", text });
       setInput("");
       setSending(true);
       
       // Show typing indicator immediately
       let typingMsg = { role: "assistant", text: "...", isTyping: true };
       push(typingMsg);
       
       const eventSource = new EventSource(
           `${API_BASE}/chat?driver_id=${driver.driver_id}&message=${text}`
       );
       
       let fullResponse = "";
       eventSource.onmessage = (event) => {
           const chunk = JSON.parse(event.data).chunk;
           fullResponse += chunk;
           // Update message in real-time
           setMsgs(prev => {
               const last = prev[prev.length - 1];
               if (last.isTyping) {
                   return [...prev.slice(0, -1), 
                           { role: "assistant", text: fullResponse, isTyping: true }];
               }
               return prev;
           });
       };
       
       eventSource.onclose = () => {
           setMsgs(prev => {
               const last = prev[prev.length - 1];
               return [...prev.slice(0, -1), 
                       { role: "assistant", text: fullResponse, isTyping: false }];
           });
           setSending(false);
       };
   };
   ```

#### Requirement 2: Message Highlighting

**Current State**: Entire response is plain text.

**Target State**: Important data points (slot options, ETAs, warnings) are highlighted/styled.

**Implementation**:

1. **Backend** (tools.py):
   ```python
   # Annotate response with metadata for frontend
   def format_slot_options(slots):
       return {
           "type": "SLOT_OPTIONS",
           "ranked_slots": [
               {
                   "rank": 1,
                   "slot_id": slot["slot_id"],
                   "start_ts": slot["slot_start_ts"],
                   "duration_min": slot["duration_min"],
                   "gate": slot["gate"],
                   "score": allocation_score,
                   "reason": "Recommended - earliest available"
               },
               # ... more slots
           ],
           "text_summary": "3 slots available..."
       }
   ```

2. **Frontend** (`driver-workspace.tsx`):
   ```typescript
   // Parse rich message types and render accordingly
   function renderMessage(msg: Msg) {
       const parsed = tryParseRichContent(msg.text);
       
       if (parsed?.type === "SLOT_OPTIONS") {
           return <SlotOptionsCard slots={parsed.ranked_slots} />;
       } else if (parsed?.type === "WARNING") {
           return <WarningBanner message={parsed.text} />;
       } else if (parsed?.type === "ESCALATION_NOTICE") {
           return <EscalationNotice {...parsed} />;
       }
       
       // Fallback to text with inline highlights
       return <HighlightedText content={msg.text} />;
   }
   
   // Highlight important data points using regex patterns
   function HighlightedText({ content }: { content: string }) {
       const highlighted = content
           .replace(/(\d{2}:\d{2})/g, '<span class="highlight-time">$1</span>')
           .replace(/(CRITICAL|HIGH|URGENT)/gi, '<span class="highlight-urgent">$1</span>')
           .replace(/(Warehouse [A-F])/gi, '<span class="highlight-location">$1</span>');
       
       return <div dangerHTML={highlighted} />;
   }
   ```

---

### 2.4 Database Schema: 10 Application Layers

**Requirement**: "Start by updating your database.py to include the 10 Application Layers defined in the source (Identity, Warehouse, Resource, Shipment, Scheduling, Yard, ETA, Tracking, Notification, Reporting)."

#### Layer Architecture

| Layer | Purpose | Key Tables | Status |
|-------|---------|-----------|--------|
| **Identity** | Driver, carrier, user authentication | `drivers`, `carriers`, `users` | ✅ Exists |
| **Warehouse** | Facility info, gates, capacity, hours | `facilities`, `gates`, `facility_capacity_rules` | ⚠️ Partial |
| **Resource** | Drivers, trucks, staff, machinery availability | `drivers`, `trucks`, `staff`, `machinery`, `resource_pool` | ❌ Missing |
| **Shipment** | Cargo, origin, destination, priority | `shipments`, `shipment_items`, `shipment_status_history` | ✅ Exists |
| **Scheduling** | Dock slots, availability, reservation | `appointment_slots`, `appointments`, `slot_holds` | ✅ Exists |
| **Yard** | Truck arrival/departure, docking, queue | `yard_states`, `truck_dock_assignments`, `yard_queue` | ❌ Missing |
| **ETA** | Declared/calculated ETAs, distance, routing | `eta_updates`, `route_analysis`, `geoapify_cache` | ⚠️ Partial |
| **Tracking** | Real-time location, gate in/out, timestamps | `facility_checkins`, `driver_location_history`, `gate_logs` | ⚠️ Partial |
| **Notification** | Alerts, escalations, SMS/email queue | `notifications`, `escalations`, `notification_log` | ⚠️ Partial |
| **Reporting** | Analytics, audit trail, decision logs | `decision_audit`, `performance_metrics`, `system_events` | ❌ Missing |

#### New Tables Required

```sql
-- Layer 2: Warehouse
CREATE TABLE facility_gates (
    gate_id VARCHAR PRIMARY KEY,
    facility_id VARCHAR REFERENCES facilities,
    gate_name VARCHAR,
    gate_lat DECIMAL(10, 8),
    gate_lng DECIMAL(11, 8),
    gate_type VARCHAR (INBOUND, OUTBOUND, DUAL),
    capacity_per_hour INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE facility_capacity_rules (
    rule_id VARCHAR PRIMARY KEY,
    facility_id VARCHAR REFERENCES facilities,
    dock_type VARCHAR,
    max_concurrent_trucks INTEGER,
    queue_limit INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Layer 3: Resource
CREATE TABLE resource_pool (
    pool_id VARCHAR PRIMARY KEY,
    warehouse_id VARCHAR REFERENCES facilities,
    resource_type VARCHAR (DRIVER, TRUCK, STAFF, MACHINERY),
    total_count INTEGER,
    available_count INTEGER,
    assigned_count INTEGER,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE driver_availability (
    driver_id VARCHAR PRIMARY KEY REFERENCES drivers,
    current_warehouse_id VARCHAR REFERENCES facilities,
    home_warehouse_id VARCHAR REFERENCES facilities,
    available_from TIMESTAMPTZ,
    available_until TIMESTAMPTZ,
    status VARCHAR (AVAILABLE, ASSIGNED, IN_TRANSIT),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Layer 4: Yard
CREATE TABLE yard_states (
    yard_state_id VARCHAR PRIMARY KEY,
    truck_id VARCHAR REFERENCES trucks,
    facility_id VARCHAR REFERENCES facilities,
    state VARCHAR (EXPECTED, ARRIVED, DOCKED, UNLOADING, DEPARTED),
    state_timestamp TIMESTAMPTZ,
    gate_id VARCHAR REFERENCES facility_gates,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE truck_dock_assignments (
    assignment_id VARCHAR PRIMARY KEY,
    truck_id VARCHAR REFERENCES trucks,
    facility_id VARCHAR REFERENCES facilities,
    dock_id VARCHAR,
    assigned_at TIMESTAMPTZ,
    dock_entry_at TIMESTAMPTZ,
    dock_exit_at TIMESTAMPTZ,
    unload_duration_min INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Layer 6: Tracking
CREATE TABLE driver_location_history (
    location_id VARCHAR PRIMARY KEY,
    driver_id VARCHAR REFERENCES drivers,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    accuracy_m INTEGER,
    source VARCHAR (GPS, MANUAL, ETA_CALC),
    recorded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE gate_logs (
    log_id VARCHAR PRIMARY KEY,
    facility_id VARCHAR REFERENCES facilities,
    gate_id VARCHAR REFERENCES facility_gates,
    truck_id VARCHAR REFERENCES trucks,
    shipment_id VARCHAR REFERENCES shipments,
    event_type VARCHAR (GATE_IN, GATE_OUT, QUEUE_ENTRY, QUEUE_EXIT),
    event_timestamp TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Layer 9: Notification
CREATE TABLE notifications (
    notification_id VARCHAR PRIMARY KEY,
    recipient_type VARCHAR (DRIVER, OPS_TEAM, ADMIN),
    recipient_id VARCHAR,
    notification_type VARCHAR (SLOT_AVAILABLE, DELAY_ALERT, ESCALATION, SYSTEM_EVENT),
    title VARCHAR,
    message TEXT,
    priority VARCHAR (LOW, NORMAL, HIGH, CRITICAL),
    status VARCHAR (PENDING, SENT, READ, FAILED),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ
);

-- Layer 10: Reporting
CREATE TABLE decision_audit (
    audit_id VARCHAR PRIMARY KEY,
    decision_type VARCHAR (SLOT_ALLOCATION, ESCALATION, OVERRIDE),
    actor_id VARCHAR,
    actor_type VARCHAR (LLM_AGENT, HUMAN_OPS, SYSTEM),
    affected_shipment_id VARCHAR REFERENCES shipments,
    decision_data JSONB,
    previous_state JSONB,
    new_state JSONB,
    reasoning TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE system_events (
    event_id VARCHAR PRIMARY KEY,
    event_type VARCHAR,
    severity VARCHAR (INFO, WARNING, ERROR, CRITICAL),
    source_module VARCHAR,
    event_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

### 2.5 Operations Dashboard: Warehouse-Centric View

**Requirement**: "The dashboard must be modular, representing one card or section per warehouse (A-F) to manage the specific operational view of each site."

#### Dashboard Layout

```
┌─ Dashboard Header (Date, Sync Status, User Info)
├─ Warehouse Tabs (A | B | C | D | E | F)
│
└─ Warehouse View (when WH-A selected):
   ├─ Resource Summary Panel
   │  ├─ 🚗 Drivers: 12 available / 8 assigned / 3 in-transit
   │  ├─ 🚛 Trucks: 15 available / 10 assigned / 2 in-yard
   │  ├─ 👥 Staff: 24 on duty / 18 assigned
   │  └─ ⚙️ Machinery: 5 available / 3 in-use
   │
   ├─ Slot Timeline
   │  └─ Calendar view with gates A1-A6
   │     ├─ Confirmed (green)
   │     ├─ Pending (yellow)
   │     └─ In-Progress (blue)
   │
   ├─ Yard Snapshot
   │  ├─ Arrived (🚛 5 trucks in queue)
   │  ├─ Docked (🔧 3 trucks unloading, ETA 45min)
   │  └─ Upcoming (📋 2 trucks expected in 30min)
   │
   └─ Escalation & Admin Control Panel
      ├─ Contextual Routing (sorted by Warehouse + Urgency)
      ├─ Actionable Tickets
      │  ├─ SHP-12345 | Mechanical Failure | CRITICAL
      │  │  └─ No slots available within 3 hours
      │  │  └─ Driver Chat Link: [View Thread]
      │  │  └─ Action: [Override Capacity] [Escalate]
      │  └─ ...more tickets
      └─ Manual Overrides
         ├─ Override Reason: Commercial penalty approval
         └─ Auditability: Logged as SHIPMENT_RESOLVED event
```

---

## PART 3: PHASED IMPLEMENTATION ROADMAP

### Phase 1: Database Foundation (Week 1-2)

**Objective**: Establish 10 Application Layers in database schema.

#### Tasks

1. **Schema Migration Script** (`database_migrations.sql`)
   - Create all new tables (Resource, Yard, Tracking, Reporting layers)
   - Add location columns (lat/lng) to facilities, drivers, eta_updates
   - Create indexes for performance (facility_id, shipment_id, driver_id, warehouse_id)

2. **Update `database.py`**
   - Add helper functions for each layer:
     ```python
     # Layer 2: Warehouse
     def get_facility_with_gates(facility_id)
     def get_gate_capacity(gate_id)
     
     # Layer 3: Resource
     def get_resource_pool(warehouse_id)
     def update_driver_availability(driver_id, status)
     def find_available_drivers_at_warehouse(warehouse_id)
     
     # Layer 4: Yard
     def update_yard_state(truck_id, facility_id, new_state)
     def get_trucks_in_yard(facility_id, state_filter)
     
     # Layer 6: Tracking
     def save_driver_location(driver_id, lat, lng, source)
     def get_driver_location_history(driver_id, minutes=60)
     
     # Layer 10: Reporting
     def log_decision(decision_type, actor_id, affected_shipment_id, data)
     ```

3. **Seeding Script** (`seed_database.py`)
   - Populate gates for WH-A through WH-F
   - Create capacity rules per warehouse
   - Initialize resource pools
   - Insert sample location history for testing

---

### Phase 2: LLM Enhancement - Context-Aware Prompting (Week 2-3)

**Objective**: Add exception-specific follow-up logic to system prompt.

#### Tasks

1. **Intent Detection Module** (`app/intent_detector.py`)
   ```python
   class IntentDetector:
       EXCEPTION_TYPES = {
           "MECHANICAL_FAILURE": ["breakdown", "tyre", "engine", "damage", "repair"],
           "DRIVER_SICKNESS": ["sick", "unwell", "substitute", "replacement"],
           "TRAFFIC_CONGESTION": ["traffic", "congestion", "delay", "slow"],
           "POLICE_CHECKPOINT": ["police", "checkpoint", "stopped"],
           "FACILITY_FULL": ["no slots", "capacity", "cannot accommodate"],
       }
       
       def detect(self, message: str) -> tuple[str, float]:
           # Returns (exception_type, confidence_score)
       
       def get_required_aspects(self, exception_type: str) -> list[str]:
           # Returns list of aspects needed for this exception
   ```

2. **Dynamic System Prompt Generation** (`app/agent.py`)
   ```python
   def generate_system_prompt(exception_type: str, driver_context: dict) -> str:
       base_prompt = SYSTEM_PROMPT
       
       if exception_type == "MECHANICAL_FAILURE":
           base_prompt += """
           For this mechanical failure:
           1. First ask: "How long will repairs take?"
           2. Then ask: "What's your current location?"
           3. Call calculate_eta_with_location with new ETA
           4. If new arrival time misses facility close_time, 
              recommend ON_HOLD state for next operational window.
           """
       
       elif exception_type == "DRIVER_SICKNESS":
           base_prompt += """
           For this driver sickness:
           1. Get current warehouse from driver context
           2. Call find_available_drivers_at_warehouse
           3. Prioritize Home-Base drivers (lower repositioning cost)
           4. Present options or escalate if none available
           """
       
       # ... more exception types
       
       return base_prompt
   ```

3. **Multi-turn State Tracking** (Redis enhancement)
   ```python
   # Store in Redis for session:
   {
       "conversation_state": {
           "exception_type": "MECHANICAL_FAILURE",
           "questions_asked": ["repair_duration", "location"],
           "aspects_collected": {
               "repair_duration": "2 hours",
               "current_location": {lat: 18.52, lng: 73.85}
           },
           "follow_up_needed": ["eta_confirmation"]
       }
   }
   ```

---

### Phase 3: Location-Based Help System (Week 3-4)

**Objective**: Add location capture and ETA calculation capability.

#### Tasks

1. **Backend Location Endpoint** (`main.py`)
   ```python
   @app.post("/driver/location")
   async def save_driver_location(request: LocationRequest):
       # request.driver_id, .latitude, .longitude, .source
       save_driver_location(
           request.driver_id,
           request.latitude,
           request.longitude,
           request.source
       )
       return {"status": "Location updated"}
   ```

2. **Geoapify Integration** (`app/routing.py`)
   ```python
   class RoutingEngine:
       def __init__(self, api_key: str):
           self.api_key = api_key
           self.base_url = "https://api.geoapify.com/v1/routing"
       
       def calculate_route(
           self,
           start_lat: float,
           start_lng: float,
           end_lat: float,
           end_lng: float
       ) -> dict:
           # Call Geoapify API
           # Return: {distance_km, duration_min, polyline}
       
       def calculate_eta(
           self,
           current_location: tuple[float, float],
           destination_facility_id: str
       ) -> str:
           # Calculate optimized ETA timestamp
   ```

3. **Frontend Location Button** (`driver-workspace.tsx`)
   - Add conditional rendering when location needed
   - Implement geolocation permission flow
   - Fallback to static locations
   - Show loading state during capture

4. **Tool Enhancement** (`tools.py`)
   ```python
   @tool
   def get_feasible_slots_with_location(
       shipment_id: str,
       facility_id: str,
       driver_lat: float,
       driver_lng: float
   ) -> dict:
       # Use location to calculate accurate ETA
       # Return slot options ranked by new ETA
   ```

---

### Phase 4: Chat UI Enhancements (Week 4-5)

**Objective**: Add streaming, typing animation, and message highlighting.

#### Tasks

1. **Streaming Response Architecture**
   - Change `/chat` endpoint to `StreamingResponse`
   - Implement chunk-based response streaming
   - Frontend consumes via EventSource/WebSocket

2. **Typing Animation Component** (`components/ui/typing-indicator.tsx`)
   ```typescript
   export function TypingIndicator() {
     return (
       <div className="flex gap-1">
         <span className="animate-bounce">•</span>
         <span className="animate-bounce delay-100">•</span>
         <span className="animate-bounce delay-200">•</span>
       </div>
     );
   }
   ```

3. **Rich Message Rendering** (`driver-workspace.tsx`)
   - Parse JSON-annotated responses from backend
   - Component for slot options card
   - Component for warnings/escalation notices
   - Text highlighting with regex patterns

4. **Message Highlighting Utility** (`lib/message-highlighter.ts`)
   ```typescript
   export function highlightMessage(text: string): ReactNode {
       const patterns = [
           { regex: /(\d{2}:\d{2})/g, className: "highlight-time" },
           { regex: /(CRITICAL|HIGH|URGENT)/gi, className: "highlight-urgent" },
           { regex: /(Warehouse [A-F])/gi, className: "highlight-location" },
       ];
       // Apply highlighting and return React nodes
   }
   ```

---

### Phase 5: Operations Dashboard (Week 5-7)

**Objective**: Build warehouse-centric dashboard with resource tracking and escalation management.

#### Tasks

1. **Dashboard Layout** (`routes/dashboard.index.tsx`)
   - Warehouse tab navigation (A-F)
   - Tab-specific route structure
   - Responsive grid layout

2. **Resource Summary Component** (`components/setuhaul/resource-summary.tsx`)
   ```typescript
   interface ResourceSummary {
     warehouse_id: string;
     drivers: { available: number; assigned: number; in_transit: number };
     trucks: { available: number; assigned: number; in_yard: number };
     staff: { on_duty: number; assigned: number };
     machinery: { available: number; in_use: number };
   }
   ```

3. **Slot Timeline Component** (`components/setuhaul/slot-timeline.tsx`)
   - Calendar-based gate occupancy view
   - Color-coded status (Confirmed, Pending, In-Progress)
   - Drag-drop reschedule capability (future)

4. **Yard Snapshot Component** (`components/setuhaul/yard-snapshot.tsx`)
   - Real-time truck state display
   - States: Expected, Arrived, Docked, Unloading, Departed
   - ETA countdown for expected trucks

5. **Escalation Panel** (`components/setuhaul/escalation-panel.tsx`)
   ```typescript
   interface Escalation {
     escalation_id: string;
     warehouse_id: string;
     shipment_id: string;
     urgency: "LOW" | "NORMAL" | "HIGH" | "CRITICAL";
     reason: string;
     driver_chat_thread_id: string;
     available_actions: ("override_capacity" | "escalate" | "reassign")[];
     created_at: string;
   }
   ```

6. **WebSocket Real-time Updates** (`lib/dashboard-realtime.ts`)
   - Establish WebSocket connection
   - Subscribe to warehouse events
   - Update UI in real-time as states change

---

### Phase 6: Exception Handling Logic (Week 6-8)

**Objective**: Implement each exception-specific resolution strategy.

#### Task 1: Mechanical Failure Flow

```python
# In agent.py, add exception handler
def handle_mechanical_failure(driver_id, shipment_id, repair_duration_min):
    # 1. Get current appointment
    current_apt = get_current_appointment(shipment_id)
    current_slot_end = parse_ts(current_apt['appointment_slots']['slot_end_ts'])
    
    # 2. Calculate new ETA
    new_eta = now() + timedelta(minutes=repair_duration_min)
    
    # 3. Check if new ETA misses facility close_time
    facility = get_facility(shipment['destination_facility_id'])
    if new_eta.hour >= facility['close_time']:
        # Move to ON_HOLD for next operational window
        update_shipment_status(shipment_id, "ON_HOLD")
        return {
            "action": "ON_HOLD",
            "reason": "Repair will complete after facility close",
            "next_available_window": facility['open_time_next_day']
        }
    
    # 4. Find new feasible slots after new ETA
    slots = get_feasible_slots_with_location(
        shipment_id,
        shipment['destination_facility_id'],
        new_eta
    )
    
    return {"action": "RESCHEDULE", "options": slots}
```

#### Task 2: Driver Sickness Flow

```python
def handle_driver_sickness(driver_id):
    # 1. Get driver's current warehouse
    driver = get_driver(driver_id)
    current_warehouse = driver['current_warehouse_id']
    
    # 2. Find available replacement drivers at same warehouse
    available_drivers = find_available_drivers_at_warehouse(
        current_warehouse,
        priority="HOME_BASE"
    )
    
    if not available_drivers:
        return {
            "action": "ESCALATE",
            "reason": "No replacement drivers available at warehouse"
        }
    
    # 3. Reallocate shipments to replacement driver
    shipments = get_driver_shipments(driver_id)
    return {
        "action": "REASSIGN",
        "replacement_driver": available_drivers[0],
        "shipments_to_reassign": len(shipments)
    }
```

#### Task 3: Traffic Congestion / Police Checkpoint

```python
def handle_traffic_delay(driver_id, shipment_id, estimated_delay_min):
    # 1. Get current location
    location = get_driver_location(driver_id)
    
    # 2. Recalculate ETA using Geoapify with fresh routing
    facility = get_facility(shipment['destination_facility_id'])
    route = geoapify_routing(
        start=(location['lat'], location['lng']),
        end=(facility['facility_lat'], facility['facility_lng'])
    )
    
    new_eta = now() + timedelta(minutes=route['duration_min'])
    
    # 3. Recheck feasible slots with new ETA
    slots = get_feasible_slots_with_location(
        shipment_id,
        facility['facility_id'],
        new_eta
    )
    
    if not slots:
        return {"action": "ESCALATE", "reason": "No slots available after delay"}
    
    return {"action": "RESCHEDULE", "options": slots}
```

#### Task 4: Facility Capacity / Mass Update

```python
def handle_facility_blocked(facility_id):
    # 1. Query all TRUCK_EXPECTED shipments for this facility
    shipments = supabase.table("shipments").select("*").eq(
        "destination_facility_id", facility_id
    ).eq("current_status", "TRUCK_EXPECTED").execute()
    
    # 2. Mass-update to ON_HOLD
    for shipment in shipments.data:
        update_shipment_status(shipment['shipment_id'], "ON_HOLD")
        log_decision(
            decision_type="FACILITY_CAPACITY_HOLD",
            actor_id="SYSTEM",
            affected_shipment_id=shipment['shipment_id'],
            data={"facility_id": facility_id, "reason": "Facility blocked"}
        )
    
    # 3. Escalate as CRITICAL for ops team
    escalate_to_human(
        shipment_ids=[s['shipment_id'] for s in shipments.data],
        warehouse_id=facility_id,
        urgency="CRITICAL",
        reason=f"Facility {facility_id} blocked - {len(shipments.data)} shipments on hold"
    )
```

---

### Phase 7: Testing & Validation (Week 8-9)

**Objective**: Ensure all components work together correctly.

#### Test Categories

1. **Unit Tests** (`test/`)
   - Intent detection accuracy
   - Slot feasibility checks
   - Allocation scoring logic
   - ETA calculations

2. **Integration Tests**
   - End-to-end chat flow with follow-up questions
   - Location capture and ETA recalculation
   - Dashboard real-time updates
   - Escalation workflows

3. **Load Tests**
   - Concurrent driver messages
   - Dashboard concurrent updates
   - Database query performance

4. **Scenario Tests**
   - Mechanical failure with location
   - Driver sickness with reassignment
   - Traffic congestion with rerouting
   - Facility capacity with mass hold

---

### Phase 8: Deployment & Documentation (Week 9-10)

**Objective**: Prepare production-ready system.

#### Tasks

1. **API Documentation** (OpenAPI/Swagger)
   - Document all endpoints
   - Add new location, streaming, escalation endpoints

2. **Database Migration Plan**
   - Backup existing data
   - Run migrations (0-downtime if possible)
   - Verify data integrity

3. **Ops Runbook**
   - How to use dashboard
   - Manual override procedures
   - Escalation handling workflow

4. **Training Materials**
   - Video demos for ops team
   - FAQ for drivers
   - Troubleshooting guide

---

## PART 4: IMPLEMENTATION PRIORITY MATRIX

### Critical Path (Must Do First)

1. ✅ **Database Layer 10 schema** (foundation for everything)
2. ✅ **Location capture** (blocks ETA recalculation)
3. ✅ **Exception-type detection** (blocks follow-up questions)
4. ✅ **Dashboard warehouse view** (required for ops team visibility)
5. ✅ **Escalation panel** (required for human decision making)

### High Priority (Dependencies Clear)

6. ✅ **Streaming responses** (improves UX)
7. ✅ **Message highlighting** (improves UX)
8. ✅ **Resource pool tracking** (enables driver reassignment)
9. ✅ **Yard state transitions** (enables real-time tracking)

### Medium Priority (Nice to Have, Can Be Phased)

10. ⚠️ **Advanced routing** (Geoapify integration for sophisticated ETA)
11. ⚠️ **Manual dashboard overrides** (admin safety net)
12. ⚠️ **Analytics/reporting** (post-launch feature)
13. ⚠️ **SMS/email notifications** (external integration)

---

## PART 5: RISK ASSESSMENT & MITIGATION

| Risk | Severity | Mitigation |
|------|----------|-----------|
| LLM hallucination in follow-up questions | HIGH | Keep questions deterministic (enum list), validate driver input, escalate if uncertain |
| Location privacy concerns | HIGH | Implement opt-in permission flow, explain data usage, delete location history after use |
| Geoapify API rate limits | MEDIUM | Cache routes, batch requests, fallback to static locations |
| Database performance (new layers) | MEDIUM | Index on facility_id, shipment_id, warehouse_id; archival strategy for old records |
| Real-time WebSocket overload | MEDIUM | Implement broadcast groups per warehouse, message batching, exponential backoff |
| Facility blocking cascading failure | HIGH | Implement idempotent mass-update, queue-based processing, transaction rollback capability |

---

## PART 6: SUCCESS METRICS

### Phase Completion Criteria

| Phase | Metric | Target |
|-------|--------|--------|
| Phase 1 | All 10 layers schema created and tested | 100% tables created |
| Phase 2 | Intent detection accuracy | >90% on test set |
| Phase 3 | Location capture success rate | >95% with GPS, 100% with static fallback |
| Phase 4 | Streaming latency | <100ms chunk arrival |
| Phase 5 | Dashboard page load | <2s initial, <500ms updates |
| Phase 6 | Exception resolution without escalation | >70% for mechanical failure, >60% for sickness |
| Phase 7 | Test coverage | >80% unit tests, >5 end-to-end scenarios |

---

## APPENDIX A: File Structure After Implementation

```
SetuHaul/
├── app/
│   ├── agent.py (ENHANCED: dynamic system prompt, streaming)
│   ├── tools.py (ENHANCED: location-based tools)
│   ├── database.py (ENHANCED: 10 layer helpers)
│   ├── allocation.py (EXISTING)
│   ├── feasibility.py (EXISTING)
│   ├── intent_detector.py (NEW)
│   ├── routing.py (NEW: Geoapify integration)
│   ├── exception_handlers.py (NEW: exception-specific logic)
│   ├── redis_client.py (ENHANCED: multi-turn state)
│   └── main.py (ENHANCED: streaming, location endpoint)
│
├── frontend/frontend-react/src/
│   ├── components/setuhaul/
│   │   ├── driver-workspace.tsx (ENHANCED: typing, highlighting, location button)
│   │   ├── ops-assistant.tsx (EXISTING)
│   │   ├── resource-summary.tsx (NEW)
│   │   ├── slot-timeline.tsx (NEW)
│   │   ├── yard-snapshot.tsx (NEW)
│   │   └── escalation-panel.tsx (NEW)
│   ├── components/ui/
│   │   └── typing-indicator.tsx (NEW)
│   ├── hooks/
│   │   └── use-realtime-dashboard.tsx (NEW)
│   ├── lib/
│   │   ├── message-highlighter.ts (NEW)
│   │   ├── dashboard-realtime.ts (NEW)
│   │   └── api.ts (ENHANCED)
│   └── routes/
│       ├── dashboard.index.tsx (NEW: warehouse tabs)
│       ├── dashboard.$warehouseId.tsx (NEW: warehouse detail view)
│       └── driver.tsx (ENHANCED)
│
├── Docs/
│   ├── strategy (EXISTING)
│   ├── COMPREHENSIVE_ANALYSIS_AND_IMPLEMENTATION_PLAN.md (THIS FILE)
│   ├── API_DOCUMENTATION.md (NEW)
│   ├── DATABASE_MIGRATION_GUIDE.md (NEW)
│   └── OPS_RUNBOOK.md (NEW)
│
├── test/
│   ├── test_intent_detection.py (NEW)
│   ├── test_exception_handlers.py (NEW)
│   ├── test_routing.py (NEW)
│   ├── test_dashboard_realtime.ts (NEW)
│   └── test_scenarios.py (NEW: end-to-end scenarios)
│
└── database_migrations/
    ├── 001_create_application_layers.sql (NEW)
    ├── 002_add_location_columns.sql (NEW)
    └── 003_seed_initial_data.sql (NEW)
```

---

## APPENDIX B: Key Implementation Notes

### Note 1: System Prompt Management
The system prompt should be generated dynamically at runtime based on:
- Detected exception type
- Available context (driver location, facility status)
- Conversation history
- Current time/facility hours

Store static templates and inject context dynamically.

### Note 2: Location Privacy
- Always request permission before capturing GPS
- Show user what data is being sent
- Delete location history after booking confirmation
- Log location access for audit trail

### Note 3: Multi-turn Conversation State
Use Redis to store per-conversation state:
```python
conversation_state = {
    "driver_id": "DRV-001",
    "conversation_id": "CONV-ABC123",
    "exception_type": "MECHANICAL_FAILURE",
    "turn_count": 3,
    "questions_asked": ["repair_duration", "location"],
    "aspects_collected": {...},
    "last_turn_at": timestamp,
    "ttl": 3600  # 1 hour expiry
}
```

### Note 4: Escalation Auditability
Every escalation must create a `decision_audit` record:
```python
{
    "audit_id": "AUDIT-XYZ",
    "decision_type": "ESCALATION",
    "actor_id": "AGENT-LLM",
    "affected_shipment_id": "SHP-12345",
    "decision_data": {
        "reason": "No feasible slots within 3 hours",
        "urgency": "HIGH"
    },
    "previous_state": {"status": "IN_TRANSIT", "appointment": null},
    "new_state": {"status": "ESCALATED", "escalation_id": "ESC-456"},
    "created_at": timestamp
}
```

### Note 5: WebSocket vs EventSource
- Use **EventSource** (Server-Sent Events) for one-directional streaming (agent response)
- Use **WebSocket** for bi-directional real-time dashboard updates
- Fallback to polling if WebSocket unavailable

---

## CONCLUSION

This comprehensive analysis identifies **8 implementation phases** spanning **10 weeks** to transform SetuHaul from a basic exception handler into a **full-featured Transit Management System**.

**Critical Success Factors**:
1. Strong database foundation (10 Application Layers)
2. Deterministic exception-type logic (no LLM guessing)
3. Location-first ETA calculations (GPS or static fallback)
4. Real-time dashboard for ops visibility
5. Auditable escalation workflow

**Expected Outcome**: A production-ready system capable of resolving 70%+ of driver exceptions automatically, with clear escalation paths for human intervention.

