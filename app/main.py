from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.agent import run_agent
from app.redis_client import get_all_active_holds
from app.database import supabase, get_driver
import logging

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