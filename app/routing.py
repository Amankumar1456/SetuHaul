"""
Routing and ETA Calculation Module
Uses HARDCODED warehouse locations and driver test locations for ETA calculation.
Replaces Geoapify with simple distance-based estimation.

Hardcoded Locations:
- Warehouse A (WH-A): 18.5204, 73.8567
- Warehouse B (WH-B): 18.5220, 73.8585
- Test Location 1 (Between A & B): 18.5212, 73.8576
- Test Location 2 (Near A): 18.5190, 73.8550
- Test Location 3 (Near B): 18.5240, 73.8600
"""

from dataclasses import dataclass
from typing import Tuple, Optional
from datetime import datetime, timedelta, timezone
import math


@dataclass
class Location:
    """A geographic location."""
    latitude: float
    longitude: float
    name: str = None
    
    def __repr__(self):
        return f"{self.name}({self.latitude}, {self.longitude})" if self.name else f"({self.latitude}, {self.longitude})"


@dataclass
class RouteInfo:
    """Information about a calculated route."""
    start_location: Location
    end_location: Location
    distance_km: float
    duration_min: int
    calculated_eta_ts: str  # ISO format timestamp
    confidence: str  # HIGH, MEDIUM, LOW


# ============================================================================
# HARDCODED WAREHOUSE LOCATIONS
# ============================================================================

WAREHOUSE_LOCATIONS = {
    "FAC-001": Location(latitude=18.5204, longitude=73.8567, name="Warehouse A"),
    "FAC-002": Location(latitude=18.5220, longitude=73.8585, name="Warehouse B"),
    "FAC-003": Location(latitude=18.5190, longitude=73.8550, name="Warehouse C"),
    "FAC-004": Location(latitude=18.5240, longitude=73.8600, name="Warehouse D"),
    "FAC-005": Location(latitude=18.5170, longitude=73.8530, name="Warehouse E"),
    "FAC-006": Location(latitude=18.5260, longitude=73.8620, name="Warehouse F"),
}

# ============================================================================
# TEST DRIVER LOCATIONS
# Used when driver clicks "Send Location" button in chat
# ============================================================================

TEST_DRIVER_LOCATIONS = {
    "test_location_1": Location(latitude=18.5212, longitude=73.8576, name="Test: Between WH-A and WH-B"),
    "test_location_2": Location(latitude=18.5190, longitude=73.8550, name="Test: Near WH-A"),
    "test_location_3": Location(latitude=18.5240, longitude=73.8600, name="Test: Near WH-B"),
    "test_location_4": Location(latitude=18.5185, longitude=73.8545, name="Test: Far from WH-A"),
}

# Speed assumption: 50 km/h average (accounting for city traffic in India)
AVERAGE_SPEED_KMH = 50


