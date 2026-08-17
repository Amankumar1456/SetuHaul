from app.database import get_driver
from app.redis_client import place_hold, get_hold, release_hold

# Test Supabase
print("Testing Supabase...")
try:
    driver = get_driver("DRV001")
    if driver:
        print(f"✓ Supabase works — found driver: {driver['driver_name']}")
    else:
        print("✗ Supabase connected but driver not found — check your seed data")
except Exception as e:
    print(f"✗ Supabase failed — {e}")

# Test Redis
print("\nTesting Redis...")
try:
    result = place_hold("SLOT-TEST-001", "SHP1006", "DRV006")
    if result["success"]:
        print(f"✓ Redis works — hold placed successfully")
        release_hold("SLOT-TEST-001", "SHP1006")
        print("✓ Hold released cleanly")
    else:
        print(f"✗ Redis hold failed — {result}")
except Exception as e:
    print(f"✗ Redis failed — {e}")

print("\nDone.")