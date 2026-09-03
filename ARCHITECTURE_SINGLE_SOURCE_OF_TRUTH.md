# SetuHaul — Single Source of Truth Architecture

This document is grounded only in the code and comments under the SetuHaul app and frontend. It is meant to be the canonical architecture reference for future diagram generation or agent-to-agent handoff.

## 1) System boundary

The system is a Python FastAPI backend + LangGraph ReAct agent + Supabase + Redis + static frontend pages.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Client / Interface Layer                             │
│                                                                             │
│  - Driver portal: frontend/index.html                                        │
│  - Driver chat: frontend/chat.html                                           │
│  - Ops dashboard: frontend/dashboard.html                                    │
│  - Static assets served via FastAPI app.mount("/static", ...)               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application Layer                             │
│  app/main.py                                                                 │
│  - app = FastAPI()                                                          │
│  - CORS enabled                                                             │
│  - Auth endpoints                                                            │
│  - Driver + shipment lookup endpoints                                        │
│  - Chat endpoints                                                            │
│  - Ops queue / holds / escalation / thread endpoints                         │
│  - Warehouse resource / yard / slots endpoints                               │
│  - Streaming chat endpoint                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Agent Orchestration Layer                            │
│                                                                             │
│  app/agent.py                                                               │
│  - run_agent(driver_id, message)                                            │
│  - loads chat history from Redis                                            │
│  - detects exception type with IntentDetector                               │
│  - builds dynamic system prompt                                             │
│  - creates LangGraph ReAct agent                                             │
│  - invokes LLM + tools                                                      │
│  - stores new messages back to Redis + Supabase                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
            ┌───────────────────────────┼──────────────────────────────┐
            ▼                           ▼                              ▼
┌──────────────────────┐   ┌──────────────────────────────┐   ┌──────────────────────┐
│ Tool Layer           │   │ Business Rule / Validation  │   │ Persistence Layer    │
│ app/tools.py         │   │ app/allocation.py           │   │ Supabase / Redis     │
│ - lookup_driver_...  │   │ app/feasibility.py          │   │ app/database.py      │
│ - get_feasible_...   │   │ - deterministic slot rank  │   │ app/redis_client.py  │
│ - hold_slot_tool     │   │ - feasibility checks       │   │                      │
│ - confirm_booking_   │   │ - prevents bad bookings    │   │                      │
│ - release_hold_tool  │   │ - allocation policy        │   │                      │
│ - escalate_to_human  │   │ - no LLM decision making   │   │                      │
└──────────────────────┘   └──────────────────────────────┘   └──────────────────────┘
                                      │
                                      │
                            ┌─────────┴─────────┐
                            ▼                   ▼
              ┌─────────────────────┐   ┌──────────────────────────┐
              │ Supabase Postgres  │   │ Redis cache / locks      │
              │ tables: drivers,   │   │ - hold:* slot locks      │
              │ shipments,         │   │ - conversation:* history │
              │ appointments,      │   │ - TTL 2 min holds        │
              │ appointment_slots, │   │ - TTL 1 hour messages    │
              │ eta_updates,       │   └──────────────────────────┘
              │ chat_threads,      │
              │ chat_messages,     │
              │ driver_exceptions, │
              │ decision_audit,    │
              │ facility data, etc.│
              └─────────────────────┘
