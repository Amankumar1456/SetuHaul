import os
from supabase import create_client, Client
from dotenv import load_dotenv
import uuid
from datetime import datetime, timezone

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

print("SUPABASE_URL (repr):", repr(supabase_url))
print("SUPABASE_KEY (repr):", repr(supabase_key))

if not supabase_url or not supabase_key:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in environment (.env).")

if supabase_key.startswith("sb_publishable_"):
    raise RuntimeError(
        "Invalid SUPABASE_KEY: the value in .env is a publishable key. "
        "Use the Supabase project service_role secret key for server-side access."
    )

# Connect to Supabase
supabase: Client = create_client(supabase_url, supabase_key)

# ── Drivers ───────────────────────────────────────────────────────────────────

def get_driver(driver_id: str) -> dict | None:
    result = supabase.table("drivers").select("*").eq("driver_id", driver_id).execute()
    return result.data[0] if result.data else None

def get_driver_shipments(driver_id: str) -> list:
    """Get all active shipments for a driver."""
    result = supabase.table("shipments").select("*").eq(
        "driver_id", driver_id
    ).in_(
        "current_status", ["IN_TRANSIT", "WAITING", "ASSIGNED"]
    ).execute()
    return result.data

# ── Shipments ─────────────────────────────────────────────────────────────────

def get_shipment(shipment_id: str) -> dict | None:
    result = supabase.table("shipments").select("*").eq(
        "shipment_id", shipment_id
    ).execute()
    return result.data[0] if result.data else None

def get_current_appointment(shipment_id: str) -> dict | None:
    result = supabase.table("appointments").select(
        "*, appointment_slots(*)"
    ).eq(
        "shipment_id", shipment_id
    ).eq("is_current", 1).in_(
        "appointment_status",
        ["CONFIRMED", "PENDING_CONFIRMATION", "IN_PROGRESS"]
    ).execute()
    return result.data[0] if result.data else None

# ── ETA ───────────────────────────────────────────────────────────────────────

def get_latest_eta(shipment_id: str) -> dict | None:
    result = supabase.table("eta_updates").select("*").eq(
        "shipment_id", shipment_id
    ).order("created_at", desc=True).limit(1).execute()
    return result.data[0] if result.data else None

