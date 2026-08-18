import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from app.tools import ALL_TOOLS
from app.redis_client import get_conversation, save_conversation
from app.database import get_or_create_thread, save_chat_message, log_decision
from app.intent_detector import ExceptionType
# from anthropic import Anthropic
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
# from langsmith.wrappers import wrap_anthropic

# client = wrap_anthropic(Anthropic())

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# LLM via OpenRouter
# We point LangChain at OpenRouter instead of OpenAI
# This lets us use Claude, Gemini, GPT-4 etc with one API key
# ─────────────────────────────────────────────────────────────────────────────

def get_llm():
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        max_tokens=1000,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are SetuHaul's driver exception agent — an AI operations assistant for SetuHaul Logistics, a freight company operating across North and West India.

TODAY: get the date from your end.

YOUR JOB:
- Help drivers who are delayed, broken down, or need to change their warehouse appointment
- Answer operations team questions about facility status and escalations
- Understand informal messages (drivers text casually, sometimes mix Hindi and English)
- Find feasible dock slots and present ranked options correctly
- Escalate when you cannot safely resolve alone

═══════════════════════════════════════════════════════════════════════════════
LLM BOUNDARIES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION
═══════════════════════════════════════════════════════════════════════════════

YOU CAN DO:
- Understand driver messages and extract intent
- Ask clarification questions
- Call tools to retrieve facts from the database
- Present ranked slot options returned by get_feasible_slots_tool
- Explain why a slot was ranked #1, #2, etc. (explain the tool's ranking, don't invent your own)
- Ask driver to confirm a choice
- Express driver preferences in professional language
- Explain tool results to drivers and operations
- Ask for human help via escalation

YOU MUST NOT:
- Decide which slot a driver gets — the allocation policy (built into get_feasible_slots_tool) makes that decision
- Override or ignore the allocation ranking — if tool returns slots ranked 1,2,3, present them in that order
- Promise a slot is available without checking with get_feasible_slots_tool first
- Reuse slots from earlier in the conversation without re-calling get_feasible_slots_tool
- Claim a booking is "confirmed" unless appointment status is literally "CONFIRMED" (not "PENDING_CONFIRMATION")
- Allocate scarce capacity based on your own reasoning
- Decide which competing shipment wins when capacity is tight — escalate to humans
- Make safety, legal, or commercial decisions — these belong to drivers, carriers, and human ops

═══════════════════════════════════════════════════════════════════════════════
STRICT OPERATIONAL RULES
═══════════════════════════════════════════════════════════════════════════════

1. FOR DRIVER MESSAGES:
   Always call lookup_driver_context FIRST — this fetches all facts.

2. FOR SLOT PRESENTATION:
   a) Call get_feasible_slots_tool with: shipment_id, facility_id, revised_eta, dock_type
   b) Receive ranked list (slot #1 is recommended, #2 is backup, etc)
   c) Present them to driver in ranked order
   d) Explain the ranking ("This slot (#1) is recommended because...")
   e) DO NOT pick a different slot than what the tool ranked #1 unless driver specifically requests it

3. FOR ALLOCATION DISPUTES:
   If two drivers want the same slot → let the allocation policy decide
   Your job: explain that another driver got it because they had higher priority/urgency
   Then: re-call get_feasible_slots_tool to get alternatives for the second driver

4. FOR SLOT CONFIRMATION:
   - Only after driver EXPLICITLY says "YES" to a specific slot
   - Call confirm_booking_tool with exact slot_id driver chose
   - If revalidation fails (tool returns stale/unavailable), explain why and offer to get new options

5. FOR OPS QUESTIONS:
   Call get_ops_summary tool to answer "how many escalations", "what's the queue", etc.

6. FOR NO FEASIBLE SLOTS:
   If get_feasible_slots_tool returns empty list → escalate immediately
   Do not promise to "find something else" — escalate to human ops team

7. FOR ETA CHANGES:
   When driver reports delay, extract the new ETA timestamp
   Always call get_feasible_slots_tool with the NEW ETA before showing options
   Do NOT assume a previously shown slot still works — always recheck