```

## 2) What each source file is responsible for

### app/main.py
Source of HTTP API surface.

Responsibilities:
- Create FastAPI app and enable CORS.
- Mount static frontend under /static.
- Serve HTML pages: /, /portal, /portal/chat, /dashboard.
- Authenticate driver via POST /auth/login.
- Lookup driver, shipments, active queue, holds, slots, escalations, threads.
- Expose warehouse dashboard endpoints:
  - /warehouse/{warehouse_id}/resources
  - /warehouse/{warehouse_id}/yard
  - /warehouse/{warehouse_id}/slots
  - /warehouse/{warehouse_id}/escalations
- Provide driver chat endpoints:
  - POST /chat
  - POST /chat/stream
  - POST /ops/chat

### app/agent.py
Source of the conversational AI orchestrator.

Responsibilities:
- Load environment and initialize LLM via OpenRouter.
- Build system prompt, including exception-specific guidance.
- Detect exception type with IntentDetector.
- Combine history from Redis and new message.
- Invoke LangGraph ReAct agent with ALL_TOOLS.
- Parse last non-tool message as final response.
- Save human/agent conversation to Redis and Supabase.

Important code-level policy:
- The prompt explicitly says the LLM must not decide booking allocation itself.
- Booking/slot ranking is delegated to deterministic tools and policy modules.

### app/tools.py
Source of agent-callable tools.

These are the actual tools used by the ReAct agent:
- lookup_driver_context(driver_id)
- get_feasible_slots_tool(shipment_id, facility_id, after_eta_ts, dock_type)
- hold_slot_tool(slot_id, shipment_id, driver_id)
- confirm_booking_tool(slot_id, shipment_id, driver_id, revised_eta_ts, eta_confidence, eta_note)
- release_hold_tool(slot_id, shipment_id)
- escalate_to_human(shipment_id, driver_id, thread_id, reason, urgency)

These tools are deterministic and are the only place where operational decisions are made.

### app/database.py
Source of persistent business data access and database writes.

Core database responsibilities:
- Driver lookup and active shipment queries.
- Shipment and appointment lookup.
- ETA inserts and retrieval.
- Facility and gate queries.
- Slot availability queries and appointment booking.
- Chat thread creation and message logging.
- Escalation persistence.
- Audit / decision logging.
- Warehouse / yard / resource pool / tracking / notification functions.

### app/redis_client.py
Source of transient state.

Responsibilities:
- Slot holds with 2-minute TTL, using atomic SET NX EX.
- Conversation memory with 1-hour TTL.
- Get / release / inspect holds for concurrency prevention.
- Dashboard reads for active holds.

### app/intent_detector.py
Source of exception classification.

Detected categories:
- MECHANICAL_FAILURE
- DRIVER_SICKNESS
- TRAFFIC_CONGESTION
- POLICE_CHECKPOINT
- FACILITY_BLOCKED
- GENERIC_DELAY

It classifies the message and produces follow-up questions, but it does not make slot selections.

### app/allocation.py
Source of deterministic slot-ranking policy.

Responsibilities:
- score_slot(...)
- allocate_slot(...)
- Rank candidate slots by priority and time fit.
- Returns a ranked list with explanations.
- This is the explicit policy layer; it replaces ad hoc LLM allocation logic.

### app/feasibility.py
Source of slot viability validation.

Responsibilities:
- Check if a slot exists.
- Check slot status is OPEN.
- Check slot is not already booked.
- Check dock compatibility.
- Check unload duration fits slot.
- Check facility accepts appointments.
- Check no conflicting current appointment.
- Return structured feasibility result with reasons/explanation.

This is the gate used before booking and before showing final slot recommendation.

## 3) Runtime call flow

### A. Driver chat request path

```text
POST /chat
  -> app.main.chat(request)
     -> get_or_create_thread(driver_id)
     -> run_agent(driver_id, message)
        -> get_conversation(thread_id)
        -> detector.detect_exception_type(message, thread_id)
        -> log_decision(EXCEPTION_DETECTION, ...)
        -> detector.get_conversation_state(thread_id)
        -> handler_integration run_pipeline(...)  [best-effort, non-blocking]
        -> build_dynamic_system_prompt(exception_type)
        -> build_agent(system_prompt)
        -> agent.invoke({ messages: history + new human message })
           -> tool calls as needed
           -> final assistant text returned
        -> save_conversation(thread_id, raw_history)
        -> save_chat_message(thread_id, "DRIVER", message)
        -> save_chat_message(thread_id, "AGENT", response)
     -> return ChatResponse
```

### B. Slot search and recommendation path

```text
driver message with delay / reschedule intent
  -> agent tool call: lookup_driver_context(driver_id)
     -> get_driver()
     -> get_driver_shipments(driver_id)
     -> get_current_appointment(shipment_id)
     -> get_latest_eta(shipment_id)
     -> get_facility_checkin(shipment_id)
     -> get_facility(destination_facility_id)
  -> agent tool call: get_feasible_slots_tool(shipment_id, facility_id, after_eta_ts, dock_type)
     -> get_feasible_slots(facility_id, dock_type, after_ts)
        -> query appointment_slots where OPEN + facility + dock_type + >= after_ts
        -> query appointments for slot_id collisions
     -> reject slots held by other shipments
     -> validate_slot_against_current_state(slot_id, ...)
     -> allocate_slot(candidates, shipment_id)
        -> score_slot(...) for each candidate
        -> sort by score descending
     -> return ranked slots, slot #1 recommended
```

### C. Booking confirmation path

```text
driver explicitly says YES to a specific slot
  -> confirm_booking_tool(slot_id, shipment_id, driver_id, revised_eta_ts, eta_confidence, eta_note)
     -> get_shipment(shipment_id)
     -> validate_slot_against_current_state(slot_id, shipment_id, facility_id, required_dock_type, expected_unload_min)
     -> check hold relationship: is_slot_held_by_other(slot_id, shipment_id)
     -> save_eta_update(shipment_id, eta_ts, confidence, note, driver_id)
     -> book_appointment(shipment_id, slot_id)
        -> if existing appointment on same slot already exists, return existing
        -> otherwise set previous current apt is_current = 0
        -> insert new appointment with status PENDING_CONFIRMATION
     -> release_hold(slot_id, shipment_id)
     -> log_decision(BOOKING_CONFIRMED or related decision, ...)
     -> return success/failure
