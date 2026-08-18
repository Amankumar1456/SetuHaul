from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.agent import run_agent
from app.redis_client import get_all_active_holds
from app.database import supabase, get_driver
import logging
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone, timedelta
import json

# ─────────────────────────────────────────────────────────────────────────────
# App — defined FIRST before anything else uses it
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SetuHaul Driver Exception Agent",
    description="AI agent for handling driver delays and dock slot coordination",
    version="1.0.0"
)

# CORS — must come right after app = FastAPI(...)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Logger
logger = logging.getLogger("uvicorn.error")

# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    driver_id: str
    message: str

class ChatResponse(BaseModel):
    driver_id: str
    response: str
    thread_id: str | None = None

class LoginRequest(BaseModel):
    driver_id: str
    phone: str

class LoginResponse(BaseModel):
    success: bool
    driver_name: str | None = None
    driver_id: str | None = None
    carrier_id: str | None = None
    message: str | None = None

# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "SetuHaul agent is running"}

# ─────────────────────────────────────────────────────────────────────────────
# Frontend pages
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/portal")
def serve_login():
    return FileResponse("frontend/index.html")

@app.get("/portal/chat")
def serve_chat():
    return FileResponse("frontend/chat.html")

@app.get("/dashboard")
def serve_dashboard():
    return FileResponse("frontend/dashboard.html")

# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=LoginResponse)
def driver_login(request: LoginRequest):
    """Verify driver identity using driver_id and phone number."""
    try:
        driver = get_driver(request.driver_id)
        if not driver:
            return LoginResponse(
                success=False,
                message="Driver ID not found. Please contact your dispatcher."
            )
        if driver["phone"] != request.phone:
            return LoginResponse(
                success=False,
                message="Phone number does not match our records."
            )
        if driver["driver_status"] != "ACTIVE":
            return LoginResponse(
                success=False,
                message="Your account is currently inactive. Contact operations."
            )
        return LoginResponse(
            success=True,
            driver_id=driver["driver_id"],
            driver_name=driver["driver_name"],
            carrier_id=driver["carrier_id"],
            message="Login successful"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────────────────────
# Driver endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/driver/{driver_id}")
def get_driver_endpoint(driver_id: str):
    """Get driver identity — used by the login flow."""
    try:
        driver = get_driver(driver_id)
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        return driver
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/driver/shipments/{driver_id}")
def get_driver_shipments_endpoint(driver_id: str):
    """Get active shipments for a driver — used by the chat UI banner."""
    try:
        from app.database import get_driver_shipments
        shipments = get_driver_shipments(driver_id)
        return {"shipments": shipments, "count": len(shipments)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────────────────────
# Chat
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Main endpoint — receives a driver message and returns agent response."""
    if not request.driver_id or not request.message:
        raise HTTPException(status_code=400, detail="driver_id and message are required")
    try:
        from app.database import get_or_create_thread
        thread_id = get_or_create_thread(request.driver_id)
        response = run_agent(request.driver_id, request.message)
        return ChatResponse(
            driver_id=request.driver_id,
            response=response,
            thread_id=thread_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/test-location")
def get_test_location():
    """Get a test driver location for demo/testing purposes."""
    try:
        from app.routing import RoutingEngine
        # Get all test locations
        locations = RoutingEngine.get_all_test_locations()
        if locations:
            # Return the first test location as default
            first_key = list(locations.keys())[0]
            first_loc = locations[first_key]
            return {
                "success": True,
                "latitude": first_loc.latitude,
                "longitude": first_loc.longitude,
                "name": first_loc.name,
                "description": f"{first_loc.name} - Test location for demonstration",
                "calculation_method": "HARDCODED"
            }
        else:
            return {"success": False, "error": "No test locations available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────────────────────
# Ops dashboard endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/ops/queue")
def get_queue():
    """All active shipments with their status."""
    try:
        result = supabase.table("shipments").select(
            "shipment_id, driver_id, current_status, priority_code, "
            "required_dock_type, cargo_desc, destination_facility_id"
        ).in_(
            "current_status",
            ["IN_TRANSIT", "WAITING", "IN_DOCK", "ASSIGNED"]
        ).execute()
        return {"shipments": result.data, "count": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ops/holds")
def get_holds():
    """All active Redis slot holds."""
    holds = get_all_active_holds()
    return {"active_holds": holds, "count": len(holds)}

@app.get("/ops/slots/{facility_id}")
def get_slots(facility_id: str):
    """All slots for a facility with their current status."""
    try:
        result = supabase.table("appointment_slots").select(
            "*, appointments(appointment_status, shipment_id, is_current)"
        ).eq("facility_id", facility_id).order("slot_start_ts").execute()
        return {"slots": result.data, "count": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ops/verify/{shipment_id}")
def verify_booking(shipment_id: str):
    """Verify what is actually booked for a shipment — ground truth check."""
    try:
        apt = supabase.table("appointments").select(
            "*, appointment_slots(slot_start_ts, slot_end_ts, dock_id, dock_type)"
        ).eq("shipment_id", shipment_id).eq("is_current", 1).execute()
        eta = supabase.table("eta_updates").select("*").eq(
            "shipment_id", shipment_id
        ).order("created_at", desc=True).limit(1).execute()
        all_holds = get_all_active_holds()
        shipment_holds = [h for h in all_holds if h["shipment_id"] == shipment_id]
        return {
            "shipment_id": shipment_id,
            "database_appointment": apt.data[0] if apt.data else None,
            "latest_eta_saved": eta.data[0] if eta.data else None,
            "active_redis_holds": shipment_holds,
            "verdict": "BOOKED" if apt.data else "NOT BOOKED"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ops/escalations")
def get_escalations():
    """All open escalations."""
    try:
        result = supabase.table("driver_exceptions").select(
            "*"
        ).eq("exception_status", "OPEN").order(
            "reported_at", desc=True
        ).execute()
        return {"escalations": result.data, "count": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ops/threads")
def get_threads():
    """All open chat threads."""
    try:
        result = supabase.table("chat_threads").select(
            "*"
        ).neq("thread_status", "CLOSED").order(
            "opened_at", desc=True
        ).limit(50).execute()
        return {"threads": result.data, "count": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────────────────────
# Warehouse Dashboard Endpoints (Phase 5)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/warehouse/{warehouse_id}/resources")
def get_warehouse_resources(warehouse_id: str):
    """Get resource availability for a warehouse (drivers, trucks, staff, machinery)."""
    try:
        from app.database import get_resource_pool
        
        # Fetch resource pool for this warehouse
        resources = get_resource_pool(warehouse_id)
        
        return {
            "success": True,
            "warehouse_id": warehouse_id,
            "resources": resources,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/warehouse/{warehouse_id}/yard")
def get_warehouse_yard(warehouse_id: str):
    """Get current yard state for a warehouse (trucks in yard and pending arrivals)."""
    try:
        from app.database import get_trucks_in_yard, get_facility
        
        # Get trucks currently in yard
        trucks_in_yard = get_trucks_in_yard(warehouse_id)
        
        # Get pending arrivals (shipments with ETA arriving at this warehouse in next 2 hours)
        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=2)
        
        pending_result = supabase.table("eta_updates").select(
            "*, shipments(shipment_id, driver_id)"
        ).eq("destination_facility_id", warehouse_id).gte(
            "declared_eta_ts", now.isoformat()
        ).lte(
            "declared_eta_ts", future.isoformat()
        ).order("declared_eta_ts").execute()
        
        arrivals = [
            {
                "truck_id": f"TRK-{e.get('shipments', {}).get('shipment_id', 'UNKNOWN')[:8]}",
                "shipment_id": e.get("shipments", {}).get("shipment_id"),
                "eta_ts": e.get("declared_eta_ts"),
                "status": "ARRIVING"
            }
            for e in (pending_result.data or [])
        ]
        
        return {
            "success": True,
            "warehouse_id": warehouse_id,
            "trucks_in_yard": trucks_in_yard,
            "arriving_trucks": arrivals,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/warehouse/{warehouse_id}/slots")
def get_warehouse_slots(warehouse_id: str):
    """Get slot timeline for a warehouse (next 24 hours across all gates)."""
    try:
        # Get slots for next 24 hours
        now = datetime.now(timezone.utc)
        tomorrow = now + timedelta(hours=24)
        
        result = supabase.table("appointment_slots").select(
            "slot_id, facility_id, gate_id, slot_start_ts, slot_end_ts, status"
        ).eq("facility_id", warehouse_id).gte(
            "slot_start_ts", now.isoformat()
        ).lte(
            "slot_start_ts", tomorrow.isoformat()
        ).order("slot_start_ts").execute()
        
        return {
            "success": True,
            "warehouse_id": warehouse_id,
            "slots": result.data if result.data else [],
            "count": len(result.data) if result.data else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/warehouse/{warehouse_id}/escalations")
def get_warehouse_escalations(warehouse_id: str):
    """Get escalations for a specific warehouse."""
    try:
        # Get open escalations related to this warehouse
        result = supabase.table("driver_exceptions").select(
            "exception_id, shipment_id, driver_id, exception_type, reported_at, "
            "exception_status, notes"
        ).eq("exception_status", "OPEN").order(
            "reported_at", desc=True
        ).execute()
        
        # Filter by warehouse (shipments going to this warehouse)
        escalations = []
        if result.data:
            for exc in result.data:
                if exc.get("shipment_id"):
                    # Check if shipment is for this warehouse
                    shipment = supabase.table("shipments").select(
                        "destination_facility_id"
                    ).eq("shipment_id", exc["shipment_id"]).limit(1).execute()
                    
                    if shipment.data and shipment.data[0].get("destination_facility_id") == warehouse_id:
                        escalations.append({
                            "escalation_id": exc.get("exception_id"),
                            "shipment_id": exc.get("shipment_id"),
                            "driver_id": exc.get("driver_id"),
                            "exception_type": exc.get("exception_type"),
                            "urgency": "HIGH" if exc.get("exception_type") == "ESCALATED" else "MEDIUM",
                            "reason": exc.get("notes", ""),
                            "reported_at": exc.get("reported_at"),
                            "status": exc.get("exception_status"),
                        })
        
        return {
            "success": True,
            "warehouse_id": warehouse_id,
            "escalations": escalations,
            "count": len(escalations),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────────────────────
# Startup diagnostics
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def log_registered_routes():
    routes = []
    for r in app.routes:
        path = getattr(r, "path", None) or getattr(r, "path_format", None)
        methods = getattr(r, "methods", None)
        if not path:
            continue
        methods_str = ",".join(sorted(list(methods))) if methods else ""
        routes.append(f"{methods_str} {path}".strip())
    logger.info("Registered routes:\n%s", "\n".join(routes))



@app.post("/ops/chat")
def ops_chat(request: ChatRequest):
    """
    Ops assistant chat endpoint — used by the dashboard assistant.
    Uses a system-level driver context instead of a real driver.
    """
    try:
        from app.database import get_or_create_thread
        # Use a fixed ops thread — not a real driver
        thread_id = f"OPS-THREAD-{request.driver_id}"
        response = run_agent("DRV001", request.message)
        return ChatResponse(
            driver_id="OPS",
            response=response,
            thread_id=thread_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    """Streaming version of chat — sends tokens as they arrive."""
    from app.database import get_or_create_thread

    def generate():
        try:
            thread_id = get_or_create_thread(request.driver_id)
            response = run_agent(request.driver_id, request.message)

            # Stream word by word for perceived speed
            words = response.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words)-1 else "")
                yield f"data: {json.dumps({'token': chunk, 'thread_id': thread_id})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")