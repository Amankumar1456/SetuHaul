-- SetuHaul Application Layer Architecture Migration
-- Implements 10 Application Layers for Transit Management System
-- Date: 2026-08-18

-- ============================================================================
-- LAYER 1: IDENTITY (Already exists, no changes needed)
-- ============================================================================
-- drivers table
-- carriers table  
-- users table

-- ============================================================================
-- LAYER 2: WAREHOUSE - Enhanced with Location & Gates
-- ============================================================================

ALTER TABLE facilities ADD COLUMN IF NOT EXISTS (
    facility_lat DECIMAL(10, 8),
    facility_lng DECIMAL(11, 8),
    facility_code VARCHAR(10),
    open_time_24h INT DEFAULT 7,
    close_time_24h INT DEFAULT 18,
    max_concurrent_trucks INT DEFAULT 10,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS facility_gates (
    gate_id VARCHAR PRIMARY KEY,
    facility_id VARCHAR NOT NULL REFERENCES facilities(facility_id),
    gate_name VARCHAR NOT NULL,
    gate_number INT,
    gate_type VARCHAR DEFAULT 'DUAL', -- INBOUND, OUTBOUND, DUAL
    gate_lat DECIMAL(10, 8),
    gate_lng DECIMAL(11, 8),
    capacity_per_hour INT DEFAULT 2,
    status VARCHAR DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS facility_capacity_rules (
    rule_id VARCHAR PRIMARY KEY,
    facility_id VARCHAR NOT NULL REFERENCES facilities(facility_id),
    dock_type VARCHAR NOT NULL,
    max_concurrent_trucks INT DEFAULT 5,
    queue_limit INT DEFAULT 20,
    buffer_time_min INT DEFAULT 15,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(facility_id, dock_type)
);

-- ============================================================================
-- LAYER 3: RESOURCE - Track Warehouse Resources
-- ============================================================================

CREATE TABLE IF NOT EXISTS resource_pool (
    pool_id VARCHAR PRIMARY KEY,
    warehouse_id VARCHAR NOT NULL REFERENCES facilities(facility_id),
    resource_type VARCHAR NOT NULL, -- DRIVER, TRUCK, STAFF, MACHINERY
    total_count INT DEFAULT 0,
    available_count INT DEFAULT 0,
    assigned_count INT DEFAULT 0,
    in_transit_count INT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(warehouse_id, resource_type)
);

CREATE TABLE IF NOT EXISTS driver_availability (
    driver_id VARCHAR PRIMARY KEY REFERENCES drivers(driver_id),
    current_warehouse_id VARCHAR REFERENCES facilities(facility_id),
    home_warehouse_id VARCHAR REFERENCES facilities(facility_id),
    available_from TIMESTAMPTZ,
    available_until TIMESTAMPTZ,
    status VARCHAR DEFAULT 'AVAILABLE', -- AVAILABLE, ASSIGNED, IN_TRANSIT, ON_BREAK, UNAVAILABLE
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS truck_pool (
    truck_id VARCHAR PRIMARY KEY,
    warehouse_id VARCHAR NOT NULL REFERENCES facilities(facility_id),
    truck_plate VARCHAR UNIQUE NOT NULL,
    status VARCHAR DEFAULT 'AVAILABLE', -- AVAILABLE, ASSIGNED, IN_YARD, LOADING, IN_TRANSIT, UNLOADING
    current_location_lat DECIMAL(10, 8),
    current_location_lng DECIMAL(11, 8),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- LAYER 4: SHIPMENT (Already exists, no changes needed)
-- ============================================================================
-- shipments table
-- shipment_items table (if needed)

-- ============================================================================
-- LAYER 5: SCHEDULING (Enhanced with Holds)
-- ============================================================================

ALTER TABLE appointment_slots ADD COLUMN IF NOT EXISTS (
    gate_id VARCHAR REFERENCES facility_gates(gate_id),
    dock_id VARCHAR,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS slot_holds (
    hold_id VARCHAR PRIMARY KEY,
    slot_id VARCHAR NOT NULL REFERENCES appointment_slots(slot_id),
    shipment_id VARCHAR NOT NULL REFERENCES shipments(shipment_id),
    driver_id VARCHAR REFERENCES drivers(driver_id),
    held_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    released_at TIMESTAMPTZ
);

-- ============================================================================
-- LAYER 6: YARD - Truck Arrival & Movement
-- ============================================================================

CREATE TABLE IF NOT EXISTS yard_states (
    yard_state_id VARCHAR PRIMARY KEY,
    truck_id VARCHAR NOT NULL REFERENCES truck_pool(truck_id),
    facility_id VARCHAR NOT NULL REFERENCES facilities(facility_id),
    state VARCHAR NOT NULL, -- EXPECTED, ARRIVED, DOCKED, UNLOADING, DEPARTED
    state_timestamp TIMESTAMPTZ DEFAULT NOW(),
    gate_id VARCHAR REFERENCES facility_gates(gate_id),
    queue_position INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS truck_dock_assignments (
    assignment_id VARCHAR PRIMARY KEY,
    truck_id VARCHAR NOT NULL REFERENCES truck_pool(truck_id),
    facility_id VARCHAR NOT NULL REFERENCES facilities(facility_id),
    dock_id VARCHAR,
    gate_id VARCHAR REFERENCES facility_gates(gate_id),
    assigned_at TIMESTAMPTZ,
    dock_entry_at TIMESTAMPTZ,
    dock_exit_at TIMESTAMPTZ,
    unload_duration_min INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS yard_queue (
    queue_entry_id VARCHAR PRIMARY KEY,
    facility_id VARCHAR NOT NULL REFERENCES facilities(facility_id),
    truck_id VARCHAR NOT NULL REFERENCES truck_pool(truck_id),
    shipment_id VARCHAR REFERENCES shipments(shipment_id),
    queue_position INT,
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    departed_at TIMESTAMPTZ,
    status VARCHAR DEFAULT 'WAITING' -- WAITING, IN_PROGRESS, COMPLETED, CANCELLED
);

-- ============================================================================
-- LAYER 7: ETA - Enhanced with Location-based Calculations
-- ============================================================================

ALTER TABLE eta_updates ADD COLUMN IF NOT EXISTS (
    driver_lat DECIMAL(10, 8),
    driver_lng DECIMAL(11, 8),
    calculated_distance_km DECIMAL(8, 2),
    calculated_duration_min INT,
    calculation_method VARCHAR DEFAULT 'DECLARED', -- DECLARED, GPS_CALCULATED, HARDCODED
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- LAYER 8: TRACKING - Driver & Truck Location History
-- ============================================================================

CREATE TABLE IF NOT EXISTS driver_location_history (
    location_id VARCHAR PRIMARY KEY,
    driver_id VARCHAR NOT NULL REFERENCES drivers(driver_id),
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    accuracy_m INT,
    source VARCHAR NOT NULL, -- GPS, MANUAL, SYSTEM_ASSIGNED
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    used_for_eta BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gate_logs (
    log_id VARCHAR PRIMARY KEY,
    facility_id VARCHAR NOT NULL REFERENCES facilities(facility_id),
    gate_id VARCHAR REFERENCES facility_gates(gate_id),
    truck_id VARCHAR REFERENCES truck_pool(truck_id),
    shipment_id VARCHAR REFERENCES shipments(shipment_id),
    event_type VARCHAR NOT NULL, -- GATE_IN, GATE_OUT, QUEUE_ENTRY, QUEUE_EXIT, DOCK_START, DOCK_END
    event_timestamp TIMESTAMPTZ DEFAULT NOW(),
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- LAYER 9: NOTIFICATION - Alerts & Escalations (Enhanced)
-- ============================================================================

ALTER TABLE escalations ADD COLUMN IF NOT EXISTS (
    warehouse_id VARCHAR REFERENCES facilities(facility_id),
    urgency_level VARCHAR DEFAULT 'NORMAL', -- LOW, NORMAL, HIGH, CRITICAL
    manual_override_by VARCHAR,
    manual_override_reason TEXT,
    manual_override_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
) IF NOT EXISTS;

CREATE TABLE IF NOT EXISTS notifications (
    notification_id VARCHAR PRIMARY KEY,
    recipient_type VARCHAR NOT NULL, -- DRIVER, OPS_TEAM, ADMIN
    recipient_id VARCHAR NOT NULL,
    notification_type VARCHAR NOT NULL, -- SLOT_AVAILABLE, DELAY_ALERT, ESCALATION, SYSTEM_EVENT, LOCATION_REQUIRED
    title VARCHAR NOT NULL,
    message TEXT NOT NULL,
    priority VARCHAR DEFAULT 'NORMAL', -- LOW, NORMAL, HIGH, CRITICAL
    status VARCHAR DEFAULT 'PENDING', -- PENDING, SENT, READ, FAILED
    requires_action BOOLEAN DEFAULT FALSE,
    action_type VARCHAR, -- SHARE_LOCATION, CONFIRM_ETA, ACCEPT_SLOT
    created_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ
);

-- ============================================================================
-- LAYER 10: REPORTING - Decision Audit & Analytics
-- ============================================================================

CREATE TABLE IF NOT EXISTS decision_audit (
    audit_id VARCHAR PRIMARY KEY,
    decision_type VARCHAR NOT NULL, -- SLOT_ALLOCATION, ESCALATION, OVERRIDE, EXCEPTION_HANDLER
    actor_id VARCHAR NOT NULL,
    actor_type VARCHAR NOT NULL, -- LLM_AGENT, HUMAN_OPS, SYSTEM
    affected_shipment_id VARCHAR REFERENCES shipments(shipment_id),
    decision_data JSONB,
    previous_state JSONB,
    new_state JSONB,
    reasoning TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_events (
    event_id VARCHAR PRIMARY KEY,
    event_type VARCHAR NOT NULL,
    severity VARCHAR NOT NULL, -- INFO, WARNING, ERROR, CRITICAL
    source_module VARCHAR NOT NULL,
    event_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS performance_metrics (
    metric_id VARCHAR PRIMARY KEY,
    metric_name VARCHAR NOT NULL,
    metric_value DECIMAL(10, 2),
    metric_unit VARCHAR,
    warehouse_id VARCHAR REFERENCES facilities(facility_id),
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_facility_gates_facility_id ON facility_gates(facility_id);
CREATE INDEX IF NOT EXISTS idx_resource_pool_warehouse_id ON resource_pool(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_driver_availability_warehouse_id ON driver_availability(current_warehouse_id);
CREATE INDEX IF NOT EXISTS idx_truck_pool_warehouse_id ON truck_pool(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_slot_holds_slot_id ON slot_holds(slot_id);
CREATE INDEX IF NOT EXISTS idx_slot_holds_expires_at ON slot_holds(expires_at);
CREATE INDEX IF NOT EXISTS idx_yard_states_facility_id ON yard_states(facility_id);
CREATE INDEX IF NOT EXISTS idx_yard_states_truck_id ON yard_states(truck_id);
CREATE INDEX IF NOT EXISTS idx_yard_states_state ON yard_states(state);
CREATE INDEX IF NOT EXISTS idx_driver_location_history_driver_id ON driver_location_history(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_location_history_recorded_at ON driver_location_history(recorded_at);
CREATE INDEX IF NOT EXISTS idx_gate_logs_facility_id ON gate_logs(facility_id);
CREATE INDEX IF NOT EXISTS idx_gate_logs_shipment_id ON gate_logs(shipment_id);
CREATE INDEX IF NOT EXISTS idx_decision_audit_shipment_id ON decision_audit(affected_shipment_id);
CREATE INDEX IF NOT EXISTS idx_decision_audit_created_at ON decision_audit(created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_recipient_id ON notifications(recipient_id);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE facility_gates IS 'Layer 2: Warehouse gate information with location coordinates';
COMMENT ON TABLE resource_pool IS 'Layer 3: Warehouse resource availability (drivers, trucks, staff)';
COMMENT ON TABLE yard_states IS 'Layer 6: Truck yard state transitions (Expected → Arrived → Docked → Departed)';
COMMENT ON TABLE driver_location_history IS 'Layer 8: Driver GPS location history for ETA calculations';
COMMENT ON TABLE decision_audit IS 'Layer 10: Audit trail for all system decisions (allocation, escalation, overrides)';

PRINT 'Migration completed successfully. All 10 Application Layers implemented.';
