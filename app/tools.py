from langchain_core.tools import tool
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from app.database import (
    get_driver,
    get_driver_shipments,
    get_shipment,
    get_current_appointment,
    get_latest_eta,
    get_facility_checkin,
    get_feasible_slots,
    get_facility,
    book_appointment,
    save_eta_update,
    save_escalation,
    get_or_create_thread,
)
from app.redis_client import place_hold, release_hold, is_slot_held_by_other

# ─────────────────────────────────────────────────────────────────────────────
# TOOLS — these are the functions the AI agent can call
# The agent decides WHEN to call them based on the conversation
# But the tools themselves are deterministic — no AI guessing inside them
# ─────────────────────────────────────────────────────────────────────────────

@tool
@traceable(name="lookup_driver_context", run_type="tool")
def lookup_driver_context(driver_id: str) -> dict:
    """
    Look up everything about a driver and their active shipment.
    Call this FIRST when any driver sends a message.
    Returns driver info, active shipments, current appointment, and latest ETA.
    """
    # Get driver
    driver = get_driver(driver_id)
    if not driver:
        return {"error": f"Driver {driver_id} not found in system"}

    # Get their active shipments
    shipments = get_driver_shipments(driver_id)
    if not shipments:
        return {
            "driver_name": driver["driver_name"],
            "driver_id": driver_id,
            "active_shipments": [],
            "message": "No active shipments found for this driver today"
        }

    # For each shipment, get appointment and ETA
    shipment_details = []
    for shp in shipments:
        appointment = get_current_appointment(shp["shipment_id"])
        latest_eta = get_latest_eta(shp["shipment_id"])
        checkin = get_facility_checkin(shp["shipment_id"])
        facility = get_facility(shp["destination_facility_id"])

        shipment_details.append({
            "shipment_id": shp["shipment_id"],
            "cargo": shp["cargo_desc"],
            "priority": shp["priority_code"],
            "status": shp["current_status"],
            "destination": facility["facility_name"] if facility else shp["destination_facility_id"],
            "facility_id": shp["destination_facility_id"],
            "required_dock_type": shp["required_dock_type"],
            "expected_unload_min": shp["expected_unload_min"],
            "current_appointment": {
                "appointment_id": appointment["appointment_id"],
                "status": appointment["appointment_status"],
                "slot_start": appointment["appointment_slots"]["slot_start_ts"],
                "slot_end": appointment["appointment_slots"]["slot_end_ts"],
            } if appointment else None,
            "latest_eta": {
                "timestamp": latest_eta["declared_eta_ts"],
                "confidence": latest_eta["confidence_code"],
                "note": latest_eta["note"],
            } if latest_eta else "No ETA update — using original plan",
            "facility_checkin": {
                "gate_in_at": checkin["gate_in_at"],
                "queue_status": checkin["queue_status"],
            } if checkin else "Not yet arrived at facility",
        })

    return {
        "driver_name": driver["driver_name"],
        "driver_id": driver_id,
        "carrier": driver["carrier_id"],
        "active_shipments": shipment_details,
        "shipment_count": len(shipment_details),
        "note": "If multiple shipments exist, ask driver which one this is about"
    }


@tool
@traceable(name="get_feasible_slots", run_type="tool")
def get_feasible_slots_tool(
    shipment_id: str,
    facility_id: str,
    after_eta_ts: str,
    dock_type: str
) -> dict:
    """
    Find available dock slots for a shipment after the driver's revised ETA.
    Only call this after you know the shipment ID and revised ETA.
    Returns up to 5 compatible slots ordered by start time.
    dock_type must be one of: STANDARD, REEFER, HEAVY
    after_eta_ts must be ISO format e.g. 2026-08-04T11:20:00+05:30
    """
    slots = get_feasible_slots(facility_id, dock_type, after_eta_ts)

    if not slots:
        return {
            "available": False,
            "message": "No compatible slots found after the given ETA. Escalation recommended.",
            "dock_type": dock_type,
            "searched_after": after_eta_ts
        }

    # Check Redis holds — filter out slots held by other shipments
    # Check Redis holds — filter out slots held by other shipments
    from datetime import datetime, timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))

    def to_ist(ts):
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return dt.astimezone(IST).strftime('%d %b %Y %I:%M %p IST')

    available_slots = []
    for slot in slots:
        if is_slot_held_by_other(slot["slot_id"], shipment_id):
            continue  # skip — another driver is actively considering this
        available_slots.append({
            "slot_id": slot["slot_id"],
            "dock_id": slot["dock_id"],
            "start_time": to_ist(slot["slot_start_ts"]),
            "end_time": to_ist(slot["slot_end_ts"]),
            "dock_type": slot["dock_type"],
            "status": "AVAILABLE"
        })

    if not available_slots:
        return {
            "available": False,
            "message": "All compatible slots are currently being processed by other requests. Try again in 2 minutes or escalate.",
        }

    return {
        "available": True,
        "slots": available_slots,
        "count": len(available_slots),
        "note": "Show these options to the driver clearly. Do NOT book until driver explicitly confirms one."
    }


