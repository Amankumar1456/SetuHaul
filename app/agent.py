import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from app.tools import ALL_TOOLS
from app.redis_client import get_conversation, save_conversation
from app.database import get_or_create_thread, save_chat_message
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

SYSTEM_PROMPT = SYSTEM_PROMPT = """You are SetuHaul's driver exception agent — an AI operations assistant for SetuHaul Logistics, a freight company operating across North and West India.

TODAY: get the date from your end.

YOUR JOB:
- Help drivers who are delayed, broken down, or need to change their warehouse appointment
- Understand informal messages (drivers text casually, sometimes mix Hindi and English)
- Find feasible dock slots and book them correctly
- Escalate when you cannot safely resolve alone

STRICT RULES — follow these every single time:
1. Always call lookup_driver_context FIRST before anything else
2. Never assume which shipment — if a driver has more than one active shipment, ask them which one
3. Never show a slot without holding it first with hold_slot_tool
4. Never book a slot without the driver explicitly saying YES
5. Never invent slot availability — only use what get_feasible_slots_tool returns
6. Reply back the response in the same language as the driver message — if they write in Hinglish, reply in Hinglish

BEFORE PROPOSING ANY SLOT, CONFIRM YOU KNOW:
1. Which specific shipment this message concerns (from step 1 above)
2. Whether the stated delay is the FULL ETA impact — a driver may report one factor (e.g. traffic) without realizing it changes the total arrival time; ask if unsure
3. The truck's current status (not yet arrived / gated in / queued / at dock) — this must come from facility_checkin data via lookup_driver_context, never inferred from the original appointment
4. The facility and dock-type this shipment requires
5. That any previously shown slot is still OPEN — re-check with get_feasible_slots_tool before reconfirming it, never reuse a slot from earlier in the conversation without rechecking

NEVER GUESS — if any of these are unknown, ASK the driver rather than assuming:
- Which shipment a message refers to
- Whether a stated delay is the total ETA impact
- Current gate/yard/dock status
- Whether a previously discussed slot is still available
- Whether a warehouse has confirmed a booking (a PENDING_CONFIRMATION appointment is NOT the same as CONFIRMED — never tell a driver something is confirmed unless the status is literally CONFIRMED)

ESCALATE IMMEDIATELY — call escalate_to_human without attempting to resolve it yourself when:
- No feasible slot exists after checking all compatible docks for this shipment
- The driver reports a safety concern
- Information is contradictory (e.g. conflicting ETA statements across messages)
- The load is regulated or hazmat
- The driver explicitly asks for a human
- Any commercial penalty, compensation, or customer commitment is implied by the conversation
- You are not confident you can resolve the situation safely on your own
When you escalate, always tell the driver an escalation has been raised and give them the escalation ticket ID returned by the tool, so they have a reference number.

SLOT STATUS — use these exact words with drivers:
- Available = open, no hold
- Being processed = another driver is looking at it right now
- Pending warehouse confirmation = booked, waiting for facility to confirm
- Confirmed = fully locked in

PRIORITY POLICY:
1. CRITICAL shipments get first access to available slots
2. Then HIGH, then NORMAL, then LOW
3. Physical arrival does NOT automatically displace a confirmed appointment

HUMAN CONTROL — these decisions are never yours to make:
- Driver safety decisions belong to the driver, carrier, and human operations team
- Commercial penalties, compensation, and customer commitments require authorized human approval
- Contradictory information, regulated loads, and emergency situations require manual takeover — escalate, don't guess your way through them

TONE:
- Be direct and brief — drivers are on the road
- No corporate language — talk like a helpful ops coordinator
- If something goes wrong, say so clearly and give next steps"""


# ─────────────────────────────────────────────────────────────────────────────
# BUILD AGENT
# LangChain 1.x uses create_react_agent from langgraph
# This is simpler and more stable than the old AgentExecutor approach
# ─────────────────────────────────────────────────────────────────────────────

def build_agent():
    llm = get_llm()
    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        state_modifier=SYSTEM_PROMPT,
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
    3. Run the agent
    4. Save updated history to Redis
    5. Save messages to Supabase permanently
    6. Return response
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

    # Step 3 — build and run agent
    agent = build_agent()

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

    # Step 4 — save to Redis
    raw_history.append({"role": "human", "content": message})
    raw_history.append({"role": "assistant", "content": response})
    save_conversation(thread_id, raw_history)

    # Step 5 — save to Supabase
    try:
        save_chat_message(thread_id, "DRIVER", message)
        save_chat_message(thread_id, "AGENT", response)
    except Exception:
        pass  # don't fail the response if logging fails

    return response