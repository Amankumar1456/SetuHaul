"""
Comprehensive slot feasibility checking.

Determines whether a specific slot is feasible for a shipment appointment,
with detailed failure reasons for auditability.

A slot is feasible if:
1. It still exists in the system (not deleted)
2. It is in OPEN status
3. No active appointment on this slot
4. Dock type matches shipment requirements
5. Slot duration accommodates expected unload time
6. Facility is still accepting appointments
7. Shipment hasn't already confirmed a different appointment for this time
"""

from typing import TypedDict
from datetime import datetime, timezone, timedelta
from app.database import supabase


class FeasibilityResult(TypedDict):
    """Result of feasibility check."""
    feasible: bool
    slot_id: str
    shipment_id: str
    reasons: list[str]  # Machine-readable failure reasons
    explanation: str  # Human-readable explanation


def check_slot_exists(slot_id: str) -> tuple[bool, str | None]:
    """Check if slot exists in database."""
    try:
        result = supabase.table("appointment_slots").select("*").eq(
            "slot_id", slot_id
        ).execute()
        if not result.data:
            return False, "SLOT_NOT_FOUND"
        return True, None
    except Exception as e:
        return False, f"SLOT_QUERY_ERROR: {str(e)}"


def check_slot_status_open(slot_id: str) -> tuple[bool, str | None]:
    """Check if slot is in OPEN status."""
    try:
        result = supabase.table("appointment_slots").select("slot_status").eq(
            "slot_id", slot_id
        ).execute()
        if not result.data:
            return False, "SLOT_NOT_FOUND"
        status = result.data[0].get("slot_status")
        if status != "OPEN":
            return False, f"SLOT_NOT_OPEN: {status}"
        return True, None
    except Exception as e:
        return False, f"SLOT_STATUS_ERROR: {str(e)}"


def check_slot_not_booked(slot_id: str) -> tuple[bool, str | None]:
    """Check if slot has no active appointment already."""
    try:
        result = supabase.table("appointments").select("appointment_id").eq(
            "slot_id", slot_id
        ).in_(
            "appointment_status",
            ["CONFIRMED", "PENDING_CONFIRMATION", "IN_PROGRESS"]
        ).execute()
        if result.data:
            # Slot already has an appointment
            existing_apt = result.data[0]
            return False, f"SLOT_ALREADY_BOOKED: {existing_apt.get('appointment_id')}"
        return True, None
    except Exception as e:
        return False, f"BOOKING_CHECK_ERROR: {str(e)}"


def check_dock_compatibility(
    slot_id: str,
    required_dock_type: str
) -> tuple[bool, str | None]:
    """Check if slot dock type matches shipment requirement."""
    try:
        result = supabase.table("appointment_slots").select("dock_type").eq(
            "slot_id", slot_id
        ).execute()
        if not result.data:
            return False, "SLOT_NOT_FOUND"
        slot_dock_type = result.data[0].get("dock_type")
        if slot_dock_type != required_dock_type:
            return False, f"DOCK_INCOMPATIBLE: slot={slot_dock_type}, required={required_dock_type}"
        return True, None
    except Exception as e:
        return False, f"DOCK_CHECK_ERROR: {str(e)}"


def check_unload_fits_slot(
    slot_id: str,
    expected_unload_min: int
) -> tuple[bool, str | None]:
    """
    Check if shipment's expected unload time fits within slot duration.
    
    Formula: slot_duration >= expected_unload_min (with buffer)
    """
    try:
        result = supabase.table("appointment_slots").select(
            "slot_start_ts, slot_end_ts"
        ).eq("slot_id", slot_id).execute()
        
        if not result.data:
            return False, "SLOT_NOT_FOUND"
        
        slot = result.data[0]
        slot_start = datetime.fromisoformat(
            slot["slot_start_ts"].replace('Z', '+00:00')
        )
        slot_end = datetime.fromisoformat(
            slot["slot_end_ts"].replace('Z', '+00:00')
        )
        
        slot_duration_min = (slot_end - slot_start).total_seconds() / 60
        
        # Add 15-minute buffer for check-in/paperwork
        required_with_buffer = expected_unload_min + 15
        
        if slot_duration_min < required_with_buffer:
            return False, (
                f"UNLOAD_TOO_LONG: slot={slot_duration_min:.0f}min, "
                f"required={required_with_buffer}min (including 15min buffer)"
            )
        return True, None
    except Exception as e:
        return False, f"UNLOAD_CHECK_ERROR: {str(e)}"


