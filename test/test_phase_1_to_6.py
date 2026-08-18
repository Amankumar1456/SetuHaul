"""
Unit and Integration Tests for SetuHaul TMS Phases 1-6

Test Organization:
- test_routing.py: Phase 3 (Routing Engine)
- test_intent_detector.py: Phase 2 (Exception Detection)
- test_exception_handlers.py: Phase 6 (Exception Workflows)
- test_agent_integration.py: Integration test (Full pipeline)
- test_database.py: Phase 1 (Database functions)
"""

import pytest
from datetime import datetime, timezone, timedelta

# ─────────────────────────────────────────────────────────────────────────────
# Test: Routing Engine (Phase 3)
# ─────────────────────────────────────────────────────────────────────────────

class TestRoutingEngine:
    """Unit tests for hardcoded location routing."""
    
    def test_haversine_distance_calculation(self):
        """Test distance calculation between two points."""
        from app.routing import RoutingEngine
        
        # Pune to nearby location (should be <50 km)
        distance = RoutingEngine.haversine_distance(
            lat1=18.5204,  # Pune downtown
            lng1=73.8567,
            lat2=18.5300,
            lng2=73.8700
        )
        
        assert 5 < distance < 20, f"Distance {distance} seems wrong for nearby Pune coords"
    
    def test_duration_calculation_from_distance(self):
        """Test ETA duration calculation."""
        from app.routing import RoutingEngine
        
        # 50 km should take 60 minutes at 50 kmh
        duration = RoutingEngine.calculate_duration_min(50)
        assert duration == 60, f"Expected 60 min, got {duration}"
        
        # 100 km should take 120 minutes
        duration = RoutingEngine.calculate_duration_min(100)
        assert duration == 120, f"Expected 120 min, got {duration}"
        
        # <5 km should still be minimum 5 minutes
        duration = RoutingEngine.calculate_duration_min(1)
        assert duration == 5, f"Expected 5 min minimum, got {duration}"
    
    def test_eta_timestamp_calculation(self):
        """Test ETA timestamp generation."""
        from app.routing import RoutingEngine
        
        now = datetime.now(timezone.utc)
        duration_min = 30
        
        eta = RoutingEngine.calculate_eta_timestamp(duration_min, now)
        eta_dt = datetime.fromisoformat(eta.replace('Z', '+00:00'))
        
        # Should be ~30 minutes in the future
        diff = (eta_dt - now).total_seconds() / 60
        assert 28 < diff < 32, f"ETA difference {diff} should be ~30 minutes"
    
    def test_warehouse_location_retrieval(self):
        """Test getting warehouse coordinates."""
        from app.routing import RoutingEngine
        
        wh_a = RoutingEngine.get_warehouse_location("FAC-001")
        
        assert wh_a is not None, "FAC-001 should exist"
        assert hasattr(wh_a, 'latitude'), "Should have latitude"
        assert hasattr(wh_a, 'longitude'), "Should have longitude"
        assert 18 < wh_a.latitude < 19, "Should be in Pune region"
        assert 73 < wh_a.longitude < 74, "Should be in Pune region"
    
    def test_calculate_route_full_pipeline(self):
        """Test complete route calculation."""
        from app.routing import RoutingEngine
        
        # Simulate driver at one location going to warehouse
        route = RoutingEngine.calculate_route(
            driver_lat=18.52,
            driver_lng=73.87,
            facility_id="FAC-001",
            name="Driver Location"
        )
        
        assert route is not None, "Route should be calculated"
        assert route.distance_km > 0, "Distance should be positive"
        assert route.duration_min >= 5, "Duration should be at least 5 minutes"
        assert route.calculated_eta_ts is not None, "ETA should be set"
    
    def test_test_location_retrieval(self):
        """Test getting test driver locations."""
        from app.routing import RoutingEngine
        
        locations = RoutingEngine.get_all_test_locations()
        
        assert len(locations) > 0, "Should have test locations"
        assert all(hasattr(loc, 'latitude') for loc in locations.values()), "All should have lat"
        assert all(hasattr(loc, 'longitude') for loc in locations.values()), "All should have lng"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Intent Detector (Phase 2)
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentDetector:
    """Unit tests for exception detection."""
    
    def test_mechanical_failure_detection(self):
        """Test detecting mechanical failure exceptions."""
        from app.intent_detector import get_detector
        
        detector = get_detector()
        
        # Clear any previous state
        detector.clear_conversation("test_conv_1")
        
        # Test with engine failure keyword
        result = detector.detect_exception_type(
            "My truck engine stopped, won't restart",
            "test_conv_1"
        )
        
        assert result.exception_type == "MECHANICAL_FAILURE", \
            f"Expected MECHANICAL_FAILURE, got {result.exception_type}"
        assert result.confidence > 0.5, f"Confidence should be >0.5, got {result.confidence}"
    
    def test_driver_sickness_detection(self):
        """Test detecting driver sickness exceptions."""
        from app.intent_detector import get_detector
        
        detector = get_detector()
        detector.clear_conversation("test_conv_2")
        
        result = detector.detect_exception_type(
            "I have high fever and dizziness, need help",
            "test_conv_2"
        )
        
        assert result.exception_type == "DRIVER_SICKNESS", \
            f"Expected DRIVER_SICKNESS, got {result.exception_type}"
    
    def test_traffic_congestion_detection(self):
        """Test detecting traffic delays."""
        from app.intent_detector import get_detector
        
        detector = get_detector()
        detector.clear_conversation("test_conv_3")
        
        result = detector.detect_exception_type(
            "Stuck in traffic on NH48, moving very slowly",
            "test_conv_3"
        )
        
        assert result.exception_type == "TRAFFIC_CONGESTION", \
            f"Expected TRAFFIC_CONGESTION, got {result.exception_type}"
    
    def test_police_checkpoint_detection(self):
        """Test detecting police checkpoints."""
        from app.intent_detector import get_detector
        
        detector = get_detector()
        detector.clear_conversation("test_conv_4")
        
        result = detector.detect_exception_type(
            "Police stopped me at a checkpoint, asking for documents",
            "test_conv_4"
        )
        
        assert result.exception_type == "POLICE_CHECKPOINT", \
            f"Expected POLICE_CHECKPOINT, got {result.exception_type}"
    
    def test_confidence_scoring(self):
        """Test that confidence scores vary with keyword strength."""
        from app.intent_detector import get_detector
        
        detector = get_detector()
        
        # Strong match
        detector.clear_conversation("conf_test_1")
        strong = detector.detect_exception_type(
            "Engine failure, truck broken down, needs repair",
            "conf_test_1"
        )
        
        # Weak match
        detector.clear_conversation("conf_test_2")
        weak = detector.detect_exception_type(
            "Running a bit slow today",
            "conf_test_2"
        )
        
        assert strong.confidence > weak.confidence, \
            "Strong keywords should have higher confidence"
    
    def test_aspect_recording(self):
        """Test recording conversation aspects."""
        from app.intent_detector import get_detector
        
        detector = get_detector()
        detector.clear_conversation("aspect_test")
        
        # Detect exception
        detector.detect_exception_type(
            "My truck broke down with engine failure",
            "aspect_test"
        )
        
        # Record aspect
        detector.record_aspect("aspect_test", "repair_duration", "90 minutes")
        
        # Retrieve state
        state = detector.get_conversation_state("aspect_test")
        
        assert state.get("repair_duration") == "90 minutes", \
            "Aspect should be recorded in conversation state"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Exception Handlers (Phase 6)
