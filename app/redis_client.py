import redis
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to Redis
r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))

# ── Slot Holds ────────────────────────────────────────────────────────────────
# A hold means: this slot is being considered by a driver
# It blocks other drivers from claiming the same slot
# Expires automatically after 2 minutes

HOLD_EXPIRY_SECONDS = 120  # 2 minutes

def place_hold(slot_id: str, shipment_id: str, driver_id: str) -> dict:
    """
    Atomically place a soft lock on a slot for 2 minutes.
    Uses SET ... NX EX so the check-and-set can't race between two
    concurrent callers — only one can ever win the hold.
    If someone else already holds it, return failure.
    """
    hold_key = f"hold:{slot_id}"
    hold_data = {
        "slot_id": slot_id,
        "shipment_id": shipment_id,
        "driver_id": driver_id,
    }

    # Atomic: SET only succeeds if the key does not already exist.
    # No read-then-write window for a second request to slip through.
    acquired = r.set(hold_key, json.dumps(hold_data), nx=True, ex=HOLD_EXPIRY_SECONDS)

    if not acquired:
        existing = r.get(hold_key)
        existing_data = json.loads(existing) if existing else None

        # Same shipment re-holding (e.g. re-confirming) — refresh TTL, allow it.
        if existing_data and existing_data["shipment_id"] == shipment_id:
            r.setex(hold_key, HOLD_EXPIRY_SECONDS, json.dumps(hold_data))
            return {
                "success": True,
                "slot_id": slot_id,
                "expires_in_seconds": HOLD_EXPIRY_SECONDS,
                "message": "Slot held for 2 minutes. Please confirm quickly."
            }

        return {
            "success": False,
            "reason": "Slot is being processed by another request. Please choose a different slot."
        }

    return {
        "success": True,
        "slot_id": slot_id,
        "expires_in_seconds": HOLD_EXPIRY_SECONDS,
        "message": "Slot held for 2 minutes. Please confirm quickly."
    }

def get_hold(slot_id: str) -> dict | None:
    """Check if a slot is currently held. Returns None if no hold."""
    hold_key = f"hold:{slot_id}"
    data = r.get(hold_key)
    return json.loads(data) if data else None


def release_hold(slot_id: str, shipment_id: str) -> dict:
    """
    Release a hold.
    Called when driver cancels, picks a different slot,
    or conversation ends without booking.
    """
    hold_key = f"hold:{slot_id}"
    existing = r.get(hold_key)

    if not existing:
        return {"success": False, "reason": "No hold found for this slot"}

    existing_data = json.loads(existing)
    if existing_data["shipment_id"] != shipment_id:
        return {"success": False, "reason": "Hold belongs to a different shipment"}

    r.delete(hold_key)
    return {"success": True, "message": "Hold released"}


def is_slot_held_by_other(slot_id: str, shipment_id: str) -> bool:
    """Returns True if slot is held by a DIFFERENT shipment."""
    hold = get_hold(slot_id)
    if not hold:
        return False
    return hold["shipment_id"] != shipment_id


def get_all_active_holds() -> list:
    """Get all currently active holds — used by the ops dashboard."""
    keys = r.keys("hold:*")
    holds = []
    for key in keys:
        data = r.get(key)
        if data:
            holds.append(json.loads(data))
    return holds


# ── Conversation Memory ───────────────────────────────────────────────────────
# Each driver conversation is stored in Redis so the agent remembers
# what was said earlier in the same session
# Expires after 1 hour of inactivity

CONVERSATION_EXPIRY_SECONDS = 3600  # 1 hour

def save_conversation(thread_id: str, messages: list) -> None:
    """Save the full conversation history for a thread."""
    key = f"conversation:{thread_id}"
    r.setex(key, CONVERSATION_EXPIRY_SECONDS, json.dumps(messages))


def get_conversation(thread_id: str) -> list:
    """
    Load conversation history.
    Returns empty list if no conversation found
    (new driver, or session expired).
    """
    key = f"conversation:{thread_id}"
    data = r.get(key)
    return json.loads(data) if data else []


def clear_conversation(thread_id: str) -> None:
    """Clear a conversation — used when thread is closed or escalated."""
    key = f"conversation:{thread_id}"
    r.delete(key)


def get_conversation_summary(thread_id: str) -> dict:
    """
    Return a quick summary of the conversation state.
    Useful for the ops dashboard.
    """
    messages = get_conversation(thread_id)
    return {
        "thread_id": thread_id,
        "message_count": len(messages),
        "has_history": len(messages) > 0,
        "last_role": messages[-1]["role"] if messages else None,
    }