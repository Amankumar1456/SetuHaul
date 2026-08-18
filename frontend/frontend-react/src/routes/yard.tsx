import { createFileRoute } from "@tanstack/react-router";
import { ArrowRightLeft, Clock, DoorOpen, LogOut, Timer, Truck as TruckIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { InternalTopBar, Panel, StatusPill } from "@/components/setuhaul/ui";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useOps, warehouseName } from "@/lib/setuhaul/store";
import type { Truck, WarehouseId } from "@/lib/setuhaul/types";

export const Route = createFileRoute("/yard")({
  head: () => ({
    meta: [
      { title: "Yard Engine — SetuHaul" },
      {
        name: "description",
        content:
          "Yard operator console: track trucks inside the yard, dock them at gates and record departures across SetuHaul warehouses.",
      },
      { property: "og:title", content: "Yard Engine — SetuHaul" },
      {
        property: "og:description",
        content: "Manage truck arrival, docking and departure for each SetuHaul warehouse yard.",
      },
    ],
  }),
  component: YardEngine,
});

const fmt = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "—";

const durationSince = (iso?: string | null) => {
  if (!iso) return "—";
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
};

function YardEngine() {
  const { state, markArrived, markDocked, markDeparted } = useOps();
  const [warehouseId, setWarehouseId] = useState<WarehouseId>("WH-A");
  const wh = state.warehouses.find((w) => w.id === warehouseId)!;

  const inYard = state.trucks.filter(
    (t) =>
      t.currentWarehouse === warehouseId &&
      (t.yardState === "Arrived" || t.yardState === "Docked" || t.yardState === "On Hold"),
  );
  const expected = state.trucks.filter(
    (t) => t.currentWarehouse === warehouseId && t.yardState === "Expected",
  );

  return (
    <div className="min-h-screen bg-background">
      <InternalTopBar subtitle="Yard Engine" />
      <div className="mx-auto max-w-[1600px] px-4 py-6">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight">{wh.name} · Yard Operations</h1>
            <p className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
              <StatusPill status="Operational" />
              <span className="font-mono">
                {wh.opensAt} — {wh.closesAt}
              </span>
              <span>
                Yard {inYard.length}/{wh.yardCapacity} occupied · {wh.gates.length} gates
              </span>
            </p>
          </div>
          <div className="w-56">
            <Select value={warehouseId} onValueChange={(v) => setWarehouseId(v as WarehouseId)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {state.warehouses.map((w) => (
                  <SelectItem key={w.id} value={w.id}>
                    {w.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <Panel title={`Current trucks inside yard (${inYard.length})`} icon={TruckIcon}>
            <div className="space-y-3">
              {inYard.length === 0 ? (
                <Empty text="No trucks currently inside the yard." />
              ) : (
                inYard.map((t) => (
                  <YardCard
                    key={t.id}
                    truck={t}
                    gates={wh.gates}
                    onDock={(gate) => {
                      markDocked(t.id, gate);
                      toast.success(`${t.id} docked at ${gate}`);
                    }}
                    onDepart={() => {
                      markDeparted(t.id);
                      toast.success(`${t.id} departed ${wh.name}`);
                    }}
                  />
                ))
              )}
            </div>
          </Panel>

          <Panel title={`Upcoming arrivals (${expected.length})`} icon={Clock}>
            <div className="space-y-3">
              {expected.length === 0 ? (
                <Empty text="No expected arrivals in this window." />
              ) : (
                expected.map((t) => {
                  const shipment = state.shipments.find((s) => s.id === t.shipmentId);
                  const driver = state.drivers.find((d) => d.id === t.driverId);
                  const slot = state.slots.find((s) => s.id === shipment?.slotId);
                  return (
                    <div key={t.id} className="rounded-md border border-border bg-surface p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-mono text-sm font-semibold">{t.id}</div>
                          <div className="font-mono text-xs text-muted-foreground">
                            {shipment?.id ?? "Unassigned"}
                          </div>
                        </div>
                        <StatusPill status="Expected" />
                      </div>
                      <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
                        <Field label="Driver" value={driver?.name ?? "—"} />
                        <Field label="Gate" value={slot?.gate ?? "TBD"} />
                        <Field
                          label="Slot"
                          value={slot ? `${slot.start}–${slot.end}` : "Unscheduled"}
                        />
                      </div>
                      <Button
                        size="sm"
                        className="mt-3 w-full"
                        onClick={() => {
                          markArrived(t.id, warehouseId);
                          toast.success(`${t.id} marked arrived`);
                        }}
                      >
                        Mark Arrived
                      </Button>
                    </div>
                  );
                })
              )}
            </div>
          </Panel>
        </div>

        <Panel className="mt-5" title="Yard state machine" icon={ArrowRightLeft}>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {["Expected", "Arrived", "Docked", "Departed"].map((s, i) => (
              <span key={s} className="flex items-center gap-2">
                <StatusPill status={s} />
                {i < 3 ? <span className="text-muted-foreground">→</span> : null}
              </span>
            ))}
            <span className="ml-4 text-muted-foreground">
              Arrivals outside {wh.opensAt}–{wh.closesAt} are placed{" "}
              <span className="font-semibold text-foreground">On Hold</span> until the next
              operational window.
            </span>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function YardCard({
  truck,
  gates,
  onDock,
  onDepart,
}: {
  truck: Truck;
  gates: string[];
  onDock: (gate: string) => void;
  onDepart: () => void;
}) {
  const { state } = useOps();
  const [gate, setGate] = useState(gates[0] ?? "");
  const shipment = state.shipments.find((s) => s.id === truck.shipmentId);
  const driver = state.drivers.find((d) => d.id === truck.driverId);

  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-sm font-semibold">{truck.id}</div>
          <div className="font-mono text-xs text-muted-foreground">
            {shipment?.id ?? "No shipment"}
          </div>
        </div>
        <StatusPill status={truck.yardState ?? "Arrived"} />
      </div>
      <div className="mt-3 grid grid-cols-4 gap-3 text-xs">
        <Field label="Driver" value={driver?.name ?? "—"} />
        <Field label="Arrived" value={fmt(truck.arrivalTime)} />
        <Field label="Gate / Dock" value={truck.gate ?? "—"} />
        <Field label="Dwell" value={durationSince(truck.arrivalTime)} icon={Timer} />
      </div>
      <div className="mt-3 flex gap-2">
        {truck.yardState === "Docked" ? (
          <Button size="sm" variant="secondary" className="flex-1" onClick={onDepart}>
            <LogOut className="size-3.5" /> Mark Departed
          </Button>
        ) : (
          <>
            <Select value={gate} onValueChange={setGate}>
              <SelectTrigger className="h-8 w-28 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {gates.map((g) => (
                  <SelectItem key={g} value={g}>
                    {g}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button size="sm" className="flex-1" onClick={() => onDock(gate)}>
              <DoorOpen className="size-3.5" /> Mark Docked
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon?: typeof Timer;
}) {
  return (
    <div>
      <div className="label-xs">{label}</div>
      <div className="mt-0.5 flex items-center gap-1 font-mono text-xs text-foreground">
        {Icon ? <Icon className="size-3 text-muted-foreground" /> : null}
        {value}
      </div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="rounded-md border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
      {text}
    </div>
  );
}
