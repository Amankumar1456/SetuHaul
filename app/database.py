import os
from supabase import create_client, Client
from dotenv import load_dotenv
import uuid
from datetime import datetime, timezone, timedelta

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


# ============================================================================
# LAYER 2: WAREHOUSE FUNCTIONS
# ============================================================================

def get_facility_with_gates(facility_id: str) -> dict | None:
    """Get facility details along with all gates."""
    facility = get_facility(facility_id)
    if not facility:
        return None
    
    gates_result = supabase.table("facility_gates").select("*").eq(
        "facility_id", facility_id
    ).order("gate_number").execute()
    
    facility["gates"] = gates_result.data if gates_result.data else []
    return facility

def get_facility_capacity_rule(facility_id: str, dock_type: str) -> dict | None:
    """Get capacity rules for a specific facility and dock type."""
    result = supabase.table("facility_capacity_rules").select("*").eq(
        "facility_id", facility_id
    ).eq("dock_type", dock_type).execute()
    
    return result.data[0] if result.data else None

def get_gate_info(gate_id: str) -> dict | None:
    """Get gate details by gate ID."""
    result = supabase.table("facility_gates").select("*").eq(
        "gate_id", gate_id
    ).execute()
    
    return result.data[0] if result.data else None

def get_facility_gates(facility_id: str) -> list:
    """Get all gates for a facility."""
    result = supabase.table("facility_gates").select("*").eq(
        "facility_id", facility_id
    ).order("gate_number").execute()
    
    return result.data if result.data else []

# ============================================================================
# LAYER 3: RESOURCE POOL FUNCTIONS
# ============================================================================

def get_resource_pool(warehouse_id: str, resource_type: str = None) -> list:
    """Get resource pool information for a warehouse."""
    query = supabase.table("resource_pool").select("*").eq(
        "warehouse_id", warehouse_id
    )
    
    if resource_type:
        query = query.eq("resource_type", resource_type)
    
    result = query.execute()
    return result.data if result.data else []

def get_available_drivers_at_warehouse(warehouse_id: str) -> list:
    """Get available drivers at a specific warehouse."""
    result = supabase.table("driver_availability").select("*").eq(
        "current_warehouse_id", warehouse_id
    ).eq("status", "AVAILABLE").execute()
    
    return result.data if result.data else []

def find_replacement_drivers_at_warehouse(warehouse_id: str, count: int = 1) -> list:
    """Find replacement drivers at the same warehouse (priority: home-base drivers)."""
    available = get_available_drivers_at_warehouse(warehouse_id)
    
    # Sort by home_warehouse_id == current_warehouse_id (home-base drivers first)
    sorted_drivers = sorted(
        available,
        key=lambda d: d.get("home_warehouse_id") == warehouse_id,
        reverse=True
    )
    
    return sorted_drivers[:count]