class RoutingEngine:
    """
    Calculates routes and ETAs using hardcoded locations.
    Simple distance-based calculation without external API calls.
    """
    
    @staticmethod
    def haversine_distance(
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float
    ) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.
        Returns distance in kilometers.
        
        This is a basic approximation suitable for testing.
        In production, use proper routing API.
        """
        R = 6371  # Earth's radius in kilometers
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        # Haversine formula
        a = (
            math.sin(delta_lat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    @staticmethod
    def calculate_duration_min(distance_km: float, speed_kmh: float = AVERAGE_SPEED_KMH) -> int:
        """
        Calculate duration in minutes based on distance and speed.
        Simple formula: duration = distance / speed * 60
        """
        hours = distance_km / speed_kmh
        minutes = int(hours * 60)
        return max(5, minutes)  # Minimum 5 minutes
    
    @staticmethod
    def calculate_eta_timestamp(
        duration_min: int,
        start_time: Optional[datetime] = None
    ) -> str:
        """Calculate ETA timestamp (ISO format)."""
        if start_time is None:
            start_time = datetime.now(timezone.utc)
        
        eta_time = start_time + timedelta(minutes=duration_min)
        return eta_time.isoformat()
    
    @classmethod
    def calculate_route(
        cls,
        start_lat: float,
        start_lng: float,
        end_facility_id: str,
        start_location_name: str = "Driver Location"
    ) -> Optional[RouteInfo]:
        """
        Calculate route from driver location to destination warehouse.
        
        Args:
            start_lat: Driver latitude
            start_lng: Driver longitude
            end_facility_id: Destination warehouse ID (FAC-001, etc.)
            start_location_name: Name for the start location
        
        Returns:
            RouteInfo with distance, duration, ETA
        """
        # Get destination warehouse
        end_location = WAREHOUSE_LOCATIONS.get(end_facility_id)
        if not end_location:
            return None
        
        # Create start location
        start_location = Location(
            latitude=start_lat,
            longitude=start_lng,
            name=start_location_name
        )
        
        # Calculate distance using Haversine
        distance_km = cls.haversine_distance(
            start_lat, start_lng,
            end_location.latitude, end_location.longitude
        )
        
        # Calculate duration
        duration_min = cls.calculate_duration_min(distance_km)
        
        # Calculate ETA timestamp
        eta_ts = cls.calculate_eta_timestamp(duration_min)
        
        return RouteInfo(
            start_location=start_location,
            end_location=end_location,
            distance_km=round(distance_km, 2),
            duration_min=duration_min,
            calculated_eta_ts=eta_ts,
            confidence="MEDIUM"  # Hardcoded estimates have medium confidence
        )
    
    @classmethod
    def calculate_eta_for_driver(
        cls,
        driver_lat: float,
        driver_lng: float,
        destination_facility_id: str
    ) -> dict:
        """
        Calculate ETA for a driver to a facility.
        Returns dict suitable for saving to database.
        """
        route = cls.calculate_route(
            start_lat=driver_lat,
            start_lng=driver_lng,
            end_facility_id=destination_facility_id,
            start_location_name="Driver Current Location"
        )
        
        if not route:
            return {
                "error": f"Facility {destination_facility_id} not found",
                "confidence": "LOW"
            }
        
        return {
            "distance_km": route.distance_km,
            "duration_min": route.duration_min,
            "calculated_eta_ts": route.calculated_eta_ts,
            "calculation_method": "HARDCODED",
            "confidence": "MEDIUM",
            "start_location": f"({route.start_location.latitude}, {route.start_location.longitude})",
            "end_location": f"{route.end_location.name} ({route.end_location.latitude}, {route.end_location.longitude})",
            "note": "ETA calculated using hardcoded warehouse locations and simple distance estimation"
        }
    
    @classmethod
    def get_test_location(cls, location_key: str) -> Optional[Location]:
        """
        Get a test driver location by key.
        Used for testing without real GPS.
        """
        return TEST_DRIVER_LOCATIONS.get(location_key)
    
    @classmethod
    def get_all_test_locations(cls) -> dict:
        """Get all available test locations."""
        return TEST_DRIVER_LOCATIONS
    
    @classmethod
    def get_warehouse_location(cls, facility_id: str) -> Optional[Location]:
        """Get warehouse location by facility ID."""
        return WAREHOUSE_LOCATIONS.get(facility_id)
    
    @classmethod
    def get_all_warehouse_locations(cls) -> dict:
        """Get all warehouse locations."""
        return WAREHOUSE_LOCATIONS


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def calculate_eta_simple(
    driver_lat: float,
    driver_lng: float,
    destination_facility_id: str
) -> dict:
    """
    Simple wrapper for ETA calculation.
    Used by tools.py and agent.py
    """
    return RoutingEngine.calculate_eta_for_driver(
        driver_lat=driver_lat,
        driver_lng=driver_lng,
        destination_facility_id=destination_facility_id
    )


def get_test_locations_list() -> dict:
    """Get list of test locations for UI."""
    locations = {}
    for key, loc in TEST_DRIVER_LOCATIONS.items():
        locations[key] = {
            "name": loc.name,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "description": f"{loc.name} ({loc.latitude}, {loc.longitude})"
        }
    return locations


def get_warehouse_info(facility_id: str) -> dict:
    """Get warehouse info for ETA display."""
    warehouse = WAREHOUSE_LOCATIONS.get(facility_id)
    if not warehouse:
        return None
    
    return {
        "facility_id": facility_id,
        "name": warehouse.name,
        "latitude": warehouse.latitude,
        "longitude": warehouse.longitude,
        "coordinates": f"({warehouse.latitude}, {warehouse.longitude})"
    }
