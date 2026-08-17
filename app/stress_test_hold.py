# stress_test_hold.py
import uuid
from concurrent.futures import ThreadPoolExecutor
from langsmith import trace
from app.tools import hold_slot_tool

SLOT_ID = "SLOT-JAI-D1-001"

DRIVERS = [
    ("SHP1003", "DRV003"),
    ("SHP1004", "DRV004"),
    ("SHP1005", "DRV005"),
]

def attempt_hold(shipment_id, driver_id, scenario_id):
    with trace(name="stress-hold-attempt", tags=[f"scenario-{scenario_id}"]) as run:
        result = hold_slot_tool.invoke({
            "slot_id": SLOT_ID,
            "shipment_id": shipment_id,
            "driver_id": driver_id,
        })
        if run:
            run.extra = {"metadata": {"driver_id": driver_id, "shipment_id": shipment_id}}
        return driver_id, result

def main():
    scenario_id = str(uuid.uuid4())[:8]
    print(f"Scenario ID: scenario-{scenario_id}\n")

    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = [ex.submit(attempt_hold, shp, drv, scenario_id) for shp, drv in DRIVERS]
        results = [f.result() for f in futures]

    for driver_id, result in results:
        print(driver_id, "->", result)

    print(f"\nFilter LangSmith by tag: scenario-{scenario_id}")

if __name__ == "__main__":
    main()