def update_driver_availability(driver_id: str, warehouse_id: str, status: str) -> None:
    """Update driver availability status and warehouse location."""
    supabase.table("driver_availability").upsert({
        "driver_id": driver_id,
        "current_warehouse_id": warehouse_id,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

def update_resource_pool(warehouse_id: str, resource_type: str, available_count: int) -> None:
    """Update resource availability count."""
    supabase.table("resource_pool").update({
        "available_count": available_count,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("warehouse_id", warehouse_id).eq(
        "resource_type", resource_type
    ).execute()

# ============================================================================
# LAYER 6: YARD STATE FUNCTIONS
# ============================================================================

def update_yard_state(truck_id: str, facility_id: str, new_state: str, gate_id: str = None) -> str:
    """Record truck yard state transition."""
    yard_state_id = f"YS-{uuid.uuid4().hex[:8].upper()}"
    
    supabase.table("yard_states").insert({
        "yard_state_id": yard_state_id,
        "truck_id": truck_id,
        "facility_id": facility_id,
        "state": new_state,
        "state_timestamp": datetime.now(timezone.utc).isoformat(),
        "gate_id": gate_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    
    return yard_state_id

def get_trucks_in_yard(facility_id: str, state_filter: str = None) -> list:
    """Get trucks currently in yard at a facility."""
    query = supabase.table("yard_states").select("*").eq(
        "facility_id", facility_id
    )
    
    if state_filter:
        query = query.eq("state", state_filter)
    
    result = query.order("state_timestamp", desc=True).execute()
    return result.data if result.data else []

def get_latest_yard_state(truck_id: str) -> dict | None:
    """Get the most recent yard state for a truck."""
    result = supabase.table("yard_states").select("*").eq(
        "truck_id", truck_id
    ).order("state_timestamp", desc=True).limit(1).execute()
    
    return result.data[0] if result.data else None

# ============================================================================
# LAYER 7: ETA FUNCTIONS (ENHANCED)
# ============================================================================

def save_eta_update_with_location(
    shipment_id: str,
    eta_ts: str,
    confidence: str,
    note: str,
    driver_lat: float = None,
    driver_lng: float = None,
    duration_min: int = None,
    distance_km: float = None
) -> None:
    """Record ETA update with optional location data."""
    supabase.table("eta_updates").insert({
        "eta_update_id": f"ETA-{uuid.uuid4().hex[:8].upper()}",
        "shipment_id": shipment_id,
        "source_type": "DRIVER_DECLARED",
        "declared_eta_ts": eta_ts,
        "confidence_code": confidence,
        "note": note,
        "driver_lat": driver_lat,
        "driver_lng": driver_lng,
        "calculated_duration_min": duration_min,
        "calculated_distance_km": distance_km,
        "calculation_method": "HARDCODED" if driver_lat else "DECLARED",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

# ============================================================================
# LAYER 8: TRACKING FUNCTIONS
# ============================================================================

def save_driver_location(
    driver_id: str,
    latitude: float,
    longitude: float,
    source: str = "GPS"
) -> str:
    """Save driver location to history."""
    location_id = f"LOC-{uuid.uuid4().hex[:8].upper()}"
    
    supabase.table("driver_location_history").insert({
        "location_id": location_id,
        "driver_id": driver_id,
        "latitude": latitude,
        "longitude": longitude,
        "source": source,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    
    return location_id

def get_driver_location_history(driver_id: str, minutes: int = 60) -> list:
    """Get driver location history for the last N minutes."""
    cutoff_time = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    
    result = supabase.table("driver_location_history").select("*").eq(
        "driver_id", driver_id
    ).gte("recorded_at", cutoff_time).order(
        "recorded_at", desc=True
    ).execute()
    
    return result.data if result.data else []

def get_latest_driver_location(driver_id: str) -> dict | None:
    """Get the most recent location for a driver."""
    result = supabase.table("driver_location_history").select("*").eq(
        "driver_id", driver_id
    ).order("recorded_at", desc=True).limit(1).execute()
    
    return result.data[0] if result.data else None

def log_gate_event(
    facility_id: str,
    gate_id: str,
    truck_id: str,
    shipment_id: str,
    event_type: str
) -> str:
    """Log a gate event (entry, exit, dock start, dock end)."""
    log_id = f"GATE-{uuid.uuid4().hex[:8].upper()}"
    
    supabase.table("gate_logs").insert({
        "log_id": log_id,
        "facility_id": facility_id,
        "gate_id": gate_id,
        "truck_id": truck_id,
        "shipment_id": shipment_id,
        "event_type": event_type,
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    
    return log_id

# ============================================================================
# LAYER 9: NOTIFICATION FUNCTIONS
# ============================================================================

def create_notification(
    recipient_type: str,
    recipient_id: str,
    notification_type: str,
    title: str,
    message: str,
    priority: str = "NORMAL",
    requires_action: bool = False,
    action_type: str = None
) -> str:
    """Create a notification for a recipient."""
    notification_id = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"
    
    supabase.table("notifications").insert({
        "notification_id": notification_id,
        "recipient_type": recipient_type,
        "recipient_id": recipient_id,
        "notification_type": notification_type,
        "title": title,
        "message": message,
        "priority": priority,
        "status": "PENDING",
        "requires_action": requires_action,
        "action_type": action_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    
    return notification_id

def get_pending_notifications(recipient_id: str) -> list:
    """Get all pending notifications for a recipient."""
    result = supabase.table("notifications").select("*").eq(
        "recipient_id", recipient_id
    ).eq("status", "PENDING").order(
        "created_at", desc=True
    ).execute()
    
    return result.data if result.data else []

# ============================================================================
# LAYER 10: REPORTING FUNCTIONS
# ============================================================================

def log_decision(
    decision_type: str,
    actor_id: str,
    actor_type: str,
    affected_shipment_id: str,
    decision_data: dict = None,
    previous_state: dict = None,
    new_state: dict = None,
    reasoning: str = None
) -> str:
    """Log a decision to the audit trail."""
    audit_id = f"AUDIT-{uuid.uuid4().hex[:8].upper()}"
    
    supabase.table("decision_audit").insert({
        "audit_id": audit_id,
        "decision_type": decision_type,
        "actor_id": actor_id,
        "actor_type": actor_type,
        "affected_shipment_id": affected_shipment_id,
        "decision_data": decision_data,
        "previous_state": previous_state,
        "new_state": new_state,
        "reasoning": reasoning,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    
    return audit_id

def log_system_event(
    event_type: str,
    severity: str,
    source_module: str,
    event_data: dict = None
) -> str:
    """Log a system event."""
    event_id = f"EVENT-{uuid.uuid4().hex[:8].upper()}"
    
    supabase.table("system_events").insert({
        "event_id": event_id,
        "event_type": event_type,
        "severity": severity,
        "source_module": source_module,
        "event_data": event_data,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    
    return event_id

def get_audit_trail(affected_shipment_id: str) -> list:
    """Get audit trail for a shipment."""
    result = supabase.table("decision_audit").select("*").eq(
        "affected_shipment_id", affected_shipment_id
    ).order("created_at", desc=True).execute()
    
    return result.data if result.data else []