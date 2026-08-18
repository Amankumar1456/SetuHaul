-- Seed Initial Data for SetuHaul
-- Hardcoded warehouse locations and gate information
-- Date: 2026-08-18

-- ============================================================================
-- WAREHOUSE LOCATIONS (Layer 2: Warehouse)
-- Hardcoded coordinates for 6 warehouses
-- ============================================================================

-- Update facilities with hardcoded location data
UPDATE facilities SET 
    facility_lat = 18.5204,
    facility_lng = 73.8567,
    facility_code = 'WH-A',
    open_time_24h = 7,
    close_time_24h = 18,
    max_concurrent_trucks = 10
WHERE facility_id = 'FAC-001' OR facility_name LIKE '%Warehouse A%';

UPDATE facilities SET 
    facility_lat = 18.5220,
    facility_lng = 73.8585,
    facility_code = 'WH-B',
    open_time_24h = 7,
    close_time_24h = 18,
    max_concurrent_trucks = 10
WHERE facility_id = 'FAC-002' OR facility_name LIKE '%Warehouse B%';

UPDATE facilities SET 
    facility_lat = 18.5190,
    facility_lng = 73.8550,
    facility_code = 'WH-C',
    open_time_24h = 7,
    close_time_24h = 18,
    max_concurrent_trucks = 8
WHERE facility_id = 'FAC-003' OR facility_name LIKE '%Warehouse C%';

UPDATE facilities SET 
    facility_lat = 18.5240,
    facility_lng = 73.8600,
    facility_code = 'WH-D',
    open_time_24h = 7,
    close_time_24h = 18,
    max_concurrent_trucks = 8
WHERE facility_id = 'FAC-004' OR facility_name LIKE '%Warehouse D%';

UPDATE facilities SET 
    facility_lat = 18.5170,
    facility_lng = 73.8530,
    facility_code = 'WH-E',
    open_time_24h = 7,
    close_time_24h = 18,
    max_concurrent_trucks = 6
WHERE facility_id = 'FAC-005' OR facility_name LIKE '%Warehouse E%';

UPDATE facilities SET 
    facility_lat = 18.5260,
    facility_lng = 73.8620,
    facility_code = 'WH-F',
    open_time_24h = 7,
    close_time_24h = 18,
    max_concurrent_trucks = 6
WHERE facility_id = 'FAC-006' OR facility_name LIKE '%Warehouse F%';

-- ============================================================================
-- FACILITY GATES (Layer 2: Warehouse Gates)
-- Each warehouse has 6 gates (A1-A6, B1-B6, etc.)
-- ============================================================================

-- Warehouse A Gates
INSERT INTO facility_gates (gate_id, facility_id, gate_name, gate_number, gate_type, gate_lat, gate_lng, capacity_per_hour, status)
VALUES 
('GATE-A1', 'FAC-001', 'Gate A1 (Inbound)', 1, 'INBOUND', 18.5204, 73.8567, 2, 'ACTIVE'),
('GATE-A2', 'FAC-001', 'Gate A2 (Inbound)', 2, 'INBOUND', 18.5205, 73.8568, 2, 'ACTIVE'),
('GATE-A3', 'FAC-001', 'Gate A3 (Dock)', 3, 'DUAL', 18.5206, 73.8569, 3, 'ACTIVE'),
('GATE-A4', 'FAC-001', 'Gate A4 (Dock)', 4, 'DUAL', 18.5207, 73.8570, 3, 'ACTIVE'),
('GATE-A5', 'FAC-001', 'Gate A5 (Outbound)', 5, 'OUTBOUND', 18.5208, 73.8571, 2, 'ACTIVE'),
('GATE-A6', 'FAC-001', 'Gate A6 (Outbound)', 6, 'OUTBOUND', 18.5209, 73.8572, 2, 'ACTIVE')
ON CONFLICT DO NOTHING;

-- Warehouse B Gates
INSERT INTO facility_gates (gate_id, facility_id, gate_name, gate_number, gate_type, gate_lat, gate_lng, capacity_per_hour, status)
VALUES 
('GATE-B1', 'FAC-002', 'Gate B1 (Inbound)', 1, 'INBOUND', 18.5220, 73.8585, 2, 'ACTIVE'),
('GATE-B2', 'FAC-002', 'Gate B2 (Inbound)', 2, 'INBOUND', 18.5221, 73.8586, 2, 'ACTIVE'),
('GATE-B3', 'FAC-002', 'Gate B3 (Dock)', 3, 'DUAL', 18.5222, 73.8587, 3, 'ACTIVE'),
('GATE-B4', 'FAC-002', 'Gate B4 (Dock)', 4, 'DUAL', 18.5223, 73.8588, 3, 'ACTIVE'),
('GATE-B5', 'FAC-002', 'Gate B5 (Outbound)', 5, 'OUTBOUND', 18.5224, 73.8589, 2, 'ACTIVE'),
('GATE-B6', 'FAC-002', 'Gate B6 (Outbound)', 6, 'OUTBOUND', 18.5225, 73.8590, 2, 'ACTIVE')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- FACILITY CAPACITY RULES (Layer 2: Warehouse Capacity)
-- ============================================================================

