import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { initialState, warehouseName } from "./seed";
import type {
  ActivityEvent,
  Driver,
  OpsState,
  Shipment,
  ShipmentStatus,
  Slot,
  Truck,
  WarehouseId,
} from "./types";

export const nowTime = () =>
  new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

const addMinutes = (mins: number) =>
  new Date(Date.now() + mins * 60000).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });

interface Ctx {
  state: OpsState;
  createShipment: (input: {
    origin: WarehouseId;
    destination: WarehouseId;
    goodsType: string;
    pickupDate: string;
    pickupTime: string;
  }) => Shipment;
  markArrived: (truckId: string, warehouseId: WarehouseId) => void;
  markDocked: (truckId: string, gate: string) => void;
  markDeparted: (truckId: string) => void;
  changeSlot: (shipmentId: string, slotId: string) => void;
  registerDriver: (input: {
    name: string;
    phone: string;
    licenseId: string;
    warehouse: WarehouseId;
  }) => Driver;
  loginDriver: (driverId: string) => void;
  logoutDriver: () => void;
  updateDriverLocation: (driverId: string, warehouseId: WarehouseId) => void;
}

const OpsContext = createContext<Ctx | null>(null);

let seq = 1030;

export function OpsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<OpsState>(() =>
    JSON.parse(JSON.stringify(initialState)) as OpsState,
  );

  const log = useCallback(
    (s: OpsState, text: string, kind: ActivityEvent["kind"] = "info", entity?: ActivityEvent["entity"]) => {
      const ev: ActivityEvent = {
        id: `EV-${Math.random().toString(36).slice(2, 8)}`,
        at: new Date().toISOString(),
        time: nowTime(),
        text,
        kind,
        ...(entity ? { entity } : {}),
      };
      s.activity = [ev, ...s.activity].slice(0, 60);
    },
    [],
  );

  const mutate = useCallback((fn: (draft: OpsState) => void) => {
    setState((prev) => {
      const draft = JSON.parse(JSON.stringify(prev)) as OpsState;
      fn(draft);
      return draft;
    });
  }, []);

  const touchShipment = (sh: Shipment, status: ShipmentStatus) => {
    sh.status = status;
    sh.lastUpdated = new Date().toISOString();
    sh.history.push({ status, at: new Date().toISOString() });
  };

  const createShipment: Ctx["createShipment"] = useCallback(
    (input) => {
      seq += 1;
      const id = `SHP-2026-${String(seq).padStart(6, "0")}`;
      const shipment: Shipment = {
        id,
        origin: input.origin,
        destination: input.destination,
        goodsType: input.goodsType,
        pickupDate: input.pickupDate,
        pickupTime: input.pickupTime,
        status: "Scheduled",
        driverId: null,
        truckId: null,
        slotId: null,
        eta: null,
        createdAt: new Date().toISOString(),
        lastUpdated: new Date().toISOString(),
        history: [
          { status: "Created", at: new Date().toISOString() },
          { status: "Scheduled", at: new Date().toISOString() },
        ],
      };
      mutate((d) => {
        // auto-assign first available slot at origin matching pickup hour
        const hour = input.pickupTime.slice(0, 2);
        const slot =
          d.slots.find(
            (s) => s.warehouseId === input.origin && s.start.startsWith(hour) && s.status === "Available",
          ) ?? d.slots.find((s) => s.warehouseId === input.origin && s.status === "Available");
        if (slot) {
          slot.status = "Confirmed";
          slot.shipmentId = id;
          slot.operation = "Loading";
          shipment.slotId = slot.id;
        }
        const driver = d.drivers.find(
          (dr) => dr.currentWarehouse === input.origin && dr.status === "Available",
        );
        if (driver) {
          driver.status = "Assigned";
          shipment.driverId = driver.id;
          const truck = d.trucks.find(
            (t) => t.currentWarehouse === input.origin && t.status === "Available",
          );
          if (truck) {
            truck.status = "Assigned";
            truck.shipmentId = id;
            truck.driverId = driver.id;
            truck.yardState = "Expected";
            shipment.truckId = truck.id;
            driver.truckId = truck.id;
          }
        }
        d.shipments = [shipment, ...d.shipments];
        log(d, `${id} created · ${warehouseName(input.origin)} → ${warehouseName(input.destination)}`, "success", {
          type: "shipment",
          id,
        });
      });
      return shipment;
    },
    [log, mutate],
  );

  const markArrived: Ctx["markArrived"] = useCallback(
    (truckId, warehouseId) => {
      mutate((d) => {
        const truck = d.trucks.find((t) => t.id === truckId);
        if (!truck) return;
        const wh = d.warehouses.find((w) => w.id === warehouseId);
        const hhmm = nowTime();
        const afterHours = wh ? hhmm >= wh.closesAt || hhmm < wh.opensAt : false;
        truck.yardState = afterHours ? "On Hold" : "Arrived";
        truck.currentWarehouse = warehouseId;
        truck.arrivalTime = new Date().toISOString();
        truck.status = "At Origin";
        truck.lastUpdated = new Date().toISOString();
        const sh = d.shipments.find((s) => s.id === truck.shipmentId);
        if (sh) touchShipment(sh, sh.origin === warehouseId ? "Origin Arrival" : "Destination Arrival");
        const dr = d.drivers.find((x) => x.id === truck.driverId);
        if (dr) {
          dr.currentWarehouse = warehouseId;
          dr.status = "At Origin";
          dr.lastUpdated = new Date().toISOString();
        }
        log(
          d,
          `${truckId} ${afterHours ? "on hold (after hours) at" : "arrived at"} ${warehouseName(warehouseId)}`,
          afterHours ? "warn" : "info",
          { type: "truck", id: truckId },
        );
      });
    },
    [log, mutate],
  );

  const markDocked: Ctx["markDocked"] = useCallback(
    (truckId, gate) => {
      mutate((d) => {
        const truck = d.trucks.find((t) => t.id === truckId);
        if (!truck) return;
        truck.yardState = "Docked";
        truck.gate = gate;
        truck.status = "Loading";
        truck.lastUpdated = new Date().toISOString();
        const sh = d.shipments.find((s) => s.id === truck.shipmentId);
        if (sh) {
          touchShipment(sh, sh.origin === truck.currentWarehouse ? "Loading" : "Unloading");
          const slot = d.slots.find((s) => s.id === sh.slotId);
          if (slot) slot.status = "In Progress";
        }
        log(d, `${truckId} docked at gate ${gate}`, "info", { type: "truck", id: truckId });
      });
    },
    [log, mutate],
  );

  const markDeparted: Ctx["markDeparted"] = useCallback(
    (truckId) => {
      mutate((d) => {
        const truck = d.trucks.find((t) => t.id === truckId);
        if (!truck) return;
        const sh = d.shipments.find((s) => s.id === truck.shipmentId);
        const from = truck.currentWarehouse;
        truck.yardState = "Departed";
        truck.gate = null;
        truck.lastUpdated = new Date().toISOString();
        const dr = d.drivers.find((x) => x.id === truck.driverId);
        if (sh && from === sh.destination) {
          touchShipment(sh, "Completed");
          truck.status = "Available";
          truck.currentWarehouse = sh.destination;
          truck.shipmentId = null;
          const slot = d.slots.find((s) => s.id === sh.slotId);
          if (slot) slot.status = "Completed";
          if (dr) {
            dr.status = "Available";
            dr.currentWarehouse = sh.destination;
            dr.destinationWarehouse = null;
            dr.etaMinutes = null;
          }
          log(d, `${sh.id} completed at ${warehouseName(sh.destination)}`, "success", {
            type: "shipment",
            id: sh.id,
          });
        } else {
          truck.status = "In Transit";
          truck.currentWarehouse = null;
          if (sh) {
            touchShipment(sh, "In Transit");
            sh.eta = addMinutes(90);
          }
          if (dr) {
            dr.status = "In Transit";
            dr.currentWarehouse = null;
            dr.destinationWarehouse = sh?.destination ?? null;
            dr.etaMinutes = 90;
            dr.lastUpdated = new Date().toISOString();
          }
          log(d, `${truckId} departed ${warehouseName(from)} · now in transit`, "info", {
            type: "truck",
            id: truckId,
          });
        }
      });
    },
    [log, mutate],
  );

  const changeSlot: Ctx["changeSlot"] = useCallback(
    (shipmentId, slotId) => {
      mutate((d) => {
        const sh = d.shipments.find((s) => s.id === shipmentId);
        if (!sh) return;
        const old = d.slots.find((s) => s.id === sh.slotId);
        if (old) {
          old.status = "Available";
          old.shipmentId = null;
          old.operation = null;
        }
        const next = d.slots.find((s) => s.id === slotId);
        if (next) {
          next.status = "Confirmed";
          next.shipmentId = shipmentId;
          next.operation = "Loading";
          sh.slotId = next.id;
          sh.pickupTime = next.start;
          sh.lastUpdated = new Date().toISOString();
          sh.history.push({ status: `Slot changed to ${next.start}`, at: new Date().toISOString() });
          log(d, `${shipmentId} slot changed to ${next.start} (gate ${next.gate})`, "warn", {
            type: "shipment",
            id: shipmentId,
          });
        }
      });
    },
    [log, mutate],
  );

  const registerDriver: Ctx["registerDriver"] = useCallback(
    (input) => {
      const id = `DRV-${String(Math.floor(Math.random() * 900) + 100)}`;
      const driver: Driver = {
        id,
        name: input.name,
        phone: input.phone,
        licenseId: input.licenseId,
        status: "Available",
        currentWarehouse: input.warehouse,
        destinationWarehouse: null,
        truckId: null,
        etaMinutes: null,
        lastUpdated: new Date().toISOString(),
      };
      mutate((d) => {
        d.drivers = [driver, ...d.drivers];
        d.session.driverId = id;
        log(d, `Driver ${input.name} registered at ${warehouseName(input.warehouse)}`, "success", {
          type: "driver",
          id,
        });
      });
      return driver;
    },
    [log, mutate],
  );

  const loginDriver = useCallback(
    (driverId: string) => mutate((d) => void (d.session.driverId = driverId)),
    [mutate],
  );
  const logoutDriver = useCallback(() => mutate((d) => void (d.session.driverId = null)), [mutate]);

  const updateDriverLocation: Ctx["updateDriverLocation"] = useCallback(
    (driverId, warehouseId) => {
      mutate((d) => {
        const dr = d.drivers.find((x) => x.id === driverId);
        if (!dr) return;
        dr.currentWarehouse = warehouseId;
        dr.status = "Available";
        dr.destinationWarehouse = null;
        dr.etaMinutes = null;
        dr.lastUpdated = new Date().toISOString();
        const truck = d.trucks.find((t) => t.id === dr.truckId);
        if (truck) {
          truck.currentWarehouse = warehouseId;
          truck.status = "Available";
        }
        log(d, `Driver ${dr.name} location updated · ${warehouseName(warehouseId)}`, "info", {
          type: "driver",
          id: driverId,
        });
      });
    },
    [log, mutate],
  );

  const value = useMemo<Ctx>(
    () => ({
      state,
      createShipment,
      markArrived,
      markDocked,
      markDeparted,
      changeSlot,
      registerDriver,
      loginDriver,
      logoutDriver,
      updateDriverLocation,
    }),
    [
      state,
      createShipment,
      markArrived,
      markDocked,
      markDeparted,
      changeSlot,
      registerDriver,
      loginDriver,
      logoutDriver,
      updateDriverLocation,
    ],
  );

  return <OpsContext.Provider value={value}>{children}</OpsContext.Provider>;
}

export function useOps() {
  const ctx = useContext(OpsContext);
  if (!ctx) throw new Error("useOps must be used inside OpsProvider");
  return ctx;
}

export { warehouseName };

/* ---------- derived selectors ---------- */

export function warehouseStats(state: OpsState, id: WarehouseId) {
  const wh = state.warehouses.find((w) => w.id === id)!;
  const drivers = state.drivers.filter((d) => d.currentWarehouse === id);
  const inTransitDrivers = state.drivers.filter(
    (d) => d.status === "In Transit" && d.destinationWarehouse === id,
  );
  const trucksHere = state.trucks.filter((t) => t.currentWarehouse === id);
  const inYard = trucksHere.filter((t) => t.yardState === "Arrived" || t.yardState === "Docked");
  const slots = state.slots.filter((s) => s.warehouseId === id);
  const upcoming = state.trucks.filter(
    (t) => t.yardState === "Expected" && t.currentWarehouse === id,
  );
  const staff = state.staff.find((s) => s.warehouseId === id)!;
  return {
    wh,
    staff,
    driversAvailable: drivers.filter((d) => d.status === "Available").length,
    driversTransit: inTransitDrivers.length,
    trucksAvailable: trucksHere.filter((t) => t.status === "Available").length,
    trucksInYard: inYard.length,
    trucksTransit: state.trucks.filter((t) => t.status === "In Transit").length,
    yardOccupancy: inYard.length,
    yardCapacity: wh.yardCapacity,
    slotsAvailable: slots.filter((s) => s.status === "Available").length,
    slotsBooked: slots.filter((s) => s.status === "Confirmed" || s.status === "Pending").length,
    slotsOccupied: slots.filter((s) => s.status === "In Progress").length,
    upcomingArrivals: upcoming.length,
    escalations: state.escalations.filter((e) => e.warehouseId === id),
  };
}

export const CUSTOMER_STAGES = [
  "Created",
  "Scheduled",
  "Picked Up",
  "In Transit",
  "Arrived",
  "Unloading",
  "Completed",
] as const;

export function customerStageIndex(status: ShipmentStatus) {
  const map: Record<ShipmentStatus, number> = {
    Created: 0,
    Scheduled: 1,
    "Origin Arrival": 1,
    Docked: 2,
    Loading: 2,
    Departed: 3,
    "In Transit": 3,
    "Destination Arrival": 4,
    Unloading: 5,
    Completed: 6,
    Cancelled: 0,
  };
  return map[status];
}

export type { Slot, Truck, Driver, Shipment };