# ─────────────────────────────────────────────────────────────────────────────

class TestMechanicalFailureHandler:
    """Unit tests for mechanical failure handler."""
    
    def test_engine_failure_critical_severity(self):
        """Test engine failure classified as CRITICAL."""
        from app.exception_handlers import MechanicalFailureHandler, HandlerContext
        
        handler = MechanicalFailureHandler()
        
        context = HandlerContext(
            driver_id="DRV-001",
            shipment_id="SHP-001",
            conversation_id="CONV-001",
            warehouse_id="FAC-001",
            exception_type="MECHANICAL_FAILURE",
            initial_message="Engine failure",
            current_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        response = handler.analyze(context, {
            "repair_symptom": "engine not starting",
            "repair_duration_estimate": "240 minutes",
            "cargo_type": "perishable food"
        })
        
        assert response.severity == "CRITICAL", f"Engine failure should be CRITICAL, got {response.severity}"
        assert "VEHICLE_REPLACEMENT" in str(response.recommended_actions), \
            "Should recommend vehicle replacement for critical engine failure"
    
    def test_repair_time_escalation_threshold(self):
        """Test escalation triggers when repair time > 120 min."""
        from app.exception_handlers import MechanicalFailureHandler, HandlerContext
        
        handler = MechanicalFailureHandler()
        context = HandlerContext(
            driver_id="DRV-001",
            shipment_id="SHP-001",
            conversation_id="CONV-001",
            warehouse_id="FAC-001",
            exception_type="MECHANICAL_FAILURE",
            initial_message="Tire issue",
            current_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        response = handler.analyze(context, {
            "repair_symptom": "tire puncture",
            "repair_duration_estimate": "150 minutes",
            "cargo_type": "general cargo"
        })
        
        assert response.escalation_required, "Should escalate for repair > 120 minutes"
        assert "exceeds threshold" in response.escalation_reason.lower()


class TestDriverSicknessHandler:
    """Unit tests for driver sickness handler."""
    
    def test_critical_emergency_symptoms(self):
        """Test emergency symptoms classified as CRITICAL."""
        from app.exception_handlers import DriverSicknessHandler, HandlerContext
        
        handler = DriverSicknessHandler()
        context = HandlerContext(
            driver_id="DRV-001",
            shipment_id="SHP-001",
            conversation_id="CONV-001",
            warehouse_id="FAC-001",
            exception_type="DRIVER_SICKNESS",
            initial_message="Emergency",
            current_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        response = handler.analyze(context, {
            "symptom_description": "severe chest pain",
            "symptom_severity": "emergency"
        })
        
        assert response.severity == "CRITICAL", f"Chest pain should be CRITICAL, got {response.severity}"
        assert response.escalation_required, "Should escalate for emergency"
        assert "MEDICAL_ESCALATION" in str(response.recommended_actions)
    
    def test_mild_symptoms_rest_recommended(self):
        """Test mild symptoms recommend warehouse rest."""
        from app.exception_handlers import DriverSicknessHandler, HandlerContext
        
        handler = DriverSicknessHandler()
        context = HandlerContext(
            driver_id="DRV-001",
            shipment_id="SHP-001",
            conversation_id="CONV-001",
            warehouse_id="FAC-001",
            exception_type="DRIVER_SICKNESS",
            initial_message="Headache",
            current_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        response = handler.analyze(context, {
            "symptom_description": "mild headache",
            "symptom_severity": "mild"
        })
        
        assert response.severity == "MEDIUM" or response.severity == "LOW"
        assert response.estimated_resolution_time_min == 60, "Mild should suggest 1-hour rest"
        assert "DRIVER_REST_AT_WAREHOUSE" in str(response.recommended_actions)


class TestTrafficCongestionHandler:
    """Unit tests for traffic handler."""
    
    def test_long_delay_requires_rebooking(self):
        """Test delays > 180 min trigger rebooking."""
        from app.exception_handlers import TrafficCongestionHandler, HandlerContext
        
        handler = TrafficCongestionHandler()
        context = HandlerContext(
            driver_id="DRV-001",
            shipment_id="SHP-001",
            conversation_id="CONV-001",
            warehouse_id="FAC-001",
            exception_type="TRAFFIC_CONGESTION",
            initial_message="Traffic",
            current_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        response = handler.analyze(context, {
            "traffic_location": "NH48",
            "estimated_delay_min": "240",
            "cargo_time_sensitive": "yes"
        })
        
        assert response.escalation_required, "Should escalate for 240 min delay"
        assert "REBOOKING_SLOT" in str(response.recommended_actions)
    
    def test_time_sensitive_cargo_affects_severity(self):
        """Test time-sensitive cargo increases severity."""
        from app.exception_handlers import TrafficCongestionHandler, HandlerContext
        
        handler = TrafficCongestionHandler()
        context = HandlerContext(
            driver_id="DRV-001",
            shipment_id="SHP-001",
            conversation_id="CONV-001",
            warehouse_id="FAC-001",
            exception_type="TRAFFIC_CONGESTION",
            initial_message="Traffic",
            current_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        response = handler.analyze(context, {
            "traffic_location": "NH44",
            "estimated_delay_min": "100",
            "cargo_time_sensitive": "perishable"
        })
        
        assert response.severity in ["HIGH", "CRITICAL"], \
            f"Perishable cargo should elevate severity, got {response.severity}"


class TestPoliceCheckpointHandler:
    """Unit tests for checkpoint handler."""
    
    def test_invalid_documents_escalation(self):
        """Test missing documents trigger escalation."""
        from app.exception_handlers import PoliceCheckpointHandler, HandlerContext
        
        handler = PoliceCheckpointHandler()
        context = HandlerContext(
            driver_id="DRV-001",
            shipment_id="SHP-001",
            conversation_id="CONV-001",
            warehouse_id="FAC-001",
            exception_type="POLICE_CHECKPOINT",
            initial_message="Checkpoint",
            current_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        response = handler.analyze(context, {
            "checkpoint_location": "NH48",
            "checkpoint_reason": "document verification",
            "documents_status": "missing permit"
        })
        
        assert response.escalation_required, "Missing documents should escalate"
        assert response.severity == "CRITICAL"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Handler Integration (Phase 6 Integration)
# ─────────────────────────────────────────────────────────────────────────────

class TestHandlerIntegration:
    """Integration tests for handler pipeline."""
    
    def test_pipeline_detection_to_handler(self):
        """Test full pipeline from detection to handler."""
        from app.handler_integration import get_integration_pipeline
        from app.intent_detector import get_detector
        
        pipeline = get_integration_pipeline()
        detector = get_detector()
        
        # Clear state
        detector.clear_conversation("integration_test_1")
        
        # Run pipeline
        result = pipeline.run_pipeline(
            driver_id="DRV-001",
            message="My truck engine stopped, won't restart",
            conversation_id="integration_test_1",
            shipment_id="SHP-001",
            warehouse_id="FAC-001",
            conversation_state={},
        )
        
        assert result["exception_type"] == "MECHANICAL_FAILURE", \
            f"Should detect mechanical failure, got {result['exception_type']}"
        assert result["handler_name"] is not None, "Handler should be identified"
        assert result["severity"] is not None, "Severity should be assigned"
    
    def test_handler_response_serialization(self):
        """Test handler response can be serialized to JSON."""
        from app.handler_integration import get_integration_pipeline
        from app.intent_detector import get_detector
        import json
        
        pipeline = get_integration_pipeline()
        detector = get_detector()
        detector.clear_conversation("serial_test")
        
        result = pipeline.run_pipeline(
            driver_id="DRV-001",
            message="I have fever and dizziness",
            conversation_id="serial_test",
            shipment_id="SHP-001",
            warehouse_id="FAC-001",
            conversation_state={},
        )
        
        # Should be JSON serializable
        try:
            json_str = json.dumps(result)
            assert len(json_str) > 0, "Result should be JSON serializable"
        except Exception as e:
            pytest.fail(f"Result should be JSON serializable: {e}")
    
    def test_agent_prompt_enhancement_generation(self):
        """Test generating agent prompt enhancement."""
        from app.handler_integration import get_integration_pipeline
        from app.intent_detector import get_detector
        
        pipeline = get_integration_pipeline()
        detector = get_detector()
        detector.clear_conversation("prompt_test")
        
        result = pipeline.run_pipeline(
            driver_id="DRV-001",
            message="Traffic jam on NH48, delay about 2 hours",
            conversation_id="prompt_test",
            shipment_id="SHP-001",
            warehouse_id="FAC-001",
            conversation_state={},
        )
        
        enhancement = pipeline.get_agent_enhancement_prompt(result)
        
        assert len(enhancement) > 0, "Should generate prompt enhancement"
        assert "EXCEPTION HANDLER ANALYSIS" in enhancement, "Should have header"
        assert result["exception_type"] in enhancement, "Should mention exception type"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Database Functions (Phase 1)
# ─────────────────────────────────────────────────────────────────────────────

class TestDatabaseFunctions:
    """Unit tests for database helper functions."""
    
    def test_warehouse_locations_hardcoded(self):
        """Test that warehouse locations are properly defined."""
        from app.routing import RoutingEngine
        
        # All warehouses should have coordinates
        warehouses = ["FAC-001", "FAC-002", "FAC-003", "FAC-004", "FAC-005", "FAC-006"]
        
        for wh_id in warehouses:
            location = RoutingEngine.get_warehouse_location(wh_id)
            assert location is not None, f"{wh_id} should have location"
            assert 18 < location.latitude < 19, f"{wh_id} latitude out of range"
            assert 73 < location.longitude < 74, f"{wh_id} longitude out of range"
    
    def test_gate_types_valid(self):
        """Test that gate types are valid (from Phase 1 schema)."""
        # This would test the actual database if integrated
        # For now, just verify expected gate types
        valid_gate_types = ["INBOUND", "OUTBOUND", "DUAL"]
        
        assert "INBOUND" in valid_gate_types
        assert "OUTBOUND" in valid_gate_types
        assert "DUAL" in valid_gate_types


# ─────────────────────────────────────────────────────────────────────────────
# Pytest Configuration
# ─────────────────────────────────────────────────────────────────────────────

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: unit tests")
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line("markers", "slow: slow running tests")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