INSERT INTO facility_capacity_rules (rule_id, facility_id, dock_type, max_concurrent_trucks, queue_limit, buffer_time_min)
VALUES 
('RULE-FAC001-DRY', 'FAC-001', 'DRY', 4, 15, 15),
('RULE-FAC001-REF', 'FAC-001', 'REFRIGERATED', 2, 8, 20),
('RULE-FAC002-DRY', 'FAC-002', 'DRY', 4, 15, 15),
('RULE-FAC002-REF', 'FAC-002', 'REFRIGERATED', 2, 8, 20),
('RULE-FAC003-DRY', 'FAC-003', 'DRY', 3, 12, 15),
('RULE-FAC004-DRY', 'FAC-004', 'DRY', 3, 12, 15),
('RULE-FAC005-DRY', 'FAC-005', 'DRY', 2, 10, 15),
('RULE-FAC006-DRY', 'FAC-006', 'DRY', 2, 10, 15)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- RESOURCE POOLS (Layer 3: Warehouse Resources)
-- Initialize resource availability per warehouse
-- ============================================================================

INSERT INTO resource_pool (pool_id, warehouse_id, resource_type, total_count, available_count, assigned_count, in_transit_count)
VALUES 
('POOL-FAC001-DRIVER', 'FAC-001', 'DRIVER', 15, 12, 3, 0),
('POOL-FAC001-TRUCK', 'FAC-001', 'TRUCK', 12, 10, 2, 0),
('POOL-FAC001-STAFF', 'FAC-001', 'STAFF', 25, 18, 7, 0),
('POOL-FAC001-MACHINERY', 'FAC-001', 'MACHINERY', 5, 4, 1, 0),

('POOL-FAC002-DRIVER', 'FAC-002', 'DRIVER', 15, 12, 3, 0),
('POOL-FAC002-TRUCK', 'FAC-002', 'TRUCK', 12, 10, 2, 0),
('POOL-FAC002-STAFF', 'FAC-002', 'STAFF', 25, 18, 7, 0),
('POOL-FAC002-MACHINERY', 'FAC-002', 'MACHINERY', 5, 4, 1, 0),

('POOL-FAC003-DRIVER', 'FAC-003', 'DRIVER', 12, 10, 2, 0),
('POOL-FAC003-TRUCK', 'FAC-003', 'TRUCK', 10, 8, 2, 0),
('POOL-FAC003-STAFF', 'FAC-003', 'STAFF', 20, 15, 5, 0),
('POOL-FAC003-MACHINERY', 'FAC-003', 'MACHINERY', 4, 3, 1, 0),

('POOL-FAC004-DRIVER', 'FAC-004', 'DRIVER', 12, 10, 2, 0),
('POOL-FAC004-TRUCK', 'FAC-004', 'TRUCK', 10, 8, 2, 0),
('POOL-FAC004-STAFF', 'FAC-004', 'STAFF', 20, 15, 5, 0),
('POOL-FAC004-MACHINERY', 'FAC-004', 'MACHINERY', 4, 3, 1, 0),

('POOL-FAC005-DRIVER', 'FAC-005', 'DRIVER', 10, 8, 2, 0),
('POOL-FAC005-TRUCK', 'FAC-005', 'TRUCK', 8, 6, 2, 0),
('POOL-FAC005-STAFF', 'FAC-005', 'STAFF', 15, 12, 3, 0),
('POOL-FAC005-MACHINERY', 'FAC-005', 'MACHINERY', 3, 2, 1, 0),

('POOL-FAC006-DRIVER', 'FAC-006', 'DRIVER', 10, 8, 2, 0),
('POOL-FAC006-TRUCK', 'FAC-006', 'TRUCK', 8, 6, 2, 0),
('POOL-FAC006-STAFF', 'FAC-006', 'STAFF', 15, 12, 3, 0),
('POOL-FAC006-MACHINERY', 'FAC-006', 'MACHINERY', 3, 2, 1, 0)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- HARDCODED DRIVER LOCATIONS & AVAILABILITY (Layer 3)
-- For testing location-based ETA calculation
-- ============================================================================

-- Note: Location will come from GPS button click in driver chat
-- These are just defaults if needed
-- Actual implementation will use hardcoded test locations:
-- Test Location 1 (Between WH-A and WH-B): 18.5212, 73.8576
-- Test Location 2 (Near WH-A): 18.5190, 73.8550
-- Test Location 3 (Near WH-B): 18.5240, 73.8600

-- ============================================================================
-- PRINT SUCCESS MESSAGE
-- ============================================================================

PRINT 'Seed data inserted successfully.';
PRINT '6 Warehouses with hardcoded coordinates (WH-A through WH-F)';
PRINT '36 Gates created (6 per warehouse)';
PRINT '8 Facility capacity rules created';
PRINT '24 Resource pools initialized';