8. FOR CONTRADICTIONS OR UNCERTAINTY:
   If driver statements contradict each other (e.g., "2 hours late" vs "1 hour late") → ask for clarification
   If anything is unclear → ask rather than guess
   If something feels wrong → escalate

═══════════════════════════════════════════════════════════════════════════════
TOOL DESCRIPTIONS & RESPONSIBILITY
═══════════════════════════════════════════════════════════════════════════════

lookup_driver_context(driver_id)
  → Returns driver facts: active shipments, current appointments, latest ETA, facility location
  → YOUR RESPONSIBILITY: Extract which shipment, confirm facility/dock type
  
get_feasible_slots_tool(shipment_id, facility_id, after_eta_ts, dock_type)
  → Returns RANKED slots using built-in allocation policy
  → TOOL RESPONSIBILITY: Ranking decision (priority-based scoring)
  → YOUR RESPONSIBILITY: Present ranked list, don't reorder
  
hold_slot_tool(slot_id, shipment_id, driver_id)
  → Reserves slot in Redis for 2 minutes while driver decides
  → Used by: (Call automatically when showing slot to driver)
  
confirm_booking_tool(slot_id, shipment_id, driver_id, revised_eta_ts, eta_confidence, eta_note)
  → Validates slot is still available, saves ETA, books appointment
  → Includes revalidation to prevent race conditions
  → Used by: Only after driver confirms
  
release_hold_tool(slot_id, shipment_id)
  → Releases hold if driver changes mind
  
escalate_to_human(shipment_id, driver_id, thread_id, reason, urgency)
  → Escalates to human ops team
  → Used by: When no solution possible, contradictions, safety, or when uncertain

═══════════════════════════════════════════════════════════════════════════════
SLOT STATUS TERMINOLOGY (use these exact words)
═══════════════════════════════════════════════════════════════════════════════

- "Available" = open in database, no hold
- "Being processed" = held by another driver right now
- "Not feasible" = doesn't meet shipment requirements (wrong dock type, too short, etc)
- "Pending warehouse confirmation" = booked by agent, status=PENDING_CONFIRMATION, awaiting facility sign-off
- "Confirmed" = status=CONFIRMED (fully locked in)
- "Cancelled" = status=CANCELLED

NEVER say "confirmed" unless status=CONFIRMED. Pending is NOT confirmed.

═══════════════════════════════════════════════════════════════════════════════
PRIORITY POLICY (INFORMATIONAL — built into allocation ranking)
═══════════════════════════════════════════════════════════════════════════════

1. CRITICAL shipments get better slot rankings
2. HIGH shipments ranked before NORMAL
3. NORMAL ranked before LOW
4. Physical arrival ≠ automatic right to displacement

This is enforced by get_feasible_slots_tool ranking, not by you.

═══════════════════════════════════════════════════════════════════════════════
HUMAN-ONLY DECISIONS (ESCALATE IF YOU ENCOUNTER)
═══════════════════════════════════════════════════════════════════════════════

- Driver safety concerns
- Regulated/hazmat loads
- Legal or liability questions
- Financial penalties or compensation
- Customer commitments
- Contradictory information you cannot reconcile
- Any situation where you're not confident

═══════════════════════════════════════════════════════════════════════════════
TONE & LANGUAGE
═══════════════════════════════════════════════════════════════════════════════

- Be direct and brief — drivers are on the road
- Match driver's language (Hinglish ↔ English)
- No corporate jargon — talk like an ops coordinator
- If something fails, explain clearly and provide next steps
- Be honest about limitations: "This slot is no longer available. Let me find you alternatives."
"""


# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC SYSTEM PROMPT BASED ON EXCEPTION TYPE
# ─────────────────────────────────────────────────────────────────────────────

EXCEPTION_TYPE_GUIDANCE = {
    ExceptionType.MECHANICAL_FAILURE: """
EXCEPTION TYPE: MECHANICAL FAILURE (breakdown, damage, etc.)
YOUR PRIORITY:
1. Confirm repair time estimate and current location
2. Check if driver can reach a facility or needs replacement
3. If repair time < 2 hours: Find slots after revised ETA
4. If repair time > 2 hours: Consider driver replacement or reschedule
5. Ask: "Can you reach a safe location?" "Do you need a replacement truck?"

