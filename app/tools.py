from langchain_core.tools import tool
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
import requests
import os
from datetime import datetime, timezone, timedelta
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
    save_eta_update_with_location,
    log_decision,
)
from app.redis_client import place_hold, release_hold, is_slot_held_by_other
from app.allocation import allocate_slot
from app.feasibility import validate_slot_against_current_state
from app.intent_detector import get_detector
from app.routing import RoutingEngine, get_test_locations_list

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
    from app.redis_client import r
    import json

    cache_key = f"driver_ctx:{driver_id}"
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)
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

    result = {
        "driver_name": driver["driver_name"],
        "driver_id": driver_id,
        "carrier": driver["carrier_id"],
        "active_shipments": shipment_details,
        "shipment_count": len(shipment_details),
        "note": "If multiple shipments exist, ask driver which one this is about"
    }
    r.setex(cache_key, 300, json.dumps(result))
    return result


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
    
    Returns ranked slot options using explicit allocation policy.
    Slots are scored by shipment priority, availability, and time-fit.
    
    Call this after you know: shipment_id, facility_id, revised ETA, required dock_type
    
    dock_type must be one of: STANDARD, REEFER, HEAVY
    after_eta_ts must be ISO format e.g. 2026-08-04T11:20:00+05:30
    
    Each slot includes:
    - slot_id: unique identifier
    - rank: position in allocation ranking (1 = best)
    - score: numerical allocation score
    - start/end times: in IST
    - allocation_reason: why this slot ranked here
    """
    # Get raw candidate slots from database
    candidates = get_feasible_slots(facility_id, dock_type, after_eta_ts)

    if not candidates:
        return {
            "available": False,
            "message": "No compatible slots found after the given ETA. Escalation recommended.",
            "dock_type": dock_type,
            "searched_after": after_eta_ts
        }

    # Filter out slots held by OTHER shipments (same shipment can refresh)
    IST = timezone(timedelta(hours=5, minutes=30))

    def to_ist(ts):
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return dt.astimezone(IST).strftime('%d %b %Y %I:%M %p IST')

    # Revalidate each candidate against current system state
    valid_candidates = []
    for slot in candidates:
        if is_slot_held_by_other(slot["slot_id"], shipment_id):
            continue  # Another driver holds this slot
        
        # Check comprehensive feasibility
        feasibility = validate_slot_against_current_state(
            slot_id=slot["slot_id"],
            shipment_id=shipment_id,
            facility_id=facility_id,
            required_dock_type=dock_type,
            expected_unload_min=30  # Default, could be from shipment
        )
        
        if feasibility["feasible"]:
            valid_candidates.append(slot)

    if not valid_candidates:
        return {
            "available": False,
            "message": "All compatible slots are currently unavailable, held by other drivers, or no longer feasible. Try again in 2 minutes or escalate.",
        }

    # Apply allocation policy to rank candidates
    allocation = allocate_slot(
        candidates=valid_candidates,
        shipment_id=shipment_id,
    )

    # Format response with allocation ranking
    slots_response = []
    if allocation:
        for rank_item in allocation["ranking"]:
            # Find full slot data
            full_slot = next(
                (s for s in valid_candidates if s["slot_id"] == rank_item["slot_id"]),
                None
            )
            if full_slot:
                slots_response.append({
                    "slot_id": rank_item["slot_id"],
                    "dock_id": rank_item["dock_id"],
                    "rank": rank_item["position"],
                    "score": rank_item["score"],
                    "start_time": to_ist(full_slot["slot_start_ts"]),
                    "end_time": to_ist(full_slot["slot_end_ts"]),
                    "dock_type": full_slot["dock_type"],
                    "status": "AVAILABLE",
                    "allocation_reason": rank_item["explanation"],
                })

    return {
        "available": True,
        "slots": slots_response,
        "count": len(slots_response),
        "allocation_policy_applied": True,
        "allocation_reasoning": allocation["reason"] if allocation else "No allocation policy",
        "note": "Slots are ranked by priority-based allocation policy. Slot #1 is recommended. Do NOT book until driver explicitly confirms one."
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
    
    CRITICAL: This tool performs revalidation before confirming to prevent
    race conditions where a slot was shown to the driver but is no longer
    available when they try to book it.
    
    Only call this when the driver has clearly said YES to a specific slot.
    
    This will:
    1. Revalidate that the slot is still feasible
    2. Save the revised ETA
    3. Create a PENDING_CONFIRMATION appointment
    4. Release the Redis hold
    
    Returns success/failure with detailed reason if revalidation fails.
    """
    
    # Get shipment info needed for revalidation
    shipment = get_shipment(shipment_id)
    if not shipment:
        return {
            "success": False,
            "reason": "Shipment not found",
            "action": "Please try again or contact operations."
        }
    
    facility_id = shipment.get("destination_facility_id")
    dock_type = shipment.get("required_dock_type")
    expected_unload_min = shipment.get("expected_unload_min", 30)
    
    # REVALIDATION STEP 1: Check if slot is still feasible
    # This is the critical race-condition prevention check
    feasibility = validate_slot_against_current_state(
        slot_id=slot_id,
        shipment_id=shipment_id,
        facility_id=facility_id,
        required_dock_type=dock_type,
        expected_unload_min=expected_unload_min
    )
    
    if not feasibility["feasible"]:
        # Slot is no longer available
        return {
            "success": False,
            "reason": "Slot is no longer available",
            "failure_reasons": feasibility["reasons"],
            "explanation": feasibility["explanation"],
            "action": "The slot you selected was taken or became unavailable. Please request alternative slots and try again.",
        }
    
    # REVALIDATION STEP 2: Check if we still hold this slot in Redis
    # (hold may have expired or been released)
    hold = is_slot_held_by_other(slot_id, shipment_id)
    if hold:
        # Different shipment holds it now
        return {
            "success": False,
            "reason": "Slot hold expired or was taken by another request",
            "action": "Please request alternative slots and try again.",
        }
    
    run = get_current_run_tree()
    
    # BOOKING STEP 1: Save the revised ETA
    save_eta_update(
        shipment_id=shipment_id,
        eta_ts=revised_eta_ts,
        confidence=eta_confidence,
        note=eta_note,
        driver_id=driver_id
    )

    # BOOKING STEP 2: Book the appointment
    appointment = book_appointment(shipment_id, slot_id)
    
    success = "error" not in appointment
    outcome = "CONFIRMED" if success else "REJECTED_STALE_VERSION"

    if not success:
        if run is not None:
            run.tags = ["slot-confirm", "race-lost"]
            run.extra = {
                "metadata": {
                    "slot_id": slot_id,
                    "shipment_id": shipment_id,
                    "outcome": outcome,
                    "reason": "Database booking failed",
                }
            }
        return {
            "success": False,
            "reason": "Booking failed in database. Likely the slot was booked by another request just now.",
            "action": "Please request alternative slots and try again.",
        }

    # BOOKING STEP 3: Release the Redis hold — slot is now properly booked in DB
    release_hold(slot_id, shipment_id)

    if run is not None:
        run.tags = ["slot-confirm", "race-won"]
        run.extra = {
            "metadata": {
                "slot_id": slot_id,
                "shipment_id": shipment_id,
                "outcome": outcome,
                "revalidation": "PASSED",
            }
        }

    return {
        "success": True,
        "appointment_id": appointment["appointment_id"],
        "status": "PENDING_CONFIRMATION",
        "message": "Appointment created. Awaiting warehouse confirmation.",
        "note": "Tell the driver their new slot is booked and pending warehouse sign-off.",
        "allocation_validated": True,
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

@tool
@traceable(name="get_ops_summary", run_type="tool")
def get_ops_summary() -> dict:
    """
    Get a real-time summary of facility operations for the current day.
    Returns counts and snapshots of:
    - Shipments in transit, waiting, and in dock
    - Active slot holds (being negotiated)
    - Open escalations (waiting for human attention)
    - Active chat threads (ongoing driver conversations)
    
    Use this to answer questions like "how many escalations are open?" 
    or "what's the current facility load?"
    """
    # Get API base URL from environment, default to localhost for local dev
    api_base = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    
    try:
        # Fetch queue data (shipments by status)
        queue_res = requests.get(f"{api_base}/ops/queue", timeout=5)
        queue_data = queue_res.json() if queue_res.status_code == 200 else {"shipments": []}
        
        # Fetch holds data
        holds_res = requests.get(f"{api_base}/ops/holds", timeout=5)
        holds_data = holds_res.json() if holds_res.status_code == 200 else {"active_holds": []}
        
        # Fetch escalations data
        esc_res = requests.get(f"{api_base}/ops/escalations", timeout=5)
        esc_data = esc_res.json() if esc_res.status_code == 200 else {"escalations": []}
        
        # Fetch threads data
        threads_res = requests.get(f"{api_base}/ops/threads", timeout=5)
        threads_data = threads_res.json() if threads_res.status_code == 200 else {"threads": []}
        
        shipments = queue_data.get("shipments", [])
        holds = holds_data.get("active_holds", [])
        escalations = esc_data.get("escalations", [])
        threads = threads_data.get("threads", [])
        
        # Parse shipments by status
        in_transit = [s for s in shipments if s.get("current_status") == "IN_TRANSIT"]
        waiting = [s for s in shipments if s.get("current_status") == "WAITING"]
        in_dock = [s for s in shipments if s.get("current_status") == "IN_DOCK"]
        
        # Count open threads (exclude CLOSED)
        open_threads = [t for t in threads if t.get("thread_status") != "CLOSED"]
        
        # Build summary with both counts and detail lists
        summary = {
            "queue": {
                "in_transit_count": len(in_transit),
                "in_transit": [
                    {
                        "shipment_id": s.get("shipment_id"),
                        "driver_id": s.get("driver_id"),
                        "priority": s.get("priority_code"),
                        "destination": s.get("destination_facility_id"),
                    }
                    for s in in_transit[:5]  # Top 5
                ],
            },
            "waiting_count": len(waiting),
            "in_dock_count": len(in_dock),
            "total_shipments": len(shipments),
            
            "holds": {
                "active_holds_count": len(holds),
                "active_holds": [
                    {
                        "slot_id": h.get("slot_id"),
                        "shipment_id": h.get("shipment_id"),
                        "held_by_driver": h.get("driver_id"),
                        "held_since": h.get("hold_ts"),
                        "expires_at": h.get("expires_at"),
                    }
                    for h in holds
                ],
            },
            
            "escalations": {
                "open_escalations_count": len(escalations),
                "open_escalations": [
                    {
                        "escalation_id": e.get("escalation_id"),
                        "shipment_id": e.get("shipment_id"),
                        "driver_id": e.get("driver_id"),
                        "reason": e.get("reason"),
                        "urgency": e.get("urgency"),
                        "reported_at": e.get("reported_at"),
                    }
                    for e in escalations
                ],
            },
            
            "threads": {
                "open_threads_count": len(open_threads),
                "total_threads": len(threads),
                "open_threads": [
                    {
                        "thread_id": t.get("thread_id"),
                        "driver_id": t.get("driver_id"),
                        "shipment_id": t.get("shipment_id"),
                        "status": t.get("thread_status"),
                        "opened_at": t.get("opened_at"),
                    }
                    for t in open_threads[:10]  # Top 10
                ],
            },
        }
        
        return {
            "success": True,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            **summary
        }
        
    except requests.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to fetch ops data: {str(e)}",
            "message": "Please try again or contact operations directly."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error processing ops summary: {str(e)}",
            "message": "Please try again or contact operations directly."
        }


