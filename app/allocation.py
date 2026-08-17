"""
Deterministic allocation policy for dock slot assignment.

This module implements the business logic for ranking and selecting dock slots
when multiple options are available to a shipment. The policy ensures:
- Explicit, auditable decision-making
- Predictable behavior under load
- Fair distribution of scarce capacity
- Priority-based allocation
- Machine-readable reasoning

Key Principle: The allocation policy is deterministic and does NOT use LLM reasoning.
Allocation decisions are made by explicit business rules, not by the agent.
"""

from typing import Optional, TypedDict
from datetime import datetime, timezone, timedelta
from app.database import supabase


class AllocationReason(TypedDict):
    """Audit trail for an allocation decision."""
    selected_slot_id: str
    shipment_id: str
    priority: str
    score: float
    ranking: list[dict]  # All candidates with scores
    reason: str  # Human-readable explanation


def get_shipment_info(shipment_id: str) -> dict | None:
    """Get shipment details for allocation scoring."""
    result = supabase.table("shipments").select(
        "shipment_id, priority_code, expected_unload_min, required_dock_type"
    ).eq("shipment_id", shipment_id).execute()
    return result.data[0] if result.data else None


def score_slot(
    slot: dict,
    shipment_priority: str,
    expected_unload_min: int,
) -> dict:
    """
    Score a single slot candidate for allocation.
    
    Scoring factors (in order of priority):
    1. Slot availability (must have capacity)
    2. Shipment priority alignment (CRITICAL > HIGH > NORMAL > LOW)
    3. Slot start time fit (earlier is better for urgent shipments)
    4. Dock congestion (fewer overlapping appointments is better)
    
    Returns: {
        "slot_id": str,
        "score": float,
        "factors": {
            "priority_boost": float,
            "time_cost": float,
            "congestion_cost": float
        },
        "explanation": str
    }
    """
    
    # Priority scoring (0-100 range)
    priority_scores = {
        "CRITICAL": 100.0,
        "HIGH": 75.0,
        "NORMAL": 50.0,
        "LOW": 25.0,
    }
    priority_boost = priority_scores.get(shipment_priority, 50.0)
    
    # Time-based scoring
    # Earlier slots are preferred for CRITICAL shipments, later slots OK for LOW
    # This prevents urgent shipments from being forced into distant slots
    try:
        slot_start = datetime.fromisoformat(
            slot["slot_start_ts"].replace('Z', '+00:00')
        )
        now = datetime.now(timezone.utc)
        minutes_ahead = (slot_start - now).total_seconds() / 60
        
        # Time cost: prefer slots within 2 hours for CRITICAL, 6 hours for others
        if shipment_priority == "CRITICAL":
            time_cost = max(0, (minutes_ahead - 120) / 60)  # 0 if within 2 hrs
        else:
            time_cost = max(0, (minutes_ahead - 360) / 60)  # 0 if within 6 hrs
    except Exception:
        time_cost = 0  # If can't parse time, no penalty
    
    # Congestion scoring (simplified)
    # Could be expanded to query overlapping appointments
    congestion_cost = 0  # Placeholder for future: analyze dock utilization
    
    # Composite score (higher is better)
    # priority_boost dominates, but time cost can affect ties
    score = priority_boost - (time_cost * 2.0) - (congestion_cost * 1.0)
    
    return {
        "slot_id": slot["slot_id"],
        "dock_id": slot["dock_id"],
        "slot_start_ts": slot["slot_start_ts"],
        "score": score,
        "factors": {
            "priority_boost": priority_boost,
            "time_cost": time_cost,
            "congestion_cost": congestion_cost,
        },
        "explanation": (
            f"Priority: {shipment_priority} ({priority_boost:.0f}pts), "
            f"Time distance: {time_cost:.1f}hrs ahead, "
            f"Congestion: {congestion_cost:.1f}"
        ),
    }


def allocate_slot(
    candidates: list[dict],
    shipment_id: str,
    shipment_priority: str | None = None,
    expected_unload_min: int = 30,
) -> AllocationReason | None:
    """
    Select the best slot for a shipment from a list of candidates.
    
    Uses explicit ranking policy to ensure:
    - Deterministic decisions
    - Auditability (can explain why slot X was chosen over Y)
    - Fair priority-based allocation
    
    Args:
        candidates: List of slot dicts from get_feasible_slots()
        shipment_id: ID of shipment being allocated
        shipment_priority: Priority code (CRITICAL|HIGH|NORMAL|LOW)
                          If None, fetched from database
        expected_unload_min: Duration needed at dock (minutes)
    
    Returns:
        AllocationReason dict with:
        - selected_slot_id: Chosen slot
        - ranking: All candidates scored and ranked
        - reason: Explanation of decision
        
        OR None if no candidates
    """
    
    if not candidates:
        return None
    
    # Get shipment info if not provided
    if not shipment_priority:
        shipment_info = get_shipment_info(shipment_id)
        if not shipment_info:
            shipment_priority = "NORMAL"  # Default
        else:
            shipment_priority = shipment_info.get("priority_code", "NORMAL")
            expected_unload_min = shipment_info.get("expected_unload_min", 30)
    
    # Score all candidates
    scored = []
    for candidate in candidates:
        scored_result = score_slot(
            candidate,
            shipment_priority,
            expected_unload_min,
        )
        scored_result["candidate_slot"] = candidate  # Keep full slot data
        scored.append(scored_result)
    
    # Sort by score (descending) — highest score is best
    ranked = sorted(scored, key=lambda x: x["score"], reverse=True)
    
    # Select top candidate
    selected = ranked[0]
    
    return AllocationReason(
        selected_slot_id=selected["slot_id"],
        shipment_id=shipment_id,
        priority=shipment_priority,
        score=selected["score"],
        ranking=[
            {
                "position": i + 1,
                "slot_id": r["slot_id"],
                "dock_id": r["dock_id"],
                "score": r["score"],
                "explanation": r["explanation"],
            }
            for i, r in enumerate(ranked[:5])  # Top 5
        ],
        reason=f"Selected slot {selected['slot_id']} (score: {selected['score']:.1f}) for {shipment_priority} shipment {shipment_id} based on priority + time availability"
    )