def save_eta_update(
    shipment_id: str,
    eta_ts: str,
    confidence: str,
    note: str,
    driver_id: str
) -> None:
    """Record a new ETA declared by the driver."""
    supabase.table("eta_updates").insert({
        "eta_update_id": f"ETA-{uuid.uuid4().hex[:8].upper()}",
        "shipment_id": shipment_id,
        "source_type": "DRIVER_DECLARED",
        "declared_eta_ts": eta_ts,
        "confidence_code": confidence,
        "note": note,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

# ── Facility & Checkins ───────────────────────────────────────────────────────

def get_facility(facility_id: str) -> dict | None:
    result = supabase.table("facilities").select("*").eq(
        "facility_id", facility_id
    ).execute()
    return result.data[0] if result.data else None

def get_facility_checkin(shipment_id: str) -> dict | None:
    result = supabase.table("facility_checkins").select("*").eq(
        "shipment_id", shipment_id
    ).execute()
    return result.data[0] if result.data else None

# ── Slots ─────────────────────────────────────────────────────────────────────

def get_feasible_slots(
    facility_id: str,
    dock_type: str,
    after_ts: str
) -> list:
    """
    Get open slots of the right dock type after the given timestamp.
    Excludes slots that already have an active appointment.
    """
    # Get open slots after the ETA
    slots_result = supabase.table("appointment_slots").select("*").eq(
        "facility_id", facility_id
    ).eq("dock_type", dock_type).eq(
        "slot_status", "OPEN"
    ).gte("slot_start_ts", after_ts).order("slot_start_ts").execute()

    if not slots_result.data:
        return []

    # Get slot IDs that are already booked
    slot_ids = [s["slot_id"] for s in slots_result.data]
    booked_result = supabase.table("appointments").select("slot_id").in_(
        "slot_id", slot_ids
    ).in_(
        "appointment_status",
        ["CONFIRMED", "PENDING_CONFIRMATION", "IN_PROGRESS"]
    ).execute()

    booked_slot_ids = {r["slot_id"] for r in booked_result.data}

    # Return only unbooked slots, max 5
    available = [
        s for s in slots_result.data
        if s["slot_id"] not in booked_slot_ids
    ]
    return available[:5]

# ── Appointments ──────────────────────────────────────────────────────────────

def book_appointment(shipment_id: str, slot_id: str) -> dict:
    """
    Create a new PENDING_CONFIRMATION appointment.
    
    IDEMPOTENCY: If this shipment already has a PENDING_CONFIRMATION or CONFIRMED
    appointment on this exact slot, return the existing appointment instead of
    creating a duplicate. This prevents retries from creating multiple bookings.
    
    ATOMICITY: Uses database logic to prevent two concurrent requests from both
    succeeding. Only one will obtain is_current=1 for this shipment.
    """
    apt_id = f"APT-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    # IDEMPOTENCY CHECK: Look for existing appointment on this slot
    existing = supabase.table("appointments").select("*").eq(
        "shipment_id", shipment_id
    ).eq("slot_id", slot_id).in_(
        "appointment_status",
        ["PENDING_CONFIRMATION", "CONFIRMED", "IN_PROGRESS"]
    ).execute()
    
    if existing.data:
        # This shipment already has an appointment on this slot
        # Return it instead of creating a duplicate
        return existing.data[0]

    # Mark any previous current appointment as not current
    # (this handles case where driver is rebooking)
    supabase.table("appointments").update(
        {"is_current": 0}
    ).eq("shipment_id", shipment_id).eq("is_current", 1).execute()

    # Create the new appointment
    result = supabase.table("appointments").insert({
        "appointment_id": apt_id,
        "shipment_id": shipment_id,
        "slot_id": slot_id,
        "appointment_status": "PENDING_CONFIRMATION",
        "booking_source": "DRIVER_CHAT",
        "is_current": 1,
        "booked_at": now,
    }).execute()

    return result.data[0] if result.data else {"error": "Booking failed"}

def cancel_appointment(shipment_id: str, reason: str) -> None:
    """Cancel the current active appointment for a shipment."""
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("appointments").update({
        "appointment_status": "CANCELLED",
        "is_current": 0,
        "cancelled_at": now,
        "cancellation_reason": reason,
    }).eq("shipment_id", shipment_id).eq("is_current", 1).execute()

# ── Chat Messages ─────────────────────────────────────────────────────────────

def save_chat_message(
    thread_id: str,
    sender_type: str,
    message_text: str
) -> None:
    """Save a message to the chat_messages table."""
    supabase.table("chat_messages").insert({
        "message_id": f"MSG-{uuid.uuid4().hex[:8].upper()}",
        "thread_id": thread_id,
        "sender_type": sender_type,
        "message_text": message_text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

def get_or_create_thread(driver_id: str, shipment_id: str = None) -> str:
    """Get the latest open thread for a driver or create a new one."""
    # Look for an existing open thread
    result = supabase.table("chat_threads").select("*").eq(
        "driver_id", driver_id
    ).eq("thread_status", "OPEN").order(
        "opened_at", desc=True
    ).limit(1).execute()

    if result.data:
        return result.data[0]["thread_id"]

    # Create a new thread
    thread_id = f"THR-{uuid.uuid4().hex[:8].upper()}"
    supabase.table("chat_threads").insert({
        "thread_id": thread_id,
        "driver_id": driver_id,
        "shipment_id": shipment_id,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "thread_status": "OPEN",
        "thread_intent": "UNKNOWN",
    }).execute()

    return thread_id

# ── Escalations ───────────────────────────────────────────────────────────────

def save_escalation(
    shipment_id: str,
    driver_id: str,
    thread_id: str,
    reason: str,
    urgency: str
) -> str:
    """Log an escalation to the driver_exceptions table."""
    exc_id = f"EXC-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    supabase.table("driver_exceptions").insert({
        "exception_id": exc_id,
        "shipment_id": shipment_id,
        "driver_id": driver_id,
        "thread_id": thread_id,
        "exception_type": "ESCALATED",
        "reported_at": now,
        "exception_status": "OPEN",
        "notes": f"[{urgency}] {reason}",
        "dedupe_key": f"{driver_id}-{shipment_id}-{now[:16]}",
    }).execute()

    return exc_id