# ── Exception Detection and Routing ───────────────────────────────────────────

@tool
@traceable(name="detect_exception_type", run_type="tool")
def detect_exception_type(
    message: str,
    thread_id: str
) -> dict:
    """
    Detect the type of exception from a driver's message.
    Classifies into: MECHANICAL_FAILURE, DRIVER_SICKNESS, TRAFFIC_CONGESTION, 
    POLICE_CHECKPOINT, FACILITY_BLOCKED, or GENERIC_DELAY.
    
    Returns the detected exception type and what follow-up questions to ask.
    Use this EARLY in the conversation when the driver reports a problem.
    
    Tracks conversation state so repeated calls refine the classification.
    """
    detector = get_detector()
    context = detector.detect_exception_type(message, thread_id)
    
    return {
        "exception_type": context.exception_type.value,
        "confidence": round(context.confidence, 2),
        "aspects_collected": context.aspects_collected,
        "aspects_needed": context.aspects_needed,
        "follow_up_questions": context.follow_up_questions,
        "reasoning": context.reasoning,
        "next_step": f"Ask follow-up questions to collect: {', '.join(context.aspects_needed)}" if context.aspects_needed else "All aspects collected. Ready to resolve."
    }


@tool
@traceable(name="calculate_eta_with_location", run_type="tool")
def calculate_eta_with_location(
    driver_latitude: float,
    driver_longitude: float,
    destination_facility_id: str,
    shipment_id: str = None
) -> dict:
    """
    Calculate ETA from driver's current location to destination warehouse.
    Uses hardcoded warehouse coordinates and simple distance calculation.
    
    Args:
        driver_latitude: Driver's current latitude
        driver_longitude: Driver's current longitude
        destination_facility_id: Target warehouse (FAC-001, FAC-002, etc.)
        shipment_id: Optional shipment ID to log the decision
    
    Returns:
        ETA info with distance, duration, and calculated arrival time.
        Saves the calculation to the database.
    """
    # Calculate route using routing engine
    eta_data = RoutingEngine.calculate_eta_for_driver(
        driver_lat=driver_latitude,
        driver_lng=driver_longitude,
        destination_facility_id=destination_facility_id
    )
    
    if "error" in eta_data:
        return {"success": False, "error": eta_data["error"]}
    
    # Save to database if shipment_id provided
    if shipment_id:
        save_eta_update_with_location(
            shipment_id=shipment_id,
            eta_ts=eta_data["calculated_eta_ts"],
            confidence="MEDIUM",
            note=eta_data.get("note", "Calculated from driver location"),
            driver_lat=driver_latitude,
            driver_lng=driver_longitude,
            duration_min=eta_data["duration_min"],
            distance_km=eta_data["distance_km"]
        )
        
        # Log decision
        log_decision(
            decision_type="ETA_RECALCULATION",
            actor_id=f"SYSTEM-{destination_facility_id}",
            actor_type="SYSTEM",
            affected_shipment_id=shipment_id,
            decision_data=eta_data,
            reasoning="Driver location shared; ETA recalculated using distance formula"
        )
    
    return {
        "success": True,
        "distance_km": eta_data["distance_km"],
        "duration_min": eta_data["duration_min"],
        "calculated_eta_ts": eta_data["calculated_eta_ts"],
        "confidence": eta_data["confidence"],
        "calculation_method": "HARDCODED",
        "start_location": eta_data["start_location"],
        "end_location": eta_data["end_location"],
        "note": eta_data["note"]
    }


@tool
@traceable(name="get_test_location_for_driver", run_type="tool")
def get_test_location_for_driver(location_key: str = None) -> dict:
    """
    Get a test driver location for testing without real GPS.
    Used for demos and testing the ETA calculation flow.
    
    If location_key not provided, returns all available test locations.
    Test locations are hardcoded between warehouses.
    
    Returns:
        Dictionary with location coordinates and metadata.
    """
    if location_key:
        location = RoutingEngine.get_test_location(location_key)
        if location:
            return {
                "success": True,
                "location_key": location_key,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "name": location.name,
                "description": f"{location.name} - Use for testing"
            }
        else:
            return {
                "success": False,
                "error": f"Test location '{location_key}' not found"
            }
    else:
        # Return all available test locations
        locations = get_test_locations_list()
        return {
            "success": True,
            "available_locations": locations,
            "count": len(locations),
            "instruction": "Use any of these location_key values with get_test_location_for_driver to get coordinates"
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
    get_ops_summary,
    detect_exception_type,
    calculate_eta_with_location,
    get_test_location_for_driver,
]