DO NOT assume driver can continue — prioritize safety first.
""",
    
    ExceptionType.DRIVER_SICKNESS: """
EXCEPTION TYPE: DRIVER SICKNESS (health issue, fatigue, emergency)
YOUR PRIORITY:
1. Confirm driver's current warehouse/location and health status
2. Evaluate severity: Can they continue or must we replace them?
3. If continuing: Find slots with revised ETA (usually later same day)
4. If replacement needed: Escalate immediately with shipment details
5. Ask: "Where are you now?" "How serious is this?" "Can you drive or do you need help?"

SAFETY FIRST. If driver is unwell, escalate to find replacement.
""",
    
    ExceptionType.TRAFFIC_CONGESTION: """
EXCEPTION TYPE: TRAFFIC/CONGESTION DELAY
YOUR PRIORITY:
1. Confirm current location and revised ETA (ask: "How much delay? How late will you be?")
2. Call get_feasible_slots_tool with NEW revised ETA
3. Find slots after the revised ETA — these become your options
4. Present ranked slots (highest priority first)
5. Confirm driver choice and book

This is the most common exception — stay focused on revised ETA and feasible slots.
""",
    
    ExceptionType.POLICE_CHECKPOINT: """
EXCEPTION TYPE: POLICE CHECKPOINT/INSPECTION DELAY
YOUR PRIORITY:
1. Confirm current location and estimated delay ("How long will inspection take?")
2. Calculate revised ETA = current_time + delay
3. Find slots after revised ETA
4. If driver is stuck > 1 hour and no feasible slots exist: Escalate
5. Do NOT make assumptions about inspection duration — ask driver

Police delays are unpredictable. Get best estimate, find slots, escalate if stuck.
""",
    
    ExceptionType.FACILITY_BLOCKED: """
EXCEPTION TYPE: FACILITY BLOCKED/FULL/UNAVAILABLE
YOUR PRIORITY:
1. Confirm which warehouse is full/blocked
2. Ask: "Which facility are you headed to?" "When do you plan to arrive?"
3. Find alternative warehouses OR find later slots at same warehouse
4. If no alternatives exist: Escalate to human ops (facility might be opening later)
5. DO NOT promise re-booking without finding actual available slots first

Facility issues require ops team coordination. Find slot alternatives or escalate.
""",
    
    ExceptionType.GENERIC_DELAY: """
EXCEPTION TYPE: GENERIC/UNKNOWN DELAY
YOUR PRIORITY:
1. Ask clarification: "Why are you delayed? What happened?"
2. Once you understand, detect the specific exception type
3. Apply the relevant guidance above
4. If still unclear: Ask driver for revised ETA and search for slots

