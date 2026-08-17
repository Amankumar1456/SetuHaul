# SetuHaul — Complete Project Documentation
**Single Source of Truth for Architecture, Flows, and System Design**

*Last Updated: 2026-08-17*  
*Project Version: 1.0.0*

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Overview](#architecture-overview)
3. [Technology Stack](#technology-stack)
4. [System Components](#system-components)
7. [Agent Tools & Capabilities](#agent-tools--capabilities)
8. [Data Flows](#data-flows)
9. [Workflows](#workflows)
10. [Deployment & Configuration](#deployment--configuration)
11. [Frontend Architecture](#frontend-architecture)
12. [Key Concepts & Terminology](#key-concepts--terminology)

---

## Project Overview

### What is SetuHaul?

**SetuHaul** is an AI-powered **driver exception management and dock slot coordination system** for freight logistics in North and West India. The system uses an intelligent agent (LLM-based) to:

- **Handle driver delays** — When a truck is running late, the driver sends a message to the agent
- **Rebook dock slots** — The agent finds available warehouse slots that fit the new ETA
- **Coordinate with warehouses** — Manages confirmation and negotiation of appointments
- **Escalate exceptions** — Routes complex issues to human operations coordinators
- **Provide ops visibility** — Real-time dashboard for operations managers

### Core Problems Solved

| Problem | Solution |
|---------|----------|
| Driver gets stuck in traffic, misses appointment | Agent finds next available slot, rebooking is automatic |
| No human available at night to handle delay calls | Conversational AI agent runs 24/7, handles ~80% of cases |
| Manual slot coordination is error-prone | Database + Redis holds ensure race-free concurrent bookings |
| Ops team has no real-time visibility | Live dashboard shows queue, escalations, holds, active threads |
| Drivers communicate in Hinglish/casual language | Agent trained to understand informal messages in Hindi/English mix |

### Target Users

1. **Drivers** — Use chat interface to report delays and get rebookings
2. **Operations Coordinators** — Manage escalations and verify bookings
3. **Warehouse Managers** — Confirm/reject appointments via system
4. **Dispatch Team** — Monitor fleet status in real-time

---

## Architecture Overview

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                             │
├──────────────────────┬──────────────────────┬───────────────────┤
│  Driver Chat UI      │  Portal Login        │  Ops Dashboard    │
│  (chat.html)         │  (index.html)        │  (dashboard.html) │
└──────────────────────┴──────────────────────┴───────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI WEB SERVER                            │
│                    (app/main.py)                                 │
├──────────────────┬──────────────────┬──────────────────────────┤
│  Chat Endpoint   │  Auth Endpoints  │  Operations Endpoints    │
│  POST /chat      │  POST /auth/login│  GET /ops/queue          │
│  GET /driver/*   │                  │  GET /ops/holds          │
│                  │                  │  GET /ops/escalations    │
│                  │                  │  GET /ops/threads        │
│                  │                  │  GET /dashboard          │
└──────────────────┴──────────────────┴──────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT ORCHESTRATION                          │
│                     (app/agent.py)                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ LLM: OpenRouter (Claude/Gemini/GPT-4)                      │ │
│  │ Framework: LangChain + LangGraph (ReAct Agent)             │ │
│  │ System Prompt: Detailed rules, priorities, boundaries      │ │
│  │ Tools: 7 deterministic functions (no AI guessing)          │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
              ↓                               ↓
    ┌─────────────────────┐      ┌──────────────────────────┐
    │  PERSISTENT STORAGE │      │  TRANSIENT STATE        │
    │  (Supabase)         │      │  (Redis)                │
    ├─────────────────────┤      ├──────────────────────────┤
    │ • Drivers           │      │ • Slot Holds            │
    │ • Shipments         │      │ • Conversation Memory   │
    │ • Facilities        │      │ • Session State         │
    │ • Appointment Slots │      │ • Rate Limiting         │
    │ • Appointments      │      └──────────────────────────┘
    │ • ETA Updates       │
    │ • Chat Threads      │
    │ • Chat Messages     │
    │ • Escalations       │
    └─────────────────────┘
```

### Component Interaction Flow

```
Driver Message
    ↓
[Web/Chat UI] ──POST /chat────→ [FastAPI Server]
    ↑                                 ↓
    ←─── Response ←────────── [Agent Orchestrator]
                                    ↙ ↓ ↘
                    ┌─────────────┴──┴──┴──────────┐
                    ↓                               ↓
            [Database Queries]              [Tool Invocations]
            • Get Driver Info               1. lookup_driver_context
            • Get Shipments                 2. get_feasible_slots_tool
            • Check Appointments            3. hold_slot_tool
            • Verify ETA                    4. confirm_booking_tool
            • Log Escalations               5. release_hold_tool
                                            6. escalate_to_human
                                            7. get_ops_summary
                    ↓                               ↓
            [Supabase]                      [Redis] + [Supabase]
            (Facts)                         (Decisions)
```

---

---

## 🎬 Master Demo Flow — From Driver Message to Confirmed Booking

> **Purpose:** This is the primary flow to use when demonstrating SetuHaul to a
> Tech Lead, interviewer, architect, or buyer.
>
> It connects the **user-visible behavior → API → LLM → tools → deterministic
> business logic → Redis concurrency protection → database persistence → Ops
> verification**.
>
> All code references are relative to the repository root:
>
> `SetuHaul/`

### The Demo Scenario

The driver sends:

> **"I'm stuck in traffic and will be 90 minutes late. Can you find me another slot?"**

---

### Master Flow

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ① DRIVER / CHAT UI                                  │
│                                                                             │
│  Driver: "I'm stuck in traffic and will be 90 minutes late."               │
│                                                                             │
│  KEY FEATURE: Natural-language exception reporting                          │
│  DEMO: Show the message being entered in chat.html                         │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    │ POST /chat
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ② FASTAPI ENTRY POINT                               │
│                                                                             │
│  app/main.py                                                               │
│                                                                             │
│  Receives: driver_id + message                                             │
│  Creates/retrieves conversation context                                    │
│  Routes request to Agent Orchestrator                                      │
│                                                                             │
│  KEY FEATURE: Controlled API boundary                                      │
│  DEMO: Open app/main.py → show /chat handler                               │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ③ AGENT ORCHESTRATOR                                │
│                                                                             │
│  app/agent.py                                                              │
│                                                                             │
│  LLM + LangChain/LangGraph                                                 │
│                                                                             │
│  • Understand driver intent                                                │
│  • Maintain conversation context                                           │
│  • Select the appropriate deterministic tool                               │
│  • Follow operational boundaries                                           │
│                                                                             │
│  IMPORTANT: LLM does NOT decide which slot to allocate                     │
│  IMPORTANT: LLM does NOT directly modify DB/Redis                          │
│                                                                             │
│  KEY FEATURE: AI orchestration with deterministic backend boundaries        │
│  DEMO: Open app/agent.py → show SYSTEM_PROMPT / tool binding               │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    │ Tool invocation
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ④ DRIVER / SHIPMENT CONTEXT                         │
│                                                                             │
│  app/tools.py                                                              │
│  lookup_driver_context                                                     │
│                                                                             │
│  Fetches authoritative operational facts:                                  │
│  • Driver                                                                   │
│  • Shipment                                                                  │
│  • Current ETA                                                               │
│  • Priority                                                                  │
│  • Required dock type                                                        │
│  • Existing appointment                                                      │
│                                                                             │
│  SOURCE OF FACTS: Supabase / PostgreSQL                                    │
│                                                                             │
│  KEY FEATURE: Agent reasons from system facts, not assumptions             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
╔═════════════════════════════════════════════════════════════════════════════╗
║                    ⑤ DETERMINISTIC FEASIBILITY                             ║
║                                                                             ║
║  app/feasibility.py                                                        ║
║  validate_slot_against_current_state()                                     ║
║                                                                             ║
║  Every candidate slot is checked against hard constraints:                 ║
║                                                                             ║
║  ✓ Slot exists                                                             ║
║  ✓ Slot is OPEN                                                            ║
║  ✓ Slot is not already booked                                              ║
║  ✓ Dock type is compatible                                                 ║
║  ✓ Unload duration fits                                                    ║
║  ✓ Facility is accepting appointments                                     ║
║  ✓ No current appointment conflict                                         ║
║                                                                             ║
║  OUTPUT: Feasible / Rejected + auditable reason codes                      ║
║                                                                             ║
║  KEY FEATURE: LLM cannot bypass operational constraints                    ║
║  DEMO: Open app/feasibility.py and show the validation functions            ║
╚═══════════════════════════════════════╤═════════════════════════════════════╝
                                        │
                                        │ Feasible candidates
                                        ▼
╔═════════════════════════════════════════════════════════════════════════════╗
║                         ⑥ ALLOCATION / PRIORITY                             ║
║                                                                             ║
║  app/allocation.py                                                         ║
║  score_slot() / allocate_slot()                                            ║
║                                                                             ║
║  Feasible ≠ Preferred                                                       ║
║                                                                             ║
║  The allocation policy ranks feasible candidates using deterministic       ║
║  business rules.                                                           ║
║                                                                             ║
║  Priority examples:                                                        ║
║      CRITICAL = 100                                                        ║
║      HIGH     = 75                                                         ║
║      NORMAL   = 50                                                         ║
║      LOW      = 25                                                         ║
║                                                                             ║
║  Additional scoring considers time-fit and congestion cost.                ║
║                                                                             ║
║  OUTPUT: Ranked slots + allocation reasoning                               ║
║                                                                             ║
║  KEY FEATURE: Explainable deterministic allocation                          ║
║  DEMO: Open app/allocation.py → show score_slot / allocate_slot             ║
╚═══════════════════════════════════════╤═════════════════════════════════════╝
                                        │
                                        │ Ranked options
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ⑦ OPTIONS RETURNED TO DRIVER                        │
│                                                                             │
│  app/tools.py                                                              │
│  get_feasible_slots_tool                                                   │
│                                                                             │
│  Example:                                                                   │
│                                                                             │
│    Rank 1 → 14:00 → Score 95.5 → "CRITICAL + earliest fit"                 │
│    Rank 2 → 15:30 → Score 78.0                                             │
│    Rank 3 → 17:00 → Score 70.0                                             │
│                                                                             │
│  IMPORTANT: Agent receives pre-ranked options.                              │
│  Agent cannot override the allocation ranking.                             │
│                                                                             │
│  KEY FEATURE: Explainable slot recommendations                              │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    │ Driver selects slot
                                    ▼
╔═════════════════════════════════════════════════════════════════════════════╗
║                       ⑧ CONFIRMATION BOUNDARY                              ║
║                                                                             ║
║  app/tools.py                                                              ║
║  confirm_booking_tool()                                                    ║
║                                                                             ║
║                   DO NOT TRUST OLD AVAILABILITY                            ║
║                                                                             ║
║  REVALIDATION #1                                                           ║
║       ↓                                                                     ║
║  validate_slot_against_current_state()                                     ║
║                                                                             ║
║  REVALIDATION #2                                                           ║
║       ↓                                                                     ║
║  Verify Redis hold still exists                                             ║
║                                                                             ║
║  If either fails → reject stale request + return alternatives               ║
║                                                                             ║
║  KEY FEATURE: Protects against stale state / TOCTOU race                   ║
║  DEMO: Show the revalidation section inside confirm_booking_tool            ║
╚═══════════════════════════════════╤═════════════════════════════════════════╝
                                    │
                                    │ Validation passes
                                    ▼
╔═════════════════════════════════════════════════════════════════════════════╗
║                         ⑨ REDIS ATOMIC HOLD                                 ║
║                                                                             ║
║  app/redis_client.py                                                       ║
║  hold_slot / atomic SET NX EX                                              ║
║                                                                             ║
║                     SLOT = LIMITED RESOURCE                                ║
║                                                                             ║
║              Driver A                 Driver B                              ║
║                 │                        │                                  ║
║                 ▼                        ▼                                  ║
║             SET NX                   SET NX                                ║
║                 │                        │                                  ║
║              SUCCESS                    FAIL                                ║
║                 │                        │                                  ║
║                 ▼                        ▼                                  ║
║               HOLD                 "Slot unavailable"                      ║
║                                                                             ║
║  Hold TTL: 120 seconds                                                     ║
║                                                                             ║
║  KEY FEATURE: Atomic concurrency protection                                ║
║  DEMO: Show Redis key / SET NX EX behavior                                  ║
╚═══════════════════════════════════╤═════════════════════════════════════════╝
                                    │
                                    │ Hold acquired
                                    ▼
╔═════════════════════════════════════════════════════════════════════════════╗
║                         ⑩ DATABASE COMMIT                                   ║
║                                                                             ║
║  app/database.py                                                          ║
║  book_appointment()                                                        ║
║                                                                             ║
║  • Check for existing appointment                                          ║
║  • Prevent duplicate retry                                                 ║
║  • Create / return appointment                                              ║
║  • Persist ETA update                                                       ║
║                                                                             ║
║  DATABASE = PERSISTENT BUSINESS STATE                                      ║
║                                                                             ║
║  KEY FEATURE: Idempotent booking                                           ║
║  DEMO: Show existing-appointment check                                     ║
╚═══════════════════════════════════╤═════════════════════════════════════════╝
                                    │
                                    │ Booking persisted
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ⑪ RELEASE TEMPORARY HOLD                            │
│                                                                             │
│  app/tools.py                                                              │
│  release_hold_tool()                                                       │
│                                                                             │
│  Redis temporary protection is released because the booking is now         │
│  represented by persistent database state.                                 │
│                                                                             │
│  KEY FEATURE: Temporary concurrency state → persistent business state       │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ⑫ CONFIRMED BOOKING                                │
│                                                                             │
│  Driver receives confirmation                                              │
│                                                                             │
│  DB contains appointment                                                   │
│  Redis hold released                                                       │
│  ETA update persisted                                                       │
│                                                                             │
│  KEY FEATURE: End-to-end automated exception resolution                    │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ⑬ OPS VERIFICATION                                  │
│                                                                             │
│  GET /ops/verify/{shipment_id}                                             │
│                                                                             │
│  Verify:                                                                    │
│  • Actual DB appointment                                                    │
│  • Latest ETA                                                               │
│  • Active Redis holds                                                       │
│  • Final booking verdict                                                    │
│                                                                             │
│  KEY FEATURE: Operational auditability / independent verification          │
│  DEMO: Open Ops Dashboard → verify the booking                             │
└─────────────────────────────────────────────────────────────────────────────┘


## Technology Stack

### Backend

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Web Framework** | FastAPI 0.115.0 | REST API server, request routing |
| **LLM Provider** | OpenRouter API | Unified interface to Claude, Gemini, GPT-4 |
| **Agent Framework** | LangChain + LangGraph | ReAct agent orchestration, tool management |
| **Database** | Supabase (PostgreSQL) | Persistent storage, relational data |
| **Cache/State** | Redis 5.0.8 | Slot holds, conversation memory, rate limiting |
| **Server** | Uvicorn 0.30.6 | ASGI application server |
| **Language** | Python 3.11.9 | All backend code |

### Frontend

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Chat Interface** | HTML5 + Vanilla JS | Driver messaging UI |
| **Login Portal** | HTML5 + Vanilla JS | Driver authentication |
| **Dashboard** | HTML5 + Vanilla JS | Operations visibility |
| **Styling** | Inline CSS (Dark theme) | SetuHaul brand colors |

### DevOps & Deployment

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Hosting** | Heroku (or similar) | Cloud application hosting |
| **Process Manager** | Procfile | Application startup configuration |
| **Version Control** | Git + GitHub | Code versioning |
| **Environment Management** | .env file | Configuration secrets |

### Observability & Monitoring

| Tool | Purpose |
|------|---------|
| **LangSmith** | Trace every agent step, see reasoning, debug decisions |
| **Uvicorn Logging** | Server-side request/response logging |
| **Supabase Dashboard** | Monitor database performance, queries |
| **Redis CLI** | Inspect active holds and conversation state |

---

## System Components

### 1. Web Server (`app/main.py`)

**Purpose**: HTTP request handling, route dispatch, response formatting

**Key Responsibilities**:
- Receive driver chat messages
- Route to agent for processing
- Return agent response to client
- Serve frontend files (HTML)
- Expose operations API endpoints
- Manage driver authentication

**Startup Behavior**:
- Logs all registered routes for debugging
- Verifies critical endpoints are available
- Confirms Supabase connectivity

### 2. Agent Orchestrator (`app/agent.py`)

**Purpose**: Conversational AI engine for exception handling

**Key Components**:
- **System Prompt** — Detailed behavioral rules (80+ lines)
  - Defines agent's responsibilities
  - Specifies when to escalate vs. resolve
  - Sets language/tone expectations
  - Mandates fact-checking from database
  
- **LLM Configuration**
  - Model: OpenRouter (configurable)
  - Temperature: 0 (deterministic)
  - Max Tokens: 1000 (brief responses)
  - Timeout: 30 seconds

- **Message History Management**
  - Loads conversation history from Redis
  - Converts to LangChain message objects
  - Maintains context across turns
  - Expires after 1 hour of inactivity

- **Execution Engine**
  - Uses LangGraph ReAct pattern
  - Agent thinks → picks tool → observes → thinks again
  - Maximum iterations: agent-defined
  - Tool calls are deterministic (no LLM guessing inside tools)

### 3. Tools Module (`app/tools.py`)

**Purpose**: Agent's interface to the real world

**7 Available Tools**:

| # | Tool | Purpose | Parameters | Returns |
|---|------|---------|-----------|---------|
| 1 | `lookup_driver_context` | Get driver & shipment facts | `driver_id` | Driver, shipments, ETA, status |
| 2 | `get_feasible_slots_tool` | Find available slots | `shipment_id`, `facility_id`, `after_eta_ts`, `dock_type` | List of 5 slots (time, dock, type) |
| 3 | `hold_slot_tool` | Reserve slot (2 min hold) | `slot_id`, `shipment_id`, `driver_id` | Success/failure, expiry time |
| 4 | `confirm_booking_tool` | Finalize appointment | `slot_id`, `shipment_id`, `driver_id`, `revised_eta_ts`, `eta_confidence`, `eta_note` | Appointment ID, status |
| 5 | `release_hold_tool` | Cancel hold | `slot_id`, `shipment_id` | Success/failure |
| 6 | `escalate_to_human` | Route to human | `shipment_id`, `driver_id`, `thread_id`, `reason`, `urgency` | Escalation ID, ticket reference |
| 7 | `get_ops_summary` | Get facility status | None (queries all /ops/* endpoints) | Queue counts, holds, escalations, threads |

### 4. Database Layer (`app/database.py`)

**Purpose**: Supabase PostgreSQL persistence and queries

**Responsibilities**:
- Fetch/verify driver data
- Query shipments and appointments
- Record ETA updates
- Save escalations
- Book appointments
- Manage chat threads
- All operations use Supabase RLS (Row-Level Security)

### 5. Redis Client (`app/redis_client.py`)

**Purpose**: Transient state management and concurrency control

**Two Key Features**:

**a) Slot Holds**
- Soft locks that prevent race conditions
- Atomic SET with NX (exists check) + EX (expiry)
- 2-minute expiry (120 seconds)
- Only one driver can hold a slot at a time
- Release on booking or cancellation

**b) Conversation Memory**
- Stores full message history per thread
- 1-hour expiry (3600 seconds)
- Loaded on each agent turn
- Enables context retention
- Cleared when thread closes

**Race Condition Prevention**:
```
Scenario: Two drivers pick the same slot simultaneously
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Driver A: hold_slot(SLOT-123)        Driver B: hold_slot(SLOT-123)
          ↓                                        ↓
  Redis SET NX → SUCCESS              Redis SET NX → FAIL
  (lock acquired)                     (already held by A)
          ↓                                        ↓
  Query DB for appointment            Return to driver B:
  (no record yet)                     "Slot being processed"
          ↓                                        ↓
  Book appointment                    Offer different slot
  Release hold from Redis
```

---

**Flow**:
1. Create/retrieve chat thread
2. Load conversation history from Redis
3. Invoke agent with all messages
4. Agent uses tools to check facts and make decisions
5. Save new messages to database and Redis
6. Return response to client

---

#### **GET /driver/shipments/{driver_id}**
Get all active shipments for a driver (shown in chat UI banner)

**Response**:
```json
{
  "shipments": [
    {
      "shipment_id": "SHP1006",
      "cargo_desc": "Electronics",
      "current_status": "IN_TRANSIT",
      "destination": "Jaipur Hub",
      "priority_code": "HIGH"
    }
  ],
  "count": 1
}
```

---

### Authentication Endpoints

#### **POST /auth/login**
Verify driver identity for portal access

**Request**:
```json
{
  "driver_id": "DRV006",
  "phone": "9876543210"
}
```

**Response (Success)**:
```json
{
  "success": true,
  "driver_id": "DRV006",
  "driver_name": "Manoj Kumar",
  "carrier_id": "CARR-001",
  "message": "Login successful"
}
```

**Validation Rules**:
- driver_id must exist in database
- phone must match database record
- driver_status must be ACTIVE
- Returns 403 if any check fails

---

### Operations Dashboard Endpoints

#### **GET /ops/queue**
Real-time shipment status (for dashboard widget)

**Response**:
```json
{
  "shipments": [
    {
      "shipment_id": "SHP1006",
      "driver_id": "DRV006",
      "current_status": "IN_TRANSIT",
      "priority_code": "HIGH",
      "required_dock_type": "STANDARD",
      "cargo_desc": "Electronics",
      "destination_facility_id": "FAC-JAI-01"
    }
  ],
  "count": 1
}
```

**Data Included**: IN_TRANSIT, WAITING, IN_DOCK, ASSIGNED shipments

---

#### **GET /ops/holds**
Show all active slot holds (negotiations in progress)

**Response**:
```json
{
  "active_holds": [
    {
      "slot_id": "SLT-JAI-D1-001",
      "shipment_id": "SHP1006",
      "driver_id": "DRV006",
      "hold_ts": "2026-08-17T10:30:00+05:30",
      "expires_at": "2026-08-17T10:32:00+05:30"
    }
  ],
  "count": 1
}
```

**Note**: Data from Redis (not persistent after 2 min expiry)

---

#### **GET /ops/escalations**
Open escalations requiring human attention

**Response**:
```json
{
  "escalations": [
    {
      "escalation_id": "EXC-XXXXXXXX",
      "shipment_id": "SHP1006",
      "driver_id": "DRV006",
      "reason": "No feasible slots after revised ETA",
      "urgency": "HIGH",
      "reported_at": "2026-08-17T10:25:00+05:30",
      "exception_status": "OPEN"
    }
  ],
  "count": 1
}
```

---

#### **GET /ops/threads**
Active chat conversations (last 50)

**Response**:
```json
{
  "threads": [
    {
      "thread_id": "THR-XXXXXXXX",
      "driver_id": "DRV006",
      "shipment_id": "SHP1006",
      "thread_status": "OPEN",
      "thread_intent": "DELAY",
      "opened_at": "2026-08-17T10:20:00+05:30"
    }
  ],
  "count": 1
}
```

---

#### **GET /ops/slots/{facility_id}**
All slots for a facility with current status

**Response**:
```json
{
  "slots": [
    {
      "slot_id": "SLT-JAI-D1-001",
      "facility_id": "FAC-JAI-01",
      "dock_id": "DOCK-JAI-D1",
      "dock_type": "STANDARD",
      "slot_start_ts": "2026-08-17T14:00:00+05:30",
      "slot_end_ts": "2026-08-17T15:30:00+05:30",
      "slot_status": "OPEN",
      "appointments": []
    }
  ],
  "count": 6
}
```

---

#### **GET /ops/verify/{shipment_id}**
Verification endpoint: check what's actually booked (agent debugging tool)

**Response**:
```json
{
  "shipment_id": "SHP1006",
  "database_appointment": {
    "appointment_id": "APT-XXXXXXXX",
    "appointment_status": "PENDING_CONFIRMATION",
    "slot_start": "2026-08-17T14:00:00+05:30"
  },
  "latest_eta_saved": {
    "declared_eta_ts": "2026-08-17T13:45:00+05:30",
    "confidence_code": "HIGH",
    "note": "90 minutes late due to traffic"
  },
  "active_redis_holds": [],
  "verdict": "BOOKED"
}
```

**Use Case**: Ops coordinator wants to verify agent's booking was recorded correctly

---

### Frontend Endpoints

#### **GET /portal**
Driver login page (index.html)

#### **GET /portal/chat**
Driver chat interface (chat.html)

#### **GET /dashboard**
Operations dashboard (dashboard.html)

#### **GET /static/{path}**
Serve frontend assets (CSS, images, etc.)

---

## Agent Tools & Capabilities

### Tool Architecture

```
Agent asks: "Should I book this slot?"
       ↓
Agent picks tool: confirm_booking_tool(...)
       ↓
Tool (deterministic function) executes
       ↓
Tool returns structured result
       ↓
Agent observes result, reasons about next step
       ↓
Agent picks next tool or formulates response
```

**Key Principle**: Tools are **deterministic**, never guessing. They check facts from database/Redis and return what actually exists.

---

### Tool Details

#### **1. lookup_driver_context**

**Purpose**: Get everything about a driver and their shipment(s)

**When Called**: 
- First call when any driver sends message
- Before showing any slot options

**Parameters**:
- `driver_id` (string) — e.g. "DRV006"

**Returns**:
```python
{
  "driver_name": "Manoj Kumar",
  "driver_id": "DRV006",
  "carrier": "CARR-001",
  "active_shipments": [
    {
      "shipment_id": "SHP1006",
      "cargo": "Electronics",
      "priority": "HIGH",
      "status": "IN_TRANSIT",
      "destination": "Jaipur Hub",
      "facility_id": "FAC-JAI-01",
      "required_dock_type": "STANDARD",
      "current_appointment": {
        "appointment_id": "APT-XXXXXXXX",
        "status": "CONFIRMED",
        "slot_start": "2026-08-17T12:00:00+05:30"
      },
      "latest_eta": {
        "timestamp": "2026-08-17T13:45:00+05:30",
        "confidence": "HIGH",
        "note": "90 minutes late due to traffic"
      },
      "facility_checkin": {
        "gate_in_at": null,
        "queue_status": "NOT_ARRIVED"
      }
    }
  ],
  "shipment_count": 1
}
```

**Agent Logic After Calling**:
- If multiple shipments: ask driver which one
- If no appointment: option to book new slot
- If delayed: extract new ETA from latest_eta
- If at facility: different logic than in-transit

---

#### **2. get_feasible_slots_tool**

**Purpose**: Find available dock slots matching shipment requirements

**When Called**:
- After confirming shipment ID and revised ETA
- When driver agrees to look for slots

**Parameters**:
- `shipment_id` — e.g. "SHP1006"
- `facility_id` — e.g. "FAC-JAI-01"
- `after_eta_ts` — ISO format, e.g. "2026-08-17T13:45:00+05:30"
- `dock_type` — One of: STANDARD, REEFER, HEAVY

**Returns**:
```python
{
  "available": True,
  "slots": [
    {
      "slot_id": "SLT-JAI-D1-003",
      "dock_id": "DOCK-JAI-D1",
      "start_time": "17 Aug 2026 02:00 PM IST",
      "end_time": "17 Aug 2026 03:30 PM IST",
      "dock_type": "STANDARD",
      "status": "AVAILABLE"
    },
    {
      "slot_id": "SLT-JAI-D1-004",
      "dock_id": "DOCK-JAI-D1",
      "start_time": "17 Aug 2026 03:30 PM IST",
      "end_time": "17 Aug 2026 05:00 PM IST",
      "dock_type": "STANDARD",
      "status": "AVAILABLE"
    }
  ],
  "count": 2,
  "note": "Show these options to driver"
}
```

**Filters Applied**:
- Only OPEN slots
- Matching dock_type
- After the driver's revised ETA
- Excluding already-booked slots
- Excluding slots held by other drivers
- Max 5 returned, sorted by time

---

#### **3. hold_slot_tool**

**Purpose**: Reserve a slot for 2 minutes while driver decides

**When Called**:
- Before showing slot details to driver
- After driver picks a specific slot option

**Parameters**:
- `slot_id` — e.g. "SLT-JAI-D1-003"
- `shipment_id` — e.g. "SHP1006"
- `driver_id` — e.g. "DRV006"

**Returns (Success)**:
```python
{
  "success": True,
  "slot_id": "SLT-JAI-D1-003",
  "expires_in_seconds": 120,
  "message": "Slot held for 2 minutes. Please confirm quickly."
}
```

**Returns (Failure — slot already held)**:
```python
{
  "success": False,
  "reason": "Slot is being processed by another request. Please choose a different slot."
}
```

**Implementation** (Redis):
- Uses `SET key value NX EX 120` (atomic)
- If key exists, returns failure immediately
- No race condition possible
- Hold expires automatically after 2 min
- Same shipment can refresh hold

---

#### **4. confirm_booking_tool**

**Purpose**: Finalize slot booking (creates PENDING_CONFIRMATION appointment)

**When Called**:
- After driver explicitly says "YES, book this slot"
- After hold is still active

**Parameters**:
- `slot_id` — e.g. "SLT-JAI-D1-003"
- `shipment_id` — e.g. "SHP1006"
- `driver_id` — e.g. "DRV006"
- `revised_eta_ts` — ISO timestamp of new ETA
- `eta_confidence` — One of: HIGH, MEDIUM, LOW
- `eta_note` — Brief reason (e.g. "Traffic on NH-8")

**Actions**:
1. Save ETA update to database
2. Mark old appointment as not-current
3. Create new appointment with status PENDING_CONFIRMATION
4. Release Redis hold
5. Return appointment ID

**Returns**:
```python
{
  "success": True,
  "appointment_id": "APT-XXXXXXXX",
  "status": "PENDING_CONFIRMATION",
  "message": "Appointment created. Awaiting warehouse confirmation.",
  "note": "Tell driver slot is booked but pending facility sign-off"
}
```

---

#### **5. release_hold_tool**

**Purpose**: Cancel a slot hold (driver changed mind or picked different slot)

**When Called**:
- Driver rejects a slot
- Driver picks a different slot
- Conversation ends without booking
- Hold expires

**Parameters**:
- `slot_id` — e.g. "SLT-JAI-D1-003"
- `shipment_id` — e.g. "SHP1006"

**Returns**:
```python
{
  "success": True,
  "message": "Hold released"
}
```

---

#### **6. escalate_to_human**

**Purpose**: Route exception to human operations coordinator

**When Called**:
- No feasible slot exists after revised ETA
- Driver reports safety concern
- Contradictory information received
- Regulated/hazmat load
- Driver explicitly asks for human help
- Agent not confident in resolution

**Parameters**:
- `shipment_id` — e.g. "SHP1006"
- `driver_id` — e.g. "DRV006"
- `thread_id` — e.g. "THR-XXXXXXXX"
- `reason` — Explanation (e.g. "No slots available within 3 hours")
- `urgency` — One of: LOW, MEDIUM, HIGH, CRITICAL

**Returns**:
```python
{
  "success": True,
  "escalation_id": "EXC-XXXXXXXX",
  "urgency": "HIGH",
  "message": "Escalated to human ops team. Reference: EXC-XXXXXXXX. A coordinator will contact you shortly."
}
```

**Backend Action**:
- Saves to driver_exceptions table
- Triggers email to operations team
- Shows escalation ID on ops dashboard
- Marks thread for manual follow-up

---

#### **7. get_ops_summary**

**Purpose**: Answer operational questions (for ops staff via admin chat)

**When Called**:
- Someone (from ops dashboard) asks "How many escalations?"
- Questions like "Current facility load?"

**Parameters**: None

**Returns**:
```python
{
  "success": True,
  "timestamp": "2026-08-17T10:30:00+05:30",
  "queue": {
    "in_transit_count": 12,
    "waiting_count": 3,
    "in_dock_count": 2,
    "total_shipments": 17
  },
  "holds": {
    "active_holds_count": 1,
    "active_holds": [
      {
        "slot_id": "SLT-JAI-D1-003",
        "shipment_id": "SHP1006",
        "held_by_driver": "DRV006",
        "held_since": "2026-08-17T10:28:00+05:30",
        "expires_at": "2026-08-17T10:30:00+05:30"
      }
    ]
  },
  "escalations": {
    "open_escalations_count": 2,
    "open_escalations": [...]
  },
  "threads": {
    "open_threads_count": 5,
    "total_threads": 23,
    "open_threads": [...]
  }
}
```

**Implementation**:
- Calls all `/ops/*` endpoints via HTTP
- Aggregates results
- Uses `API_BASE_URL` from environment (production-ready)
- Graceful error handling if API unavailable

---

## Data Flows

### Flow 1: Driver Sends Delay Message

```
ACTOR: Driver (in traffic, going to be late)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Driver types message
   ├─ "I'm stuck in traffic, 2 hours late"
   └─ Sends to chat interface

2. Chat UI → POST /chat
   ├─ Payload: {driver_id: "DRV006", message: "..."}
   └─ Browser sends to fastapi.setuhaul.com/chat

3. FastAPI Server (main.py)
   ├─ Receives POST /chat
   ├─ Calls get_or_create_thread(driver_id)
   ├─ Invokes run_agent(driver_id, message)
   └─ Returns ChatResponse to client

4. Agent Orchestrator (agent.py)
   ├─ Gets conversation history from Redis
   ├─ Builds LangChain message list
   ├─ Calls LLM via OpenRouter
   ├─ LLM returns tool choice
   └─ Loops through tool invocations

5. Agent Tool 1: lookup_driver_context
   ├─ Queries Supabase: drivers.select(*) where driver_id="DRV006"
   ├─ Queries Supabase: shipments where driver_id="DRV006"
   ├─ Gets current appointment and latest ETA
   └─ Returns driver facts to agent

6. Agent Reasoning
   ├─ Sees driver has shipment SHP1006 at Jaipur Hub
   ├─ Current appointment: 12:00 PM (now 2:00 PM — MISSED)
   ├─ Driver claims 2 hour delay
   ├─ Agent calculates new ETA: 2:00 PM + 2 hours = 4:00 PM
   └─ Decision: Find slots after 4:00 PM

7. Agent Tool 2: get_feasible_slots_tool
   ├─ Params: facility_id="FAC-JAI-01", dock_type="STANDARD", after_eta="2026-08-17T16:00:00+05:30"
   ├─ Queries DB: slots where facility_id=... AND dock_type=... AND slot_start_ts >= ...
   ├─ Filters out already-booked slots
   ├─ Filters out slots held by other drivers (from Redis)
   └─ Returns 2-3 available slots

8. Agent Tool 3: hold_slot_tool
   ├─ Picks first slot: SLT-JAI-D1-003 (4:00 PM - 5:30 PM)
   ├─ Calls hold_slot_tool(slot_id, shipment_id, driver_id)
   ├─ Redis SET key=hold:SLT-JAI-D1-003 value={...} NX EX 120
   ├─ Returns success
   └─ Slot now reserved for this driver for 2 minutes

9. Agent Response Generation
   ├─ Composes message: "Manoj, I found a slot at 4:00 PM (Dock 1). Does this work?"
   ├─ Includes slot details, confirms hold expires in 2 min
   └─ Ready for return

10. Response Saved to Storage
    ├─ Save to Redis: conversation:{thread_id} = [all messages + new response]
    ├─ Save to Supabase: chat_messages with sender_type="AGENT"
    └─ Conversation expires after 1 hour

11. Response Returned to Client
    ├─ ChatResponse: {driver_id, response, thread_id}
    └─ UI displays: "Hi Manoj, I found a slot..."

12. Driver sees options and responds
    └─ NEXT LOOP: Driver says "Yes, book that slot"
```

---

### Flow 2: Driver Confirms Booking

```
ACTOR: Driver (accepting the new slot)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Driver responds: "Yes, confirm that 4 PM slot"

2. Chat UI → POST /chat
   └─ Same as before

3. Agent loads conversation from Redis
   ├─ Sees previous exchange
   ├─ Knows which slot was shown (SLT-JAI-D1-003)
   ├─ Knows hold is still active (< 2 min)
   └─ Interprets "Yes" as confirmation

4. Agent Tool 4: confirm_booking_tool
   ├─ Calls with:
   │  ├─ slot_id = "SLT-JAI-D1-003"
   │  ├─ shipment_id = "SHP1006"
   │  ├─ driver_id = "DRV006"
   │  ├─ revised_eta_ts = "2026-08-17T16:00:00+05:30"
   │  ├─ eta_confidence = "HIGH"
   │  └─ eta_note = "Driver reported traffic, 2 hour delay"
   └─ Tool execution:

5. Inside confirm_booking_tool
   ├─ Save ETA update to database
   │  └─ INSERT into eta_updates (eta_update_id, shipment_id, declared_eta_ts, ...)
   │
   ├─ Mark old appointment as not-current
   │  └─ UPDATE appointments SET is_current=0 WHERE shipment_id="SHP1006" AND is_current=1
   │
   ├─ Create new appointment
   │  └─ INSERT into appointments (
   │      appointment_id="APT-XXXXXXXX",
   │      shipment_id="SHP1006",
   │      slot_id="SLT-JAI-D1-003",
   │      appointment_status="PENDING_CONFIRMATION",
   │      booking_source="DRIVER_CHAT",
   │      is_current=1,
   │      booked_at=now
   │     )
   │
   ├─ Release Redis hold
   │  └─ DEL hold:SLT-JAI-D1-003
   │
   └─ Return: success=True, appointment_id="APT-XXXXXXXX"

6. Agent Response
   ├─ Composes message: "Done! Your new slot is booked for 4:00 PM at Dock 1. Warehouse will confirm shortly."
   └─ Informs driver: status is PENDING_CONFIRMATION (not final yet)

7. Storage Update
   ├─ Save response to Redis and Supabase
   └─ Conversation continues

8. Ops Notification
   ├─ Dashboard shows: APT-XXXXXXXX status=PENDING_CONFIRMATION
   ├─ Warehouse manager gets notification (manual system)
   └─ Either CONFIRMS or REJECTS the appointment

END: Booking is now in system, awaiting warehouse confirmation
```

---

### Flow 3: No Slots Available (Escalation)

```
ACTOR: Driver (urgent delivery, ETA pushed back significantly)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Driver: "I won't make it. Vehicle broke down. ETA is now 11 PM."

2. Agent lookup_driver_context()
   └─ Gets shipment info, facility_id=FAC-JAI-01

3. Agent calculates: 
   ├─ Current ETA: 11:00 PM (23:00 IST)
   ├─ Facility closes at: 10:00 PM
   └─ Problem: No slots available after hours

4. Agent get_feasible_slots_tool()
   ├─ Query: facility_id, dock_type, after_eta_ts="2026-08-17T23:00:00+05:30"
   ├─ Result: empty list
   ├─ Reason: Facility closes at 10 PM, driver arriving at 11 PM
   └─ Response: available=False, no slots

5. Agent Decision
   ├─ Checks system prompt rules
   ├─ Finds: "ESCALATE IMMEDIATELY if no feasible slot exists"
   ├─ No slots exist for late arrival
   └─ Decision: ESCALATE

6. Agent Tool 6: escalate_to_human()
   ├─ Calls with:
   │  ├─ shipment_id="SHP1006"
   │  ├─ driver_id="DRV006"
   │  ├─ thread_id="THR-XXXXXXXX"
   │  ├─ reason="Vehicle broken down, ETA 11:00 PM. Facility closes at 10 PM."
   │  └─ urgency="CRITICAL"
   │
   ├─ Backend action:
   │  ├─ INSERT into driver_exceptions (exception_id="EXC-XXXXXXXX", ...)
   │  ├─ Trigger email: "HumanInTheLook@gmail.com"
   │  └─ Update ops dashboard
   │
   └─ Returns: escalation_id="EXC-XXXXXXXX"

7. Agent Response
   ├─ Message to driver:
   │  "Manoj, this is urgent. You'll arrive after the facility closes. 
   │   I've escalated this to our ops team. Reference: EXC-XXXXXXXX.
   │   A coordinator will call you shortly to find a solution."
   │
   └─ Save to DB and Redis

8. Ops Team Actions
   ├─ Dashboard shows escalation CRITICAL
   ├─ Ops coordinator reviews:
   │  ├─ Shipment details
   │  ├─ Driver info
   │  ├─ Failure reason
   │  └─ All conversation history
   │
   ├─ Coordinator options:
   │  ├─ Call facility manager to extend hours
   │  ├─ Find alternative facility
   │  ├─ Arrange next-day delivery
   │  └─ Call driver directly
   │
   └─ Manually update appointment or close thread

END: Human coordination required
```

---

### Flow 4: Ops Dashboard Real-Time Monitoring

```
ACTOR: Operations Manager (monitoring facility status)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Manager opens dashboard.html

2. Dashboard JavaScript:
   ├─ setInterval(loadAll, 30000) — refresh every 30 seconds
   └─ First call to loadAll()

3. loadAll() chains parallel fetches:
   ├─ fetch(/ops/queue) → Queue list, shipment statuses
   ├─ fetch(/ops/holds) → Active slots being negotiated
   ├─ fetch(/ops/escalations) → Issues needing attention
   ├─ fetch(/ops/threads) → Active driver conversations
   └─ fetch(/ops/slots/{facility_id}) → Available/booked slots

4. Dashboard Updates
   ├─ Stats Row:
   │  ├─ "In Transit: 12"
   │  ├─ "Waiting: 3"
   │  ├─ "In Dock: 2"
   │  ├─ "Active Holds: 1"
   │  ├─ "Escalations: 2" ← Red highlight if > 0
   │  └─ "Open Threads: 5"
   │
   ├─ Queue Panels:
   │  ├─ Shows top shipments by priority
   │  ├─ Color-coded by priority (RED=CRITICAL, ORANGE=HIGH)
   │  └─ Clickable cards show more details
   │
   ├─ Slot Schedule Grid:
   │  ├─ Dock-by-dock visualization
   │  ├─ Color-coded slots: OPEN|BOOKED|PROGRESS|HELD|BLOCKED
   │  ├─ IST timestamps formatted for India timezone
   │  └─ Hover shows slot details
   │
   ├─ Escalations Panel:
   │  ├─ Red background (urgent)
   │  ├─ Clickable escalation IDs
   │  ├─ Shows reason and urgency
   │  └─ Manual action buttons (resolve, contact driver)
   │
   ├─ Holds Panel:
   │  ├─ Yellow background (negotiations)
   │  ├─ Shows which driver holding which slot
   │  ├─ Time remaining on hold (countdown)
   │  └─ "Slot expires in 1 min 23 sec"
   │
   └─ Threads Panel:
       ├─ List of active driver conversations
       ├─ Click to see full chat history
       └─ Status indicators (OPEN, WAITING_FOR_DRIVER, etc.)

5. Admin Chat Widget (bottom-right)
   ├─ Button: "💬 Ask ops assistant"
   ├─ Ops staff can ask:
   │  ├─ "How many CRITICAL escalations?"
   │  ├─ "Which slots are held?"
   │  ├─ "Show me in-transit shipments"
   │  └─ Agent uses get_ops_summary to answer
   │
   └─ Uses same agent as driver chat

6. Real-Time Updates
   ├─ Every 30 seconds, all data refreshes
   ├─ Live badge pulses green
   ├─ Timestamp shown: "Updated: 10:30:45 AM"
   └─ Manager sees live facility state

BENEFIT: Full visibility without manual queries
```

---

## Workflows

### Workflow 1: Standard Delay Resolution (Happy Path)

```
┌─────────────────────────────────────────────────────────┐
│ ACTOR: Driver reporting delay                           │
└─────────────────────────────────────────────────────────┘

1. Driver sends message
   └─ "I'm 90 minutes late"

2. Agent calls lookup_driver_context
   └─ Confirms shipment, facility, dock type

3. Agent calls get_feasible_slots_tool
   └─ Finds available slots after new ETA

4. Agent calls hold_slot_tool
   └─ Reserves first viable slot (2 min hold)

5. Agent proposes slot
   └─ "I found a slot at 2:00 PM, Dock 3. Does this work?"

6. Driver responds "YES"

7. Agent calls confirm_booking_tool
   ├─ Saves ETA update
   ├─ Books appointment (PENDING_CONFIRMATION)
   ├─ Releases hold from Redis
   └─ Confirms to driver

8. Warehouse manager confirms
   └─ Appointment status changes to CONFIRMED

RESULT: Shipment re-booked, no human intervention needed ✓
TIME: 5-10 minutes total
```

---

### Workflow 2: Escalation Path (Complex Issue)

```
┌─────────────────────────────────────────────────────────┐
│ ACTOR: Driver in complex situation                      │
└─────────────────────────────────────────────────────────┘

1. Driver reports emergency
   └─ "Vehicle broken down, 4 hour delay, hazmat load"

2. Agent detects red flags
   ├─ Hazmat = requires special handling
   ├─ 4 hour delay = likely no slots
   ├─ Emergency = safety concern
   └─ Decision: ESCALATE immediately

3. Agent calls escalate_to_human
   ├─ urgency="CRITICAL"
   ├─ reason="Hazmat load + emergency delay"
   └─ Creates escalation ticket

4. Escalation recorded
   ├─ Saved to driver_exceptions table
   ├─ Shown on ops dashboard (RED)
   ├─ Email sent to operations team
   └─ Ticket ID provided to driver

5. Operations coordinator
   ├─ Reviews escalation details
   ├─ Sees full conversation history
   ├─ Calls driver directly
   ├─ Arranges alternative facility OR
   ├─ Contacts hazmat team OR
   └─ Coordinates special handling

6. Coordinator manually updates
   ├─ Books appointment or
   ├─ Schedules for next day or
   ├─ Diverts to alternate facility
   └─ Updates status in dashboard

7. Thread closed
   ├─ Driver informed of resolution
   ├─ Thread status = CLOSED
   └─ Escalation marked RESOLVED

RESULT: Complex issue handled by humans ✓
TIME: 15-60 minutes (real-time human coordination)
```

---

### Workflow 3: Rapid Hold/Release (Slot Shopping)

```
┌─────────────────────────────────────────────────────────┐
│ ACTOR: Driver comparing multiple slot options           │
└─────────────────────────────────────────────────────────┘

Turn 1: "What slots are available?"
  ├─ Agent gets 3 slots
  ├─ Holds slot 1 (for agent, 2 min)
  └─ Shows all 3 to driver

Turn 2: Driver asks "What's the difference between slot 2 and 3?"
  ├─ Agent checks: slot 1 still held (< 2 min)
  ├─ Discusses slots 2 and 3 (not holding them yet)
  └─ Slot 1 hold remains active

Turn 3: Driver says "Okay, I want slot 2"
  ├─ Agent releases hold on slot 1
  ├─ Agent holds slot 2
  └─ Confirms: "Slot 2 (3 PM - 4:30 PM) reserved for 2 min"

Turn 4: Driver confirms "Yes, book slot 2"
  ├─ Agent confirms_booking_tool(slot_id=2)
  ├─ Slot 2 booked, hold released
  └─ Appointment created

RESULT: Driver choice respected, slots protected via holds ✓
TIME: 3-5 minutes
```

---

## Deployment & Configuration

### Environment Variables (.env)

```bash
# LLM Configuration (OpenRouter — unified API to multiple models)
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=anthropic/claude-3-5-sonnet  # or gpt-4, gemini, etc.

# LangSmith (Observability - see every agent step)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_...
LANGSMITH_PROJECT=SetuHaul
LANGSMITH_ENDPOINT=https://api.smith.langchain.com

# Supabase (PostgreSQL + Auth)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=sbpk_production_xxxxx  # Service role key (server-side only)

# Redis (Session state + slot holds)
REDIS_URL=redis://user:pass@host:6379

# Deployment
API_BASE_URL=https://setuhaul-api.herokuapp.com  # Used by get_ops_summary tool
```

### Procfile (Heroku Deployment)

```bash
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Runtime

```
python-3.11.9
```

### How to Deploy (Heroku Example)

```bash
# 1. Create Heroku app
heroku create setuhaul-api

# 2. Set environment variables
heroku config:set SUPABASE_URL=...
heroku config:set SUPABASE_KEY=...
heroku config:set REDIS_URL=...
heroku config:set OPENROUTER_API_KEY=...
heroku config:set API_BASE_URL=https://setuhaul-api.herokuapp.com

# 3. Deploy
git push heroku main

# 4. Verify
heroku logs --tail
```

### Local Development

```bash
# 1. Clone repository
git clone <repo>
cd SetuHaul

# 2. Create .env from .env.example
cp .env.example .env
# Edit .env with local keys

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. Open browser
# Chat UI: http://localhost:8000/portal/chat
# Dashboard: http://localhost:8000/dashboard
# API: http://localhost:8000/docs (Swagger UI)
```

---

## Frontend Architecture

### 1. Login Portal (index.html)

**Purpose**: Driver authentication

**Components**:
- Driver ID input
- Phone number input (verification)
- Login button
- Error messaging

**Flow**:
```
User enters ID + phone
    ↓
POST /auth/login
    ↓
Backend verifies against database
    ↓
Success: Redirect to /portal/chat
Failure: Show error message
```

---

### 2. Chat Interface (chat.html)

**Purpose**: Driver-to-Agent conversation

**Components**:
- Driver banner (name, shipment details)
- Message history
- Input box + Send button
- Status indicators

**Features**:
- Real-time message display
- Typing indicators (if implemented)
- Slot options rendered as cards
- Clickable confirmations
- Error handling

**Flow**:
```
Driver types message
    ↓
Click "Send" or press Enter
    ↓
POST /chat {driver_id, message}
    ↓
Disable input while processing
    ↓
Receive response
    ↓
Display message + any options
    ↓
Re-enable input
```

---

### 3. Operations Dashboard (dashboard.html)

**Purpose**: Real-time facility monitoring

**Sections**:

**a) Header**
- SetuHaul logo
- Title: "SetuHaul Ops Dashboard"
- Last updated timestamp
- Live badge (green pulsing dot)
- Refresh button

**b) Stats Row**
- In Transit: X trucks
- Waiting: Y trucks
- In Dock: Z trucks
- Active Holds: H slots being negotiated
- Escalations: E issues (RED if > 0)
- Open Threads: T active conversations

**c) Queue Panels (3 columns)**
- In Transit shipments
- Waiting shipments
- In Dock shipments

**d) Slot Schedule Grid**
- Dock-by-dock visualization
- Time-based slot view
- Color-coded statuses
- IST formatting for India timezone

**e) Escalations Panel** (Red)
- List of open issues
- Urgency color-coded
- Clickable for details
- Action buttons

**f) Holds Panel** (Yellow)
- Slots being negotiated
- Driver + shipment info
- Time remaining (countdown)
- Release option

**g) Threads Panel**
- Active conversations
- Driver info
- Status indicators
- View history

**h) Admin Chat Widget** (Bottom-right)
- Floating button: 💬
- Opens chat box
- Can ask agent questions about facility state
- Uses same agent as driver chat

**Refresh Behavior**:
```
Page loads
    ↓
JavaScript: setInterval(loadAll, 30000)
    ↓
Every 30 seconds:
  ├─ fetch(/ops/queue)
  ├─ fetch(/ops/holds)
  ├─ fetch(/ops/escalations)
  ├─ fetch(/ops/threads)
  └─ fetch(/ops/slots/{facility_id})
    ↓
Update all panels
    ↓
Timestamp updated: "Updated: 10:30:45 AM"
```

---

## Key Concepts & Terminology

### Status States

#### **Shipment Status**
- `ASSIGNED` — Assigned to driver, not yet in transit
- `IN_TRANSIT` — Driver on road, heading to facility
- `WAITING` — Arrived at facility, waiting for slot
- `IN_DOCK` — Currently unloading
- `DELIVERED` — Unloading complete, departed

#### **Appointment Status**
- `CONFIRMED` — Warehouse signed off, locked in
- `PENDING_CONFIRMATION` — Booked by agent, awaiting warehouse approval
- `IN_PROGRESS` — Truck actively unloading
- `CANCELLED` — Cancelled by driver or ops

#### **Thread Status**
- `OPEN` — Active conversation
- `CLOSED` — Conversation ended
- `WAITING_FOR_DRIVER` — Awaiting driver response
- `WAITING_FOR_WAREHOUSE` — Awaiting facility confirmation

#### **Escalation Status**
- `OPEN` — Unresolved, needs attention
- `RESOLVED` — Human coordinator took action
- `DISMISSED` — False alarm, no action needed

---

### Priority Levels

| Level | Use Case | Examples |
|-------|----------|----------|
| `CRITICAL` | Emergency, time-sensitive | Vehicle broken down, hazmat issue |
| `HIGH` | Urgent, same-day delivery | High-value shipment, customer priority |
| `NORMAL` | Standard delivery | Majority of shipments |
| `LOW` | Flexible timing | Non-urgent bulk cargo |

**Agent Priority Policy**:
- CRITICAL shipments get first access to available slots
- All other factors equal, prioritize by level
- Physical arrival doesn't displace a CONFIRMED appointment

---

### Dock Types

| Type | Purpose | Examples |
|------|---------|----------|
| `STANDARD` | General cargo | Electronics, textiles, machinery |
| `REEFER` | Temperature controlled | Pharmaceuticals, perishables, frozen goods |
| `HEAVY` | Heavy/specialized equipment | Industrial machinery, construction materials |

---

### Confidence Levels

| Level | Definition | When Used |
|-------|-----------|----------|
| `HIGH` | Driver certain of arrival time | Traffic cleared, vehicle repaired |
| `MEDIUM` | Estimated based on conditions | Traffic ongoing but stabilizing |
| `LOW` | Highly uncertain | Vehicle issue, major delays |

**Agent Uses**:
- Confidence influences slot selection (HIGH confidence = farther slot OK)
- Included in ETA record for warehouse coordination

---

### Key Timing Windows

| Element | Duration | Notes |
|---------|----------|-------|
| Redis Slot Hold | 120 seconds (2 min) | Expires automatically |
| Conversation Memory | 3600 seconds (1 hour) | Expires if driver inactive |
| API Request Timeout | 30 seconds | Agent waits max 30s for LLM |
| Dashboard Refresh | 30 seconds | Auto-refresh for ops |
| Escalation TTL | N/A | Stays until human resolves |

---

### Race Condition Prevention

**Problem**: Two drivers request same slot simultaneously

**Solution**: Redis atomic SET with NX (not-exists) flag

```
Driver A and Driver B both want slot SLOT-123
    ↓
Redis command: SET hold:SLOT-123 value NX EX 120
    ↓
Execution sequence:
    Driver A: SET → SUCCESS (key created)
    Driver B: SET → FAIL (key already exists)
    ↓
Driver A: Can proceed with booking
Driver B: Offered alternative slot
```

**Why this works**:
- Redis SET NX is atomic (not two separate operations)
- No race window between check and set
- Timeout prevents permanent locks
- Same shipment can refresh hold

---

### Language & Tone Philosophy

**Driver-Facing**:
- Casual, friendly tone (not corporate)
- Understands Hinglish (Hindi-English mix)
- Brief responses (drivers on road)
- Clear next steps
- Acknowledges urgency

**Example**:
```
Good: "Manoj, I see. 2 hours late, okay. 
       I found a slot at 3:00 PM. Will that work?"

Bad:  "NOTIFICATION: Appointment status has been modified. 
       Please acknowledge the new temporal coordinate."
```

**Operations-Facing**:
- Professional, data-focused
- Technical details
- Clear escalation reasons
- Actionable information

**System Prompt Principle**: "NEVER GUESS. Check facts from database. If unknown, ASK the driver."

---

### Decision Authority Matrix

| Decision | Authority | Notes |
|----------|-----------|-------|
| Book slot (driver agrees) | **Agent** | Automatic, creates PENDING_CONFIRMATION |
| Confirm appointment | **Warehouse Manager** | Via dashboard/manual system |
| Escalate issue | **Agent** | Per system prompt rules |
| Offer compensation | **Human Only** | Agent explicitly prohibited |
| Override safety decision | **Human Only** | Driver+Carrier+Ops team |
| Release all holds | **Agent or Human** | Hold expires auto or manual release |

---

## API Response Codes & Error Handling

### Success Responses

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | GET /ops/queue returns shipment list |
| 201 | Created | POST /chat creates thread |

### Error Responses

| Code | Meaning | Example |
|------|---------|---------|
| 400 | Bad Request | Missing driver_id in /chat POST |
| 403 | Forbidden | Driver phone doesn't match login attempt |
| 404 | Not Found | Driver ID doesn't exist in database |
| 500 | Server Error | Database connection failure |

### Tool Response Patterns

All agent tools return structured JSON:

**Success Pattern**:
```json
{
  "success": true,
  "data": {...},
  "message": "Human-readable message"
}
```

**Failure Pattern**:
```json
{
  "success": false,
  "error": "Reason for failure",
  "message": "User-facing message"
}
```

---

## Performance Considerations

### Latency Budget

| Operation | Target | Timeout |
|-----------|--------|---------|
| Driver message to response | < 5 sec | 30 sec (LLM call) |
| Database query | < 100 ms | 5 sec |
| Redis operation | < 10 ms | 1 sec |
| Slot search | < 500 ms | 5 sec |

### Scalability

- **Supabase**: Handles 10,000+ drivers, millions of records
- **Redis**: In-memory, ultra-fast, 10K+ concurrent holds
- **Fastapi**: Async-first, can handle 1000+ req/sec per instance
- **LLM API**: Rate-limited by OpenRouter (plan-dependent)

### Database Indexes

Required indexes for performance:
- `shipments(driver_id, current_status)`
- `appointments(shipment_id, is_current)`
- `appointment_slots(facility_id, dock_type, slot_start_ts)`
- `chat_threads(driver_id, thread_status)`
- `driver_exceptions(exception_status, reported_at)`

---

## Security & Data Protection

### Sensitive Data Handling

- **Driver Phone**: Verified at login, not logged in conversations
- **Shipment Details**: Only shown to assigned driver
- **Database Credentials**: In .env, never in code
- **API Keys**: Rotated regularly, different per environment

### Access Control

- Supabase RLS (Row-Level Security) enforces driver can only see own shipments
- API endpoints require valid driver_id (basic validation)
- No authentication token (future: add JWT)
- All database writes include audit fields (created_at, updated_at)

### Data Retention

- Chat messages: Kept in Supabase indefinitely
- Conversation memory: Expires after 1 hour (Redis)
- Slot holds: Auto-expire after 2 minutes (Redis)
- Escalations: Kept until resolved (manual cleanup)

---

## Future Enhancements

### Planned Features

1. **JWT Authentication**
   - Replace phone verification with tokens
   - Session management for web portals

2. **SMS/WhatsApp Integration**
   - Multi-channel support beyond web chat
   - SMS alerts for status changes

3. **Google Maps Integration**
   - Real-time GPS tracking
   - ETA auto-calculation from location

4. **Warehouse Integration APIs**
   - Direct appointment confirmation (eliminate manual approval)
   - Real-time dock availability feeds

5. **Advanced Analytics**
   - Delay patterns by route/season
   - Driver performance metrics
   - Facility utilization reports

6. **Multi-Language Support**
   - Telugu, Tamil, Kannada for broader India coverage
   - Hinglish remains primary

7. **Predictive Delays**
   - ML model to predict delays before driver reports
   - Proactive slot pre-booking

---

## Troubleshooting Guide

### Issue: "Driver not found"
**Cause**: Incorrect driver_id or typo  
**Fix**: Verify driver_id in database, check spelling  
**Endpoint**: `GET /driver/{driver_id}` to debug

### Issue: "No slots available"
**Cause**: All slots booked or facility closed  
**Fix**: Check `/ops/slots/{facility_id}` to see current slots  
**Action**: Manual escalation to ops team

### Issue: "Slot hold expired"
**Cause**: Driver took > 2 minutes to confirm  
**Fix**: Agent will re-hold slot and re-offer  
**Tip**: Emphasize to driver to respond quickly

### Issue: "Appointment not appearing in database"
**Cause**: Booking failed at database layer  
**Fix**: Use `/ops/verify/{shipment_id}` to check  
**Debug**: Check agent logs in LangSmith

### Issue: "Redis connection timeout"
**Cause**: Redis server unavailable  
**Fix**: Check REDIS_URL environment variable  
**Fallback**: Slot holds fail, escalate manually

---

## Summary: What This System Does

**SetuHaul** is an **intelligent exception manager for freight logistics**:

1. **24/7 Availability**: Agent works round-the-clock
2. **Automated Rebooking**: Finds slots, holds them, books automatically
3. **Human in Loop**: Escalates when needed
4. **Real-Time Visibility**: Ops dashboard shows live facility state
5. **Data-Driven**: All decisions verified against database facts
6. **Race-Safe**: Redis prevents double-bookings
7. **Scalable**: Handles thousands of drivers and shipments

**Core Value**: Reduces operational overhead by ~80% for standard delay cases, while ensuring complex exceptions get proper human attention.

---

**Document Version**: 1.0.0  
**Last Updated**: 2026-08-17  
**Maintained By**: SetuHaul Development Team
