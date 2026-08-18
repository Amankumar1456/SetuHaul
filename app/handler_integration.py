"""
Exception Handler Integration Pipeline

Phase 6b: Integration layer connecting intent detection → exception handlers → agent response

Pipeline flow:
1. Intent Detector identifies exception type
2. Handler Context created from driver/shipment data
3. Exception Handler analyzes situation and collects aspects
4. Recommendations fed back to agent for refinement
5. Decisions logged to audit trail
"""

from typing import Dict, Optional, Any
from datetime import datetime, timezone
from app.exception_handlers import (
    get_handler_factory,
    HandlerContext,
    HandlerResponse,
)
from app.intent_detector import get_detector, ExceptionType


class HandlerIntegrationPipeline:
    """
    Orchestrates exception detection → handler analysis → logging pipeline.
    
    Workflow:
    1. Detects exception type from message
    2. Creates handler context from driver/shipment
    3. Runs appropriate exception handler
    4. Logs handler recommendation to decision audit
    5. Returns enhanced response to agent
    """
    
    def __init__(self):
        self.detector = get_detector()
        self.handler_factory = get_handler_factory()
        self.logger_name = "HandlerIntegrationPipeline"
    
    def run_pipeline(
        self,
        driver_id: str,
        message: str,
        conversation_id: str,
        shipment_id: str,
        warehouse_id: str,
        conversation_state: Dict,
        driver_lat: Optional[float] = None,
        driver_lng: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Run full pipeline from detection through handler analysis.
        
        Args:
            driver_id: Driver ID
            message: Driver message text
            conversation_id: Chat thread ID
            shipment_id: Current shipment ID
            warehouse_id: Destination warehouse ID
            conversation_state: Accumulated conversation context
            driver_lat: Driver's current latitude (optional)
            driver_lng: Driver's current longitude (optional)
        
        Returns:
            Pipeline result with exception details, handler recommendations, and next steps
        """
        
        result = {
            "driver_id": driver_id,
            "shipment_id": shipment_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "exception_type": None,
            "exception_confidence": 0.0,
            "handler_name": None,
            "handler_response": None,
            "severity": None,
            "escalation_required": False,
            "escalation_reason": None,
            "recommended_actions": [],
            "follow_up_questions": [],
            "next_steps": [],
            "error": None,
        }
        
        try:
            # STEP 1: Detect exception type
            detection_result = self.detector.detect_exception_type(message, conversation_id)
            
            result["exception_type"] = detection_result.exception_type
            result["exception_confidence"] = detection_result.confidence
            
            if not detection_result.exception_type:
                result["error"] = "No exception type detected"
                return result
            
            # STEP 2: Create handler context
            handler_context = HandlerContext(
                driver_id=driver_id,
                shipment_id=shipment_id,
                conversation_id=conversation_id,
                warehouse_id=warehouse_id,
                exception_type=detection_result.exception_type,
                initial_message=message,
                current_timestamp=datetime.now(timezone.utc).isoformat(),
                driver_location_lat=driver_lat,
                driver_location_lng=driver_lng,
            )
            
            # STEP 3: Get and run appropriate handler
            handler_exception_type = self._map_detector_type_to_handler_type(
                detection_result.exception_type
            )
            
            handler = self.handler_factory.get_handler(handler_exception_type)
            
            if not handler:
                result["error"] = f"No handler for exception type: {handler_exception_type}"
                return result
            
            # Run handler analysis
            handler_response: HandlerResponse = handler.analyze(
                handler_context,
                conversation_state
            )
            
            result["handler_name"] = handler_response.handler_name
            result["handler_response"] = self._serialize_handler_response(handler_response)
            result["severity"] = handler_response.severity
            result["escalation_required"] = handler_response.escalation_required
            result["escalation_reason"] = handler_response.escalation_reason
            result["recommended_actions"] = [a.value for a in handler_response.recommended_actions]
            result["follow_up_questions"] = handler_response.follow_up_questions
            result["next_steps"] = handler_response.next_steps
            
            # STEP 4: Log to decision audit
            self._log_handler_decision(result)
            
        except Exception as e:
            result["error"] = str(e)
            import traceback
            print(f"Pipeline error: {traceback.format_exc()}")
        
        return result
    
    def _map_detector_type_to_handler_type(self, detector_type: str) -> str:
        """Map IntentDetector exception type to Handler exception type."""
        mapping = {
            "MECHANICAL_FAILURE": "MECHANICAL_FAILURE",
            "DRIVER_SICKNESS": "DRIVER_SICKNESS",
            "TRAFFIC_CONGESTION": "TRAFFIC_CONGESTION",
            "POLICE_CHECKPOINT": "POLICE_CHECKPOINT",
            "FACILITY_BLOCKED": "TRAFFIC_CONGESTION",  # Facility blocks treated similar to traffic
            "GENERIC_DELAY": "TRAFFIC_CONGESTION",  # Generic delays use traffic handler
        }
        return mapping.get(detector_type, detector_type)
    
    def _serialize_handler_response(self, response: HandlerResponse) -> Dict:
        """Convert HandlerResponse to JSON-serializable dict."""
        return {
            "handler_name": response.handler_name,
            "exception_type": response.exception_type,
            "severity": response.severity,
            "detected_aspects": response.detected_aspects,
            "recommended_actions": [a.value for a in response.recommended_actions],
            "follow_up_questions": response.follow_up_questions,
            "escalation_required": response.escalation_required,
            "escalation_reason": response.escalation_reason,
            "estimated_resolution_time_min": response.estimated_resolution_time_min,
            "next_steps": response.next_steps,
        }
    
    def _log_handler_decision(self, result: Dict) -> None:
        """Log handler decision to audit trail (would call database function)."""
        try:
            # Import here to avoid circular dependency
            from app.database import log_decision
            
            log_decision(
                driver_id=result["driver_id"],
                shipment_id=result["shipment_id"],
                decision_type="EXCEPTION_HANDLER",
                exception_type=result["exception_type"],
                decision_details=result.get("handler_response", {}),
                severity=result["severity"],
                escalation_flag=result["escalation_required"],
                metadata={
                    "handler_name": result["handler_name"],
                    "escalation_reason": result["escalation_reason"],
                    "recommended_actions": result["recommended_actions"],
                }
            )
        except Exception as e:
            print(f"Warning: Failed to log handler decision: {e}")
    
    def get_agent_enhancement_prompt(self, pipeline_result: Dict) -> str:
        """
        Generate prompt enhancement for agent based on handler analysis.
        
        This prompt is appended to system prompt to make agent aware of
        handler recommendations.
        """
        
        if not pipeline_result.get("handler_response"):
            return ""
        
        handler_resp = pipeline_result["handler_response"]
        
        prompt_parts = [
            "\n--- EXCEPTION HANDLER ANALYSIS ---",
            f"Exception Type: {pipeline_result['exception_type']}",
            f"Handler: {pipeline_result['handler_name']}",
            f"Severity: {pipeline_result['severity']}",
        ]
        
        if handler_resp.get("detected_aspects"):
            prompt_parts.append("\nCollected Information:")
            for key, value in handler_resp["detected_aspects"].items():
                prompt_parts.append(f"  • {key}: {value}")
        
        if handler_resp.get("recommended_actions"):
            prompt_parts.append("\nRecommended Actions:")
            for action in handler_resp["recommended_actions"]:
                prompt_parts.append(f"  • {action}")
        
        if handler_resp.get("follow_up_questions"):
            prompt_parts.append("\nMissing Information (ask driver):")
            for question in handler_resp["follow_up_questions"][:2]:  # First 2 most important
                prompt_parts.append(f"  • {question}")
        
        if handler_resp.get("next_steps"):
            prompt_parts.append("\nNext Steps to Execute:")
            for step in handler_resp["next_steps"][:3]:  # First 3 most critical
                prompt_parts.append(f"  • {step}")
        
        if pipeline_result.get("escalation_required"):
            prompt_parts.append(
                f"\n⚠️ ESCALATION RECOMMENDED: {pipeline_result.get('escalation_reason')}"
            )
        
        return "\n".join(prompt_parts)


# Singleton instance
_pipeline = None

def get_integration_pipeline() -> HandlerIntegrationPipeline:
    """Get singleton handler integration pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = HandlerIntegrationPipeline()
    return _pipeline
