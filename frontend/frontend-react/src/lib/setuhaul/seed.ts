import type {
  ActivityEvent,
  Driver,
  Escalation,
  OpsState,
  Shipment,
  Slot,
  StaffPool,
  Truck,
  Warehouse,
  WarehouseId,
} from "./types";

export const HOURS = ["07", "08", "09", "10", "11", "12", "13", "14", "15", "16"];

const gateCounts: Record<WarehouseId, number> = {
  "WH-A": 6,
  "WH-B": 5,
  "WH-C": 5,
  "WH-D": 6,
  "WH-E": 5,
  "WH-F": 5,
};

export const warehouses: Warehouse[] = (
  [
    ["WH-A", "Warehouse A", "A", 20],
    ["WH-B", "Warehouse B", "B", 16],
    ["WH-C", "Warehouse C", "C", 18],
    ["WH-D", "Warehouse D", "D", 22],
    ["WH-E", "Warehouse E", "E", 14],
    ["WH-F", "Warehouse F", "F", 16],
  ] as const
).map(([id, name, code, cap]) => ({
  id: id as WarehouseId,
  name,
  code,
  yardCapacity: cap,
  opensAt: "07:00",
  closesAt: "16:00",
  gates: Array.from({ length: gateCounts[id as WarehouseId] }, (_, i) => `${code}${i + 1}`),
}));

export const warehouseName = (id: WarehouseId | null | undefined) =>
  warehouses.find((w) => w.id === id)?.name ?? "—";

const today = () => new Date().toISOString().slice(0, 10);
const stamp = (t: string) => `${today()}T${t}:00`;

const NAMES = [
  "Raj Malhotra",
  "Amit Verma",
  "Suresh Nair",
  "Karan Singh",
  "Iqbal Khan",
  "Vikram Rao",
  "Nitin Joshi",
  "Deepak Sharma",
  "Manoj Pillai",
  "Farhan Ali",
  "Sanjay Kulkarni",
  "Pramod Gowda",
  "Rohit Bansal",
  "Zaid Ahmed",
  "Arun Kadam",
  "Harish Menon",
  "Sunil Yadav",
  "Bhaskar Reddy",
  "Ganesh Iyer",
  "Tarun Bhatt",
  "Ashok Patil",
  "Naveen Das",
  "Imran Sheikh",
  "Ravi Chauhan",
];

// 4 drivers per warehouse: 3 available, 1 assigned/in transit.
export const drivers: Driver[] = NAMES.map((name, i) => {
  const wh = warehouses[i % 6]!.id;
  const id = `DRV-${String(i + 1).padStart(3, "0")}`;
  const inTransit = i === 0;
  const assigned = i >= 18;
  return {
    id,
    name,
    phone: `+91 98${(10000000 + i * 13711).toString().slice(0, 8)}`,
    licenseId: `DL-${2019 + (i % 5)}-${4000 + i * 7}`,
    status: inTransit ? "In Transit" : assigned ? "Assigned" : "Available",
    currentWarehouse: inTransit ? null : wh,
    destinationWarehouse: inTransit ? "WH-D" : null,
    truckId: i < 12 ? `T-10${40 + i}` : null,
    etaMinutes: inTransit ? 63 : null,
    lastUpdated: stamp("11:42"),
  } satisfies Driver;
});

// 24 trucks: mix of available, in-yard (arrived/docked) and expected arrivals.
export const trucks: Truck[] = Array.from({ length: 24 }, (_, i) => {
  const home = warehouses[i % 6]!;
  const bucket = Math.floor(i / 6); // 0 available, 1 arrived, 2 docked, 3 expected
  const inTransit = i === 0;
  return {
    id: `T-10${40 + i}`,
    plate: `MH-04-${String(1000 + i * 37).slice(0, 4)}`,
    status: inTransit
      ? "In Transit"
      : bucket === 0
        ? "Available"
        : bucket === 2
          ? "Loading"
          : "Assigned",
    currentWarehouse: inTransit ? null : home.id,
    driverId: i < 12 ? drivers[i]!.id : null,
    shipmentId: null,
    yardState: inTransit
      ? "Departed"
      : bucket === 1
        ? "Arrived"
        : bucket === 2
          ? "Docked"
          : "Expected",
    gate: bucket === 2 ? (home.gates[1] ?? null) : null,
    arrivalTime: bucket === 1 || bucket === 2 ? stamp("09:14") : null,
    lastUpdated: stamp("11:30"),
  } satisfies Truck;
});



export const staff: StaffPool[] = warehouses.map((w, i) => ({
  warehouseId: w.id,
  staffAvailable: 14 + i * 2,
  staffAssigned: 4 + i,
  machineryAvailable: 4 + (i % 3),
  machineryAssigned: 1 + (i % 2),
}));

function buildSlots(): Slot[] {
  const out: Slot[] = [];
  for (const w of warehouses) {
    for (const gate of w.gates) {
      for (let h = 7; h < 16; h++) {
        out.push({
          id: `${gate}-${h}`,
          warehouseId: w.id,
          gate,
          start: `${String(h).padStart(2, "0")}:00`,
          end: `${String(h + 1).padStart(2, "0")}:00`,
          status: "Available",
          shipmentId: null,
          operation: null,
        });
      }
    }
  }
  return out;
}

export const slots: Slot[] = buildSlots();

const seedShipments: Array<[string, WarehouseId, WarehouseId, string, string, Shipment["status"], string, string, string]> = [
  ["SHP-2026-001024", "WH-A", "WH-D", "General Cargo", "10:00", "In Transit", "DRV-001", "T-1040", "A2-9"],
  ["SHP-2026-001025", "WH-A", "WH-B", "Perishable", "08:00", "Loading", "DRV-002", "T-1041", "A1-8"],
  ["SHP-2026-001028", "WH-A", "WH-C", "Fragile", "12:00", "Scheduled", "DRV-001", "T-1045", "A4-12"],
  ["SHP-2026-001029", "WH-B", "WH-E", "Liquid", "13:00", "Scheduled", "DRV-001", "T-1046", "B3-13"],
  ["SHP-2026-001031", "WH-C", "WH-F", "Hazardous", "09:00", "Docked", "DRV-004", "T-1043", "C2-9"],
  ["SHP-2026-001020", "WH-D", "WH-A", "General Cargo", "07:00", "Completed", "DRV-001", "T-1044", "D1-7"],
];

export const shipments: Shipment[] = seedShipments.map(
  ([id, origin, destination, goodsType, pickupTime, status, driverId, truckId, slotId]) => ({
    id,
    origin,
    destination,
    goodsType,
    pickupDate: today(),
    pickupTime,
    status,
    driverId,
    truckId,
    slotId,
    eta: status === "In Transit" ? "12:45" : null,
    createdAt: stamp("07:05"),
    lastUpdated: stamp("11:42"),
    history: [
      { status: "Created", at: stamp("07:05") },
      { status: "Scheduled", at: stamp("07:20") },
    ],
  }),
);

// Reserve seeded slots
for (const s of shipments) {
  const slot = slots.find((x) => x.id === s.slotId);
  if (slot) {
    slot.shipmentId = s.id;
    slot.operation = s.origin === slot.warehouseId ? "Loading" : "Unloading";
    slot.status =
      s.status === "Completed" ? "Completed" : s.status === "Scheduled" ? "Confirmed" : "In Progress";
  }
  const truck = trucks.find((t) => t.id === s.truckId);
  if (truck && s.status !== "Completed") truck.shipmentId = s.id;
}

slots.find((s) => s.id === "A3-10")!.status = "Pending";
slots.find((s) => s.id === "B2-11")!.status = "Conflict";

export const activity: ActivityEvent[] = [
  ["10:42", "T-1042 arrived at Warehouse A", "info"],
  ["10:39", "SHP-2026-001028 slot changed to 12:00", "info"],
  ["10:35", "Driver Raj Malhotra accepted SHP-2026-001028", "success"],
  ["10:31", "T-1038 departed Warehouse C", "info"],
  ["10:25", "Escalation raised for SHP-2026-001024", "warn"],
].map(([time, text, kind], i) => ({
  id: `EV-${i}`,
  at: stamp(time as string),
  time: time as string,
  text: text as string,
  kind: kind as ActivityEvent["kind"],
}));

export const escalations: Escalation[] = [
  {
    id: "ESC-1",
    title: "Late Arrival",
    detail: "ETA exceeded by 22 minutes",
    shipmentId: "SHP-2026-001024",
    warehouseId: "WH-A",
    severity: "high",
  },
  {
    id: "ESC-2",
    title: "Slot Conflict",
    detail: "Destination slot unavailable",
    shipmentId: "SHP-2026-001031",
    warehouseId: "WH-B",
    severity: "medium",
  },
  {
    id: "ESC-3",
    title: "Driver Unavailable",
    detail: "Driver assigned to SHP-2026-001029 is unavailable",
    shipmentId: "SHP-2026-001029",
    warehouseId: "WH-C",
    severity: "medium",
  },
];

export const initialState: OpsState = {
  warehouses,
  drivers,
  trucks,
  slots,
  shipments,
  staff,
  activity,
  escalations,
  session: { driverId: null },
};