def check_facility_accepting_appointments(facility_id: str) -> tuple[bool, str | None]:
    """
    Check if facility is accepting new appointments.
    Could be extended to check facility hours, holidays, etc.
    """
    try:
        result = supabase.table("facilities").select("*").eq(
            "facility_id", facility_id
        ).execute()
        if not result.data:
            return False, "FACILITY_NOT_FOUND"
        # For now, all facilities are accepting unless marked otherwise
        # Future: add is_accepting_appointments boolean field
        return True, None
    except Exception as e:
        return False, f"FACILITY_CHECK_ERROR: {str(e)}"


def check_no_conflict_with_current_apt(
    shipment_id: str,
    slot_id: str
) -> tuple[bool, str | None]:
    """
    Check if shipment doesn't already have a CONFIRMED appointment
    for a different slot at this same time.
    """
    try:
        # Get the slot time
        slot_result = supabase.table("appointment_slots").select(
            "slot_start_ts, slot_end_ts"
        ).eq("slot_id", slot_id).execute()
        
        if not slot_result.data:
            return False, "SLOT_NOT_FOUND"
        
        slot_start = slot_result.data[0]["slot_start_ts"]
        slot_end = slot_result.data[0]["slot_end_ts"]
        
        # Check if shipment has CONFIRMED apt for same time on different slot
        current_apt = supabase.table("appointments").select(
            "appointment_id, slot_id, appointment_slots(slot_start_ts, slot_end_ts)"
        ).eq("shipment_id", shipment_id).eq(
            "appointment_status", "CONFIRMED"
        ).is_("is_current", True).execute()
        
        if current_apt.data:
            existing = current_apt.data[0]
            existing_slot_id = existing.get("slot_id")
            if existing_slot_id and existing_slot_id != slot_id:
                # Same shipment trying to book two slots at same time
                return False, f"CONFLICT: already confirmed at slot {existing_slot_id}"
        
        return True, None
    except Exception as e:
        return False, f"CONFLICT_CHECK_ERROR: {str(e)}"


def validate_slot_against_current_state(
    slot_id: str,
    shipment_id: str,
    facility_id: str,
    required_dock_type: str,
    expected_unload_min: int = 30,
) -> FeasibilityResult:
    """
    Comprehensive feasibility check for a slot.
    
    Runs all checks and returns structured result with:
    - feasible: bool
    - reasons: list of failure codes (empty if feasible)
    - explanation: human-readable summary
    
    This is called:
    1. When showing slot options to driver (get_feasible_slots_tool)
    2. Before confirming a booking (confirm_booking_tool) — **REVALIDATION**
    3. When checking if a hold is still valid
    """
    
    reasons = []
    
    # Sequential checks — fail fast
    checks = [
        ("Check 1: Slot exists", lambda: check_slot_exists(slot_id)),
        ("Check 2: Slot is OPEN", lambda: check_slot_status_open(slot_id)),
        ("Check 3: Slot not already booked", lambda: check_slot_not_booked(slot_id)),
        ("Check 4: Dock compatible", lambda: check_dock_compatibility(slot_id, required_dock_type)),
        ("Check 5: Unload fits slot", lambda: check_unload_fits_slot(slot_id, expected_unload_min)),
        ("Check 6: Facility accepting", lambda: check_facility_accepting_appointments(facility_id)),
        ("Check 7: No conflict with current", lambda: check_no_conflict_with_current_apt(shipment_id, slot_id)),
    ]
    
    for check_name, check_func in checks:
        feasible, reason = check_func()
        if not feasible:
            if reason:
                reasons.append(reason)
            # Continue checking all to get full failure list
    
    feasible = len(reasons) == 0
    
    return FeasibilityResult(
        feasible=feasible,
        slot_id=slot_id,
        shipment_id=shipment_id,
        reasons=reasons,
        explanation=(
            f"Slot {slot_id} is {'feasible' if feasible else 'NOT feasible'} "
            f"for shipment {shipment_id}. "
            f"Failures: {', '.join(reasons) if reasons else 'None'}"
        )
    )