@tool
@traceable(name="hold_slot", run_type="tool")
def hold_slot_tool(slot_id: str, shipment_id: str, driver_id: str) -> dict:
    """
    Place a 2-minute soft hold on a slot while the driver decides.
    Call this when you are about to show a slot to a driver for confirmation.
    This prevents another conversation from taking the same slot.
    Returns success/failure and expiry info.
    """
    result = place_hold(slot_id, shipment_id, driver_id)
    run = get_current_run_tree()
    if run is not None:
        run.tags = ["hold-acquired"] if result.get("success") else ["hold-denied"]
        run.extra = {
            "metadata": {
                "slot_id": slot_id,
                "shipment_id": shipment_id,
                "driver_id": driver_id,
                "outcome": "HOLD_ACQUIRED" if result.get("success") else "HOLD_DENIED",
            }
        }
    return result


@tool
@traceable(name="confirm_slot", run_type="tool")
def confirm_booking_tool(
    slot_id: str,
    shipment_id: str,
    driver_id: str,
    revised_eta_ts: str,
    eta_confidence: str,
    eta_note: str
) -> dict:
    """
    Confirm a slot booking after the driver explicitly agrees.
    Only call this when the driver has clearly said YES to a specific slot.
    This creates a PENDING_CONFIRMATION appointment in the database
    and saves the revised ETA.
    eta_confidence must be HIGH, MEDIUM, or LOW.
    """
    # Save the revised ETA first
    save_eta_update(
        shipment_id=shipment_id,
        eta_ts=revised_eta_ts,
        confidence=eta_confidence,
        note=eta_note,
        driver_id=driver_id
    )

    # Book the appointment
    appointment = book_appointment(shipment_id, slot_id)
    run = get_current_run_tree()
    success = "error" not in appointment
    outcome = "CONFIRMED" if success else "REJECTED_STALE_VERSION"
    expected_version = "unknown"

    if not success:
        if run is not None:
            run.tags = ["slot-confirm", "race-lost"]
            run.extra = {
                "metadata": {
                    "slot_id": slot_id,
                    "shipment_id": shipment_id,
                    "expected_version": expected_version,
                    "outcome": outcome,
                }
            }
        return {
            "success": False,
            "reason": "Booking failed in database. Please try again or escalate."
        }

    # Release the Redis hold — slot is now properly booked in DB
    release_hold(slot_id, shipment_id)

    if run is not None:
        run.tags = ["slot-confirm", "race-won"]
        run.extra = {
            "metadata": {
                "slot_id": slot_id,
                "shipment_id": shipment_id,
                "expected_version": expected_version,
                "outcome": outcome,
            }
        }

    return {
        "success": True,
        "appointment_id": appointment["appointment_id"],
        "status": "PENDING_CONFIRMATION",
        "message": "Appointment created. Awaiting warehouse confirmation.",
        "note": "Tell the driver their new slot is booked and pending warehouse sign-off."
    }


@tool
@traceable(name="release_hold", run_type="tool")
def release_hold_tool(slot_id: str, shipment_id: str) -> dict:
    """
    Release a slot hold when driver changes their mind or picks a different slot.
    Always call this if a hold exists and the driver chose something else.
    """
    result = release_hold(slot_id, shipment_id)
    run = get_current_run_tree()
    if run is not None:
        run.tags = ["hold-released"] if result.get("success") else ["hold-release-failed"]
        run.extra = {
            "metadata": {
                "slot_id": slot_id,
                "shipment_id": shipment_id,
                "outcome": "HOLD_RELEASED" if result.get("success") else "HOLD_RELEASE_FAILED",
            }
        }
    return result

def send_escalation_email(exc_id: str, shipment_id: str, driver_id: str, urgency: str, reason: str) -> None:
    """
    Stub for escalation email notification.
    Logs what WOULD be sent — replace with real SMTP/email service later.
    """
    print(
        f"[ESCALATION EMAIL] To: HumanInTheLook@gmail.com | "
        f"Ticket: {exc_id} | Urgency: {urgency} | "
        f"Shipment: {shipment_id} | Driver: {driver_id} | Reason: {reason}"
    )




@tool
@traceable(name="escalate_to_human", run_type="tool")
def escalate_to_human(
    shipment_id: str,
    driver_id: str,
    thread_id: str,
    reason: str,
    urgency: str
) -> dict:
    """
    Escalate this exception to a human operations coordinator.
    Use when: no feasible slot exists, safety concern, contradictory info,
    regulated goods, driver requests human help, or any case you cannot
    safely resolve alone.
    urgency must be one of: LOW, MEDIUM, HIGH, CRITICAL
    """
    exc_id = save_escalation(
        shipment_id=shipment_id,
        driver_id=driver_id,
        thread_id=thread_id,
        reason=reason,
        urgency=urgency
    )

    send_escalation_email(exc_id, shipment_id, driver_id, urgency, reason)

    return {
        "success": True,
        "escalation_id": exc_id,
        "urgency": urgency,
        "message": f"Escalated to human ops team. Reference: {exc_id}. A coordinator will contact the driver shortly."
    }

# ── Export all tools as a list for the agent ──────────────────────────────────
# This is what we pass to LangChain when building the agent

ALL_TOOLS = [
    lookup_driver_context,
    get_feasible_slots_tool,
    hold_slot_tool,
    confirm_booking_tool,
    release_hold_tool,
    escalate_to_human,
]