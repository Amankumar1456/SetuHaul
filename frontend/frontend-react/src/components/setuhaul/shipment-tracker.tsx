import { ArrowDown, Clock, Truck } from "lucide-react";

import { StatusPill } from "@/components/setuhaul/ui";
import { CUSTOMER_STAGES, customerStageIndex, useOps, warehouseName } from "@/lib/setuhaul/store";
import type { Shipment } from "@/lib/setuhaul/types";
import { cn } from "@/lib/utils";

const fmt = (iso?: string | null) =>
  iso
    ? new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
    : "—";

export function ShipmentTracker({ shipment }: { shipment: Shipment }) {
  const { state } = useOps();
  const idx = customerStageIndex(shipment.status);
  const driver = state.drivers.find((d) => d.id === shipment.driverId);
  const truck = state.trucks.find((t) => t.id === shipment.truckId);

  return (
    <section className="panel">
      <div className="panel-head">
        <span className="font-mono text-sm font-semibold">{shipment.id}</span>
        <StatusPill status={shipment.status} />
      </div>

      <div className="grid gap-8 p-6 md:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <div className="flex items-center gap-4">
            <div>
              <div className="label-xs">Origin</div>
              <div className="text-lg font-semibold">{warehouseName(shipment.origin)}</div>
            </div>
            <ArrowDown className="size-4 -rotate-90 text-muted-foreground" />
            <div>
              <div className="label-xs">Destination</div>
              <div className="text-lg font-semibold">{warehouseName(shipment.destination)}</div>
            </div>
          </div>

          <ol className="mt-8 space-y-0">
            {CUSTOMER_STAGES.map((stage, i) => {
              const done = i < idx;
              const active = i === idx;
              return (
                <li key={stage} className="relative flex gap-4 pb-6 last:pb-0">
                  {i < CUSTOMER_STAGES.length - 1 ? (
                    <span
                      className={cn(
                        "absolute left-[7px] top-4 h-full w-px",
                        done ? "bg-success" : "bg-border",
                      )}
                    />
                  ) : null}
                  <span
                    className={cn(
                      "relative z-10 mt-0.5 grid size-[15px] place-items-center rounded-full border-2",
                      done && "border-success bg-success",
                      active && "border-info bg-info ring-4 ring-info/15",
                      !done && !active && "border-border bg-surface",
                    )}
                  />
                  <div className="-mt-0.5">
                    <div
                      className={cn(
                        "text-sm font-medium",
                        active ? "text-foreground" : done ? "text-foreground/80" : "text-muted-foreground",
                      )}
                    >
                      {stage}
                    </div>
                    {active ? (
                      <div className="text-xs text-muted-foreground">
                        Updated {fmt(shipment.lastUpdated)}
                      </div>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>

        <aside className="space-y-4 rounded-md border border-border bg-muted/40 p-4">
          <div>
            <div className="label-xs">Current status</div>
            <div className="mt-1 text-lg font-semibold uppercase tracking-tight">
              {shipment.status}
            </div>
          </div>
          <Row label="Pickup" value={`${shipment.pickupDate} · ${shipment.pickupTime}`} />
          <Row label="Estimated arrival" value={shipment.eta ?? "Being scheduled"} />
          <Row label="Last updated" value={fmt(shipment.lastUpdated)} icon={Clock} />
          {driver ? <Row label="Driver" value={driver.name} /> : null}
          {truck ? <Row label="Truck" value={truck.id} icon={Truck} /> : null}
          <div className="border-t border-border pt-3 text-[11px] text-muted-foreground">
            Goods type · {shipment.goodsType}
          </div>
        </aside>
      </div>
    </section>
  );
}

function Row({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon?: typeof Clock;
}) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="label-xs">{label}</span>
      <span className="flex items-center gap-1.5 font-mono text-xs text-foreground">
        {Icon ? <Icon className="size-3.5 text-muted-foreground" /> : null}
        {value}
      </span>
    </div>
  );
}