```

### D. Hold management path

```text
hold_slot_tool(slot_id, shipment_id, driver_id)
  -> place_hold(slot_id, shipment_id, driver_id)
     -> Redis SET key hold:{slot_id} NX EX 120
     -> if other shipment holds it, deny or refresh same-shipment hold

release_hold_tool(slot_id, shipment_id)
  -> release_hold(slot_id, shipment_id)
     -> Redis DELETE hold:{slot_id}
```

### E. Escalation path

```text
When:
- no feasible slots
- contradictory/uncertain info
- safety concerns
- replacement driver required
- facility unable to resolve

  -> escalate_to_human(shipment_id, driver_id, thread_id, reason, urgency)
     -> save_escalation(...)
     -> insert into driver_exceptions table
     -> return escalation record
```

## 4) Critical judgments and hard guardrails in the code

These are the decision points that materially shape behavior.

### Judgment 1: Intent detection is classification only
Location: app/intent_detector.py

- The agent uses exception detection to choose system prompt guidance.
- The classification does not itself decide booking or routing.
- It only identifies likely exception type and missing info needed for follow-up.

### Judgment 2: Allocation is not decided by the LLM
Location: app/tools.py + app/allocation.py + app/agent.py

The system prompt explicitly states:
- Do not override the allocation ranking.
- Do not decide which slot wins.
- Present the ranked options returned by get_feasible_slots_tool.
- Slot #1 is the recommended option.

This is enforced by:
- get_feasible_slots_tool() calling allocate_slot(...)
- allocate_slot() sorting by deterministic scoring
- agent prompt telling the LLM to present the ranking, not invent another one

### Judgment 3: Booking revalidation is mandatory before confirmation
Location: app/tools.py -> confirm_booking_tool

Before booking, the tool must:
- validate slot feasibility again
- check it is still available
- ensure no hold by another shipment
- then save ETA and create appointment

This is the code-level race-condition prevention mechanism.

### Judgment 4: Redis holds are the concurrency control layer
Location: app/redis_client.py

- Slot holds are atomic with Redis SET NX EX.
- 2-minute TTL is used as a soft lock while the driver decides.
- This prevents multiple driver conversations from claiming the same slot at once.

### Judgment 5: Database writes are the system of record
Location: app/database.py

Supabase tables are the real persistence layer. Redis is temporary state, not the source of truth for future booking/decision history.

## 5) Data stores and their actual roles

### Supabase (persistent state)
Key objects in code:
- drivers
- shipments
- appointments
- appointment_slots
- eta_updates
- facilities
- facility_gates
- facility_checkins
- driver_exceptions
- chat_threads
- chat_messages
- decision_audit
- resource_pool
- driver_availability
- yard_states
- gate_logs
- notifications

### Redis (transient runtime state)
Keys created in code:
- hold:{slot_id}
- conversation:{thread_id}
- driver_ctx:{driver_id} (short-lived cache in tools.py)

TTL behavior:
- hold:* = 120 seconds
- conversation:* = 3600 seconds

## 6) Notable architecture constraint

The system is intentionally split between:
- LLM decision support: conversational interpretation, follow-up questions, explanation
- Deterministic operational logic: slot feasibility, slot ranking, hold locking, booking, revalidation

This split is explicit in the code comments and system prompt.

In other words:
- The model helps the driver and explains options.
- The app logic decides whether a slot is valid, how it ranks, and whether it can be booked.

## 7) Minimal implementation map

```text
app/main.py
  ├── HTTP API routes
  ├── static serving
  └── dashboard endpoints

app/agent.py
  ├── LLM setup
  ├── prompt building
  ├── exception detection
  ├── agent invocation
  └── Redis + Supabase persistence

app/tools.py
  ├── lookup inventory / context
  ├── slot search
  ├── hold / release
  ├── confirm booking
  └── escalation

app/feasibility.py
  └── validation rules for slot acceptance

app/allocation.py
  └── deterministic ranking rules

app/database.py
  └── database access + writes

app/redis_client.py
  └── short-lived locks and history

app/intent_detector.py
  └── exception classification
```

## 8) One-sentence summary

SetuHaul is a FastAPI-driven driver exception management system where a LangGraph agent interprets messages, calls deterministic tools for context + slot feasibility + booking validation, stores transient state in Redis, and persists operational truth in Supabase.

This is the architecture that should be used as the canonical reference when generating visual diagrams.