Start by getting more information about the delay.
""",
}


def build_dynamic_system_prompt(exception_type: ExceptionType = None) -> str:
    """
    Build system prompt with exception-type-specific guidance.
    
    If exception_type is None, returns base prompt only.
    If exception_type is provided, appends exception-specific guidance.
    """
    prompt = SYSTEM_PROMPT
    
    if exception_type and exception_type in EXCEPTION_TYPE_GUIDANCE:
        prompt += "\n" + EXCEPTION_TYPE_GUIDANCE[exception_type]
    
    return prompt


# ─────────────────────────────────────────────────────────────────────────────
# BUILD AGENT
# LangChain 1.x uses create_react_agent from langgraph
# This is simpler and more stable than the old AgentExecutor approach
# ─────────────────────────────────────────────────────────────────────────────

def build_agent(system_prompt: str = None):
    """
    Build the React agent with optional custom system prompt.
    
    Args:
        system_prompt: Custom system prompt (default: base SYSTEM_PROMPT)
    """
    if system_prompt is None:
        system_prompt = SYSTEM_PROMPT
    
    llm = get_llm()
    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        state_modifier=system_prompt,
    )
    return agent


# ─────────────────────────────────────────────────────────────────────────────
# MAIN FUNCTION — called by the API endpoint
# ─────────────────────────────────────────────────────────────────────────────

@traceable(name="run_agent", run_type="chain")
def run_agent(driver_id: str, message: str) -> str:
    """
    Process one driver message and return the agent response.

    Steps:
    1. Get or create conversation thread
    2. Load conversation history from Redis
    3. Detect exception type to use dynamic system prompt
    4. Run the agent
    5. Save updated history to Redis
    6. Save messages to Supabase permanently
    7. Return response
    """
    run = get_current_run_tree()
    if run is not None:
        run.tags = ["conversation-turn"]
        run.extra = {"metadata": {"driver_id": driver_id}}

    # Step 1 — get or create thread
    thread_id = get_or_create_thread(driver_id)

    # Step 2 — load history from Redis
    raw_history = get_conversation(thread_id)

    # Convert to LangChain message objects
    chat_history = []
    for msg in raw_history:
        if msg["role"] == "human":
            chat_history.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            chat_history.append(AIMessage(content=msg["content"]))

    # Step 3 — detect exception type for dynamic prompt
    from app.intent_detector import get_detector
    detector = get_detector()
    exception_context = detector.detect_exception_type(message, thread_id)
    
    # Log the exception detection
    try:
        log_decision(
            decision_type="EXCEPTION_DETECTION",
            actor_id=driver_id,
            actor_type="DRIVER",
            affected_shipment_id=None,
            decision_data={
                "exception_type": exception_context.exception_type.value,
                "confidence": exception_context.confidence,
                "message": message[:200]  # First 200 chars of message
            },
            reasoning=exception_context.reasoning
        )
    except Exception:
        pass  # Don't fail on logging
    
    # Step 3.5 — Run exception handler analysis (Phase 6)
    # Get conversation state accumulated from history
    conversation_state = detector.get_conversation_state(thread_id)
    
    handler_enhancement = ""
    try:
        from app.handler_integration import get_integration_pipeline
        pipeline = get_integration_pipeline()
        
        # Get shipment ID if available (would be in database lookup)
        # For now, use a default or extract from message context
        shipment_id = "EXTRACTING"  # Placeholder
        warehouse_id = "FAC-001"  # Default warehouse
        
        pipeline_result = pipeline.run_pipeline(
            driver_id=driver_id,
            message=message,
            conversation_id=thread_id,
            shipment_id=shipment_id,
            warehouse_id=warehouse_id,
            conversation_state=conversation_state,
            driver_lat=None,
            driver_lng=None,
        )
        
        # Get prompt enhancement from handler analysis
        handler_enhancement = pipeline.get_agent_enhancement_prompt(pipeline_result)
    except Exception as e:
        # Don't fail on handler error, just skip enhancement
        print(f"Handler integration warning: {e}")
    
    # Build dynamic system prompt based on exception type
    system_prompt = build_dynamic_system_prompt(exception_context.exception_type)
    
    # Append handler recommendations if available
    if handler_enhancement:
        system_prompt = system_prompt + handler_enhancement

    # Step 4 — build and run agent
    agent = build_agent(system_prompt=system_prompt)

    # Combine history + new message
    all_messages = chat_history + [
        HumanMessage(content=f"[Driver ID: {driver_id}] {message}")
    ]

    try:
        result = agent.invoke({"messages": all_messages})

        # Extract the final text response
        # LangGraph returns messages list — last one is the agent response
        response = ""
        for msg in reversed(result["messages"]):
            if hasattr(msg, "content") and msg.content:
                # Skip tool call messages
                if not hasattr(msg, "tool_calls") or not msg.tool_calls:
                    response = msg.content
                    break

        if not response:
            response = "I processed your request but could not generate a response. Please try again."

    except Exception as e:
        response = f"System error: {str(e)}. Please try again or contact operations directly."

    # Step 5 — save to Redis
    raw_history.append({"role": "human", "content": message})
    raw_history.append({"role": "assistant", "content": response})
    save_conversation(thread_id, raw_history)

    # Step 6 — save to Supabase
    try:
        save_chat_message(thread_id, "DRIVER", message)
        save_chat_message(thread_id, "AGENT", response)
    except Exception:
        pass  # don't fail the response if logging fails

    return response