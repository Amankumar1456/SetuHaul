# SetuHaul — Complete Project Documentation
**Single Source of Truth for Architecture, Flows, and System Design**

*Last Updated: 2026-08-18*
*Project Version: 1.1.0*

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Overview](#architecture-overview)
3. [Technology Stack](#technology-stack)
4. [System Components](#system-components)
5. [Database Schema](#database-schema)
6. [API Endpoints](#api-endpoints)
7. [Agent Tools & Capabilities](#agent-tools--capabilities)
8. [Data Flows](#data-flows)
9. [Workflows](#workflows)
10. [Deployment & Configuration](#deployment--configuration)
11. [Frontend Architecture](#frontend-architecture)
12. [Key Concepts & Terminology](#key-concepts--terminology)
13. [Known Issues & Planned Improvements](#known-issues--planned-improvements)

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
| Drivers communicate in Hinglish/casual language | Agent understands informal messages in Hindi/English mix |

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
│  React Frontend      │  HTML Portal         │  Ops Dashboard    │
│  (Railway Service 2) │  (index.html)        │  (dashboard.html) │
│  TanStack + Nitro    │  Driver Login        │  HTML + JS        │
└──────────────────────┴──────────────────────┴───────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI WEB SERVER                            │
│              (Railway Service 1 — Python Backend)                │
├──────────────────┬──────────────────┬──────────────────────────┤
│  Chat Endpoint   │  Auth Endpoints  │  Operations Endpoints    │
│  POST /chat      │  POST /auth/login│  GET /ops/queue          │
│  POST /ops/chat  │  GET /driver/*   │  GET /ops/holds          │
│                  │                  │  GET /ops/escalations    │
│                  │                  │  GET /ops/threads        │
│                  │                  │  GET /ops/slots/{id}     │
└──────────────────┴──────────────────┴──────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT ORCHESTRATION                          │
│                     (app/agent.py)                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ LLM: Groq (llama-3.3-70b-versatile) via LangChain         │ │
│  │ Framework: LangGraph ReAct Agent                           │ │
│  │ Tracing: LangSmith                                         │ │
│  │ Tools: 6 deterministic functions (no AI guessing)          │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
              ↓                               ↓
    ┌─────────────────────┐      ┌──────────────────────────┐
    │  PERSISTENT STORAGE │      │  TRANSIENT STATE         │
    │  Supabase           │      │  Redis (WSL2 / Railway)  │
    │  (PostgreSQL)       │      ├──────────────────────────┤
    ├─────────────────────┤      │ • Slot Holds (2 min TTL) │
    │ • Drivers           │      │ • Conversation Memory    │
    │ • Shipments         │      │   (1 hour TTL)           │
    │ • Facilities/Docks  │      └──────────────────────────┘
    │ • Appointment Slots │
    │ • Appointments      │
    │ • ETA Updates       │
    │ • Chat Threads      │
    │ • Chat Messages     │
    │ • Escalations       │
    └─────────────────────┘
```

---

## Technology Stack

### Backend

| Layer | Technology | Purpose |
|-------|-----------|---------| 
| **Web Framework** | FastAPI | REST API server, request routing |
| **LLM Provider** | Groq API (llama-3.3-70b-versatile) | Fast, free-tier LLM |
| **Agent Framework** | LangChain 1.x + LangGraph | ReAct agent, tool management |
| **Observability** | LangSmith | Trace every agent step |
| **Database** | Supabase (PostgreSQL) | Persistent storage |
| **Cache/State** | Redis | Slot holds, conversation memory |
| **Server** | Uvicorn | ASGI application server |
| **Language** | Python 3.11 | All backend code |

### Frontend

| Layer | Technology | Purpose |
|-------|-----------|---------| 
| **React App** | TanStack Start + Nitro | Full-stack React framework |
| **HTML Portal** | HTML5 + Vanilla JS | Driver login + chat fallback |
| **Dashboard** | HTML5 + Vanilla JS | Operations visibility |
| **Styling** | Tailwind CSS (React) / Inline CSS (HTML) | UI styling |

### DevOps & Deployment

| Component | Technology | Purpose |
|-----------|-----------|---------| 
| **Backend Hosting** | Railway (Service 1) | Python FastAPI server |
| **Frontend Hosting** | Railway (Service 2) | React/Nitro app |
| **Version Control** | Git + GitHub | Code versioning |
| **Environment** | Railway env vars + .env | Configuration secrets |

### Observability

| Tool | Purpose |
|------|---------| 
| **LangSmith** | Trace every agent step, see reasoning, debug tool calls |
| **Uvicorn Logging** | Server-side request/response logging |
| **Supabase Dashboard** | Monitor database, run SQL queries |
| **FastAPI /docs** | Interactive API testing (Swagger UI) |

---

## System Components

### 1. Web Server (`app/main.py`)

**Key endpoints**:
- `POST /chat` — Driver chat with agent
- `POST /ops/chat` — Ops assistant chat (dashboard)
- `POST /auth/login` — Driver authentication
- `GET /driver/{driver_id}` — Driver lookup
- `GET /driver/shipments/{driver_id}` — Active shipments
- `GET /ops/queue` — All active shipments
- `GET /ops/holds` — Active Redis holds
- `GET /ops/slots/{facility_id}` — Dock schedule
- `GET /ops/escalations` — Open escalations
- `GET /ops/threads` — Active chat threads
- `GET /ops/verify/{shipment_id}` — Ground truth booking check

**Important**: `app = FastAPI()` must be defined BEFORE `app.add_middleware()` — ordering matters.

### 2. Agent Orchestrator (`app/agent.py`)

- Uses `create_react_agent` from LangGraph
- Loads conversation history from Redis on each turn
- Saves updated history back to Redis after response
- Also persists messages to Supabase permanently
- `verbose=True` prints every agent step to server logs

### 3. Tools Module (`app/tools.py`)

6 tools available to the agent — all deterministic, no LLM guessing inside:

| Tool | Purpose |
|------|---------|
| `lookup_driver_context` | Get driver + shipment + appointment facts |
| `get_feasible_slots_tool` | Find available slots after ETA (IST formatted) |
| `hold_slot_tool` | 2-minute Redis soft lock on a slot |
| `confirm_booking_tool` | Book appointment + save ETA update |
| `release_hold_tool` | Release Redis hold |
| `escalate_to_human` | Create escalation in DB + ops dashboard |

### 4. Database Layer (`app/database.py`)

Supabase PostgreSQL queries. Key functions:
- `get_driver()`, `get_driver_shipments()`
- `get_shipment()`, `get_current_appointment()`
- `get_latest_eta()`, `get_facility_checkin()`
- `get_feasible_slots()` — excludes already-booked slots
- `book_appointment()` — marks old as not-current, creates new
- `save_eta_update()`, `save_chat_message()`
- `get_or_create_thread()`, `save_escalation()`

### 5. Redis Client (`app/redis_client.py`)

**Slot Holds** (key: `hold:{slot_id}`):
- `place_hold()` — atomic SET NX EX 120
- `get_hold()`, `release_hold()`
- `is_slot_held_by_other()` — used by slot search
- `get_all_active_holds()` — for ops dashboard

**Conversation Memory** (key: `conversation:{thread_id}`):
- `save_conversation()`, `get_conversation()`
- `clear_conversation()` — on thread close
- 1-hour TTL

---

## Database Schema

### Core Tables

#### **drivers**
```
driver_id (PK), driver_name, phone, carrier_id,
licence_number, home_base_city, driver_status
```

#### **shipments**
```
shipment_id (PK), driver_id (FK), vehicle_id (FK),
destination_facility_id (FK), priority_code,
current_status, required_dock_type,
expected_unload_min, cargo_desc, original_eta_ts
```

#### **appointment_slots**
```
slot_id (PK), facility_id (FK), dock_id (FK),
dock_type, slot_start_ts, slot_end_ts,
slot_status, block_reason
```

#### **appointments**
```
appointment_id (PK), shipment_id (FK), slot_id (FK),
appointment_status, booking_source, is_current,
booked_at, confirmed_at, cancelled_at,
cancellation_reason
```

#### **eta_updates**
```
eta_update_id (PK), shipment_id (FK),
source_type, declared_eta_ts, confidence_code,
note, created_at
```

#### **driver_exceptions** (escalations)
```
exception_id (PK), shipment_id (FK), driver_id (FK),
thread_id (FK), exception_type, reported_at,
exception_status, notes, dedupe_key
```

#### **chat_threads**
```
thread_id (PK), driver_id (FK), shipment_id (FK),
opened_at, closed_at, thread_status, thread_intent
```

#### **chat_messages**
```
message_id (PK), thread_id (FK),
sender_type (DRIVER|AGENT|OPS|WAREHOUSE),
message_text, created_at
```

#### **facilities**
```
facility_id (PK), facility_name, city, state,
open_time, close_time, no_show_grace_min, last_start_min
```

#### **docks**
```
dock_id (PK), facility_id (FK), dock_code,
dock_type (STANDARD|REEFER|HEAVY),
refrigerated, max_weight_kg, dock_status
```

---

## API Endpoints

### Chat

#### **POST /chat**
```json
Request:  { "driver_id": "DRV006", "message": "90 min late" }
Response: { "driver_id": "DRV006", "response": "...", "thread_id": "THR-..." }
```

#### **POST /ops/chat**
Same shape — used by dashboard ops assistant. Internally uses a system driver context.

### Auth

#### **POST /auth/login**
```json
Request:  { "driver_id": "DRV006", "phone": "+91-9000010006" }
Response: { "success": true, "driver_name": "Manoj Sharma", "driver_id": "DRV006", "carrier_id": "CAR003" }
```

### Driver

#### **GET /driver/{driver_id}**
Returns full driver record.

#### **GET /driver/shipments/{driver_id}**
Returns active shipments (IN_TRANSIT, WAITING, ASSIGNED).

### Ops Dashboard

| Endpoint | Returns |
|----------|---------|
| `GET /ops/queue` | Active shipments (IN_TRANSIT, WAITING, IN_DOCK) |
| `GET /ops/holds` | Active Redis slot holds |
| `GET /ops/slots/{facility_id}` | All slots with appointment status |
| `GET /ops/escalations` | Open escalations |
| `GET /ops/threads` | Open chat threads (last 50) |
| `GET /ops/verify/{shipment_id}` | Ground truth booking check |

### Frontend Pages (HTML)

| URL | Page |
|-----|------|
| `/portal` | Driver login |
| `/portal/chat` | Driver chat |
| `/dashboard` | Ops dashboard |

---

## Agent Tools & Capabilities

### Tool Execution Flow

```
Driver message → Agent reasons → picks tool → tool queries DB/Redis
→ returns facts → agent reasons again → picks next tool or responds
```

**Key principle**: Tools are deterministic. The LLM decides WHEN to call them, but the tools themselves never guess — they query real data.

### Slot Lifecycle

```
OPEN → HELD (Redis, 2 min) → PENDING_CONFIRMATION (DB) → CONFIRMED
                ↘ RELEASED (driver changed mind or timeout)
```

### Race Condition Prevention

```
Driver A: hold_slot(SLOT-X) → Redis SET NX → SUCCESS → holds slot
Driver B: hold_slot(SLOT-X) → Redis SET NX → FAIL → offered alternative
```

---

## Data Flows

### Flow 1: Standard Delay Resolution

```
1. Driver: "90 min late"
2. POST /chat → FastAPI → run_agent()
3. Agent: lookup_driver_context(DRV006)
   → Supabase: finds SHP1006, appointment at 10:00 AM, ETA 11:30 AM
4. Agent: get_feasible_slots_tool(FAC-JAI-01, STANDARD, after 11:30 AM)
   → Supabase: finds SLOT-JAI-D1-004 (12:00–13:00)
   → Redis: confirms no hold on this slot
5. Agent: hold_slot_tool(SLOT-JAI-D1-004, SHP1006, DRV006)
   → Redis SET NX EX 120 → SUCCESS
6. Agent responds: "I have a slot at 12:00 PM, Dock D1. Confirm?"
7. Driver: "Haan, book karo"
8. Agent: confirm_booking_tool(...)
   → Supabase: save ETA update, create appointment PENDING_CONFIRMATION
   → Redis: release hold
9. Agent responds: "Slot booked. Awaiting warehouse confirmation."
```

### Flow 2: Escalation (No Slots)

```
1. Driver: "Vehicle breakdown, 5 hour delay"
2. Agent: lookup_driver_context → finds SHP1009 CRITICAL priority
3. Agent: get_feasible_slots_tool → no slots available (facility closes)
4. Agent: escalate_to_human(urgency=CRITICAL, reason="No slots after ETA")
   → Supabase: creates EXC-XXXXXXXX in driver_exceptions
5. Agent responds: "Escalated to ops team. Reference: EXC-XXXXXXXX"
6. Dashboard shows RED escalation card for coordinator
```

### Flow 3: Two Drivers, Same Slot

```
Driver A & B both want SLOT-JAI-D2-005 at 14:00
  ↓
Driver A: Redis SET NX → SUCCESS → holds slot
Driver B: Redis SET NX → FAIL → "Slot being processed, choose another"
  ↓
Driver A confirms → Supabase appointment created → Redis hold released
Driver B: slot search returns next available slot
```

---

## Deployment & Configuration

### Environment Variables

```bash
# LLM
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...   # backup
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=setuhaul-agent

# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=eyJhbGci...

# Redis
REDIS_URL=redis://localhost:6379   # local WSL2
# or Redis Cloud URL for production

# Google (optional)
GOOGLE_API_KEY=AIza...
```

### Railway Deployment

**Service 1 — Python Backend**
```
Root directory:   /
Build command:    pip install -r requirements.txt
Start command:    uvicorn app.main:app --host 0.0.0.0 --port 8000
Port:             8000
```

**Service 2 — React Frontend**
```
Root directory:   frontend/frontend-react
Build command:    npm run build
Start command:    npx nitro preview
Port:             8080
```

### Local Development

```bash
# Terminal 1 — Redis (WSL2)
sudo service redis-server start

# Terminal 2 — Backend
cd D:\FDE\Coding_projects\SetuHaul
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# Terminal 3 — React frontend
cd frontend\frontend-react
npm run dev

# URLs
# Backend API docs: http://localhost:8000/docs
# HTML Portal:      http://localhost:8000/portal
# HTML Dashboard:   http://localhost:8000/dashboard
# React App:        http://localhost:5173 (or as shown in terminal)
```

### Useful Test Credentials

| Driver | ID | Phone |
|--------|----|-------|
| Manoj Sharma (HIGH priority, IN_TRANSIT) | DRV006 | +91-9000010006 |
| Vikram Solanki (CRITICAL, medical supplies) | DRV009 | +91-9000010009 |
| Deepak Saini (HIGH, REEFER dock) | DRV010 | +91-9000010010 |
| Rajesh Kumar | DRV001 | +91-9000010001 |

---

## Frontend Architecture

### 1. React App (TanStack Start + Nitro)

**Routes**:
- `/` — Landing page
- `/driver` — Driver workspace (login + chat)
- `/dashboard` — Ops overview
- `/dashboard/{warehouseId}` — Facility detail view

**API Connection** (`src/lib/api.ts`):
```typescript
export const API_BASE = "https://setuhaul-production.up.railway.app";
```

**Current state**: UI is connected to live backend. Ops assistant uses `/ops/chat`.

### 2. HTML Portal (Fallback)

Served directly by FastAPI. Full login → chat flow works independently.

- `/portal` — Login (driver_id + phone)
- `/portal/chat` — Chat with agent
- `/dashboard` — Ops dashboard (30s auto-refresh)

### 3. Ops Dashboard Features

- Stats row: In Transit / Waiting / In Dock / Holds / Escalations / Threads
- Dock schedule grid (colour-coded: open/booked/held/blocked/in-progress)
- Escalations panel (red cards)
- Active holds panel (yellow, ~2 min countdown)
- Chat threads panel
- Auto-refresh every 30 seconds

---

## Key Concepts & Terminology

### Status States

| Entity | States |
|--------|--------|
| Shipment | ASSIGNED → IN_TRANSIT → WAITING → IN_DOCK → DELIVERED |
| Appointment | PENDING_CONFIRMATION → CONFIRMED → IN_PROGRESS → CANCELLED |
| Slot | OPEN → BLOCKED / CLOSED |
| Thread | OPEN → CLOSED |
| Escalation | OPEN → RESOLVED → DISMISSED |

### Priority Levels

| Level | Slot Access | Example |
|-------|------------|---------|
| CRITICAL | First | Medical supplies, hazmat |
| HIGH | Second | Electronics, same-day |
| NORMAL | Third | Standard cargo |
| LOW | Last | Bulk, flexible |

### Dock Types

| Type | Use Case |
|------|----------|
| STANDARD | General dry cargo |
| REEFER | Temperature-controlled (dairy, pharma) |
| HEAVY | Industrial machinery, steel |

### Timing Windows

| Element | Duration |
|---------|----------|
| Redis slot hold | 120 seconds |
| Conversation memory (Redis) | 1 hour |
| Dashboard auto-refresh | 30 seconds |

---

## Known Issues & Planned Improvements

### Current Known Issues

| Issue | Status | Workaround |
|-------|--------|-----------|
| Dashboard not real-time (polling only) | Open | Manual refresh button |
| Ops assistant "Could not reach" error | Fixed in v1.1 — `/ops/chat` endpoint added | Use `/ops/chat` not `/chat` |
| React app uses mock data for some views | In progress | HTML portal is fully live |
| Slot times display in UTC occasionally | Partial fix — IST conversion in tools.py | Check slot_start_ts directly |

### Planned Improvements (Priority Order)

1. **Driver bookings screen** — After login, driver sees current and upcoming bookings as cards. Each card has a "Help" button that opens the chat with the booking context pre-loaded (shipment_id, slot, ETA already known). This eliminates the need for the agent to ask which shipment.

2. **Dashboard real-time sync** — Replace 30s polling with Supabase Realtime subscriptions. Slot changes, new escalations, and hold events push to dashboard instantly.

3. **Hold countdown timer** — Live countdown on held slots in dashboard (currently shows "~2 min" static).

4. **Ops assistant scoped context** — The `/ops/chat` endpoint currently uses DRV001 as a proxy. Should use a dedicated ops user with `get_ops_summary` tool access instead.

5. **JWT authentication** — Replace phone verification with proper session tokens.

6. **WhatsApp / SMS channel** — Drivers to use WhatsApp instead of web chat.

7. **Warehouse confirmation flow** — Direct API for warehouse manager to CONFIRM or REJECT PENDING_CONFIRMATION appointments from dashboard.

8. **Predictive ETA** — Auto-detect likely delays from GPS before driver reports.

---

## Master Flow Diagram

```
Driver: "I'm 90 min late, find me a slot"
         ↓
    [Chat UI / React]
         ↓  POST /chat
    [FastAPI Server]
         ↓
    [LangGraph ReAct Agent]
    LLM reasons → picks tool → observes → reasons again
         ↓
    ┌────────────────────────────────┐
    │         TOOL LAYER            │
    │  lookup_driver_context()      │  ← Supabase: who is this driver?
    │  get_feasible_slots_tool()    │  ← Supabase + Redis: what's free?
    │  hold_slot_tool()             │  ← Redis SET NX EX 120: reserve it
    │  confirm_booking_tool()       │  ← Supabase: create appointment
    │  release_hold_tool()          │  ← Redis DEL: free the hold
    │  escalate_to_human()          │  ← Supabase: create escalation
    └────────────────────────────────┘
         ↓
    [Redis] — atomic holds, conversation memory
    [Supabase] — permanent bookings, ETAs, messages
         ↓
    Response → Driver sees: "Slot at 12:00 PM booked. Ref: APT-XXXX"
         ↓
    [Ops Dashboard] — sees new appointment, escalations, holds live
```

---

## Summary

**SetuHaul** is an **intelligent exception manager for freight logistics**:

1. **24/7 Availability** — Agent runs round-the-clock
2. **Automated Rebooking** — Finds slots, holds them, books atomically
3. **Human in Loop** — Escalates when it can't resolve safely
4. **Real-Time Visibility** — Ops dashboard shows live facility state
5. **Data-Driven** — All decisions verified against DB facts, never guessed
6. **Race-Safe** — Redis prevents double-bookings under concurrent load
7. **Multilingual** — Understands Hinglish (Hindi + English mix)

**Core Value**: Reduces ops overhead by ~80% for standard delay cases. Complex exceptions get proper human attention with full context.

---

**Document Version**: 1.1.0
**Last Updated**: 2026-08-18
**Stack**: Python · FastAPI · LangChain · LangGraph · Groq · Supabase · Redis · React · TanStack · Railway