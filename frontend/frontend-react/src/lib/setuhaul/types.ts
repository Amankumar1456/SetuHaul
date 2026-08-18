export type WarehouseId = "WH-A" | "WH-B" | "WH-C" | "WH-D" | "WH-E" | "WH-F";

export type DriverStatus =
  | "Available"
  | "Assigned"
  | "At Origin"
  | "In Transit"
  | "At Destination"
  | "Inactive"
  | "Non-operational";

export type TruckStatus =
  | "Available"
  | "Assigned"
  | "At Origin"
  | "Loading"
  | "In Transit"
  | "At Destination"
  | "Unloading"
  | "Inactive"
  | "Non-operational";

export type SlotStatus =
  | "Available"
  | "Pending"
  | "Confirmed"
  | "In Progress"
  | "Completed"
  | "Cancelled"
  | "Conflict";

export type ShipmentStatus =
  | "Created"
  | "Scheduled"
  | "Origin Arrival"
  | "Docked"
  | "Loading"
  | "Departed"
  | "In Transit"
  | "Destination Arrival"
  | "Unloading"
  | "Completed"
  | "Cancelled";

export type YardState = "Expected" | "Arrived" | "Docked" | "Departed" | "On Hold";

export type ResourceStatus =
  | "Active"
  | "Inactive"
  | "Non-operational"
  | "Assigned"
  | "Available"
  | "In Transit";

export interface Warehouse {
  id: WarehouseId;
  name: string;
  code: string;
  gates: string[];
  yardCapacity: number;
  opensAt: string; // "07:00"
  closesAt: string; // "16:00"
}

export interface Driver {
  id: string;
  name: string;
  phone: string;
  licenseId: string;
  status: DriverStatus;
  currentWarehouse: WarehouseId | null;
  destinationWarehouse?: WarehouseId | null;
  truckId?: string | null;
  etaMinutes?: number | null;
  lastUpdated: string;
}

export interface Truck {
  id: string;
  plate: string;
  status: TruckStatus;
  currentWarehouse: WarehouseId | null;
  driverId?: string | null;
  shipmentId?: string | null;
  yardState?: YardState;
  gate?: string | null;
  arrivalTime?: string | null;
  lastUpdated: string;
}

export interface StaffPool {
  warehouseId: WarehouseId;
  staffAvailable: number;
  staffAssigned: number;
  machineryAvailable: number;
  machineryAssigned: number;
}

export interface Slot {
  id: string;
  warehouseId: WarehouseId;
  gate: string;
  start: string; // "10:00"
  end: string; // "11:00"
  status: SlotStatus;
  shipmentId?: string | null;
  operation?: "Loading" | "Unloading" | null;
}

export interface Shipment {
  id: string;
  origin: WarehouseId;
  destination: WarehouseId;
  goodsType: string;
  pickupDate: string; // ISO date
  pickupTime: string; // "10:00"
  status: ShipmentStatus;
  driverId?: string | null;
  truckId?: string | null;
  slotId?: string | null;
  eta?: string | null;
  createdAt: string;
  lastUpdated: string;
  history: { status: ShipmentStatus | string; at: string }[];
}

export interface ActivityEvent {
  id: string;
  at: string;
  time: string;
  text: string;
  entity?: { type: "shipment" | "truck" | "driver" | "warehouse"; id: string };
  kind: "info" | "warn" | "success";
}

export interface Escalation {
  id: string;
  title: string;
  detail: string;
  shipmentId?: string;
  warehouseId?: WarehouseId;
  severity: "high" | "medium";
}

export interface OpsState {
  warehouses: Warehouse[];
  drivers: Driver[];
  trucks: Truck[];
  slots: Slot[];
  shipments: Shipment[];
  staff: StaffPool[];
  activity: ActivityEvent[];
  escalations: Escalation[];
  session: { driverId: string | null };
}
