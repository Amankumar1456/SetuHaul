import { Link, createFileRoute } from "@tanstack/react-router";
import {
  AlertTriangle,
  ChevronLeft,
  Clock,
  Cog,
  HardHat,
  Truck as TruckIcon,
  Users,
  Warehouse as WarehouseIcon,
} from "lucide-react";

import { Panel, StatusPill } from "@/components/setuhaul/ui";
import { HOURS } from "@/lib/setuhaul/seed";
import { useOps, warehouseStats } from "@/lib/setuhaul/store";
import type { WarehouseId } from "@/lib/setuhaul/types";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/dashboard/$warehouseId")({
  head: () => ({
    meta: [
      { title: "Warehouse Operations — SetuHaul" },
      {
        name: "description",
        content:
          "Warehouse operational view: resource summary, gate slot timeline, yard status, upcoming arrivals and escalations.",
      },
      { property: "og:title", content: "Warehouse Operations — SetuHaul" },
      {
        property: "og:description",
        content: "Resources, slot timeline, yard status and escalations for a SetuHaul warehouse.",
      },
    ],
  }),
  component: WarehouseView,
});

const SLOT_TONE: Record<string, string> = {
  Available: "bg-muted/50 border-border",
  Pending: "bg-warning/15 border-warning/40 text-foreground",
  Confirmed: "bg-info/15 border-info/40 text-foreground",
  "In Progress": "bg-info/70 border-info text-white",
  Completed: "bg-success/25 border-success/50",
  Cancelled: "bg-muted border-border line-through",
  Conflict: "bg-destructive/20 border-destructive/50",
};

function WarehouseView() {
  const { warehouseId } = Route.useParams();
  const { state } = useOps();
  const wh = state.warehouses.find((w) => w.id === (warehouseId as WarehouseId));

  if (!wh) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-16 text-center">
        <p className="text-sm text-muted-foreground">Unknown warehouse.</p>
        <Link to="/dashboard" className="mt-3 inline-block text-sm underline">
          Back to dashboard
        </Link>
      </main>
    );
  }

  const s = warehouseStats(state, wh.id);
  const slots = state.slots.filter((x) => x.warehouseId === wh.id);
  const inYard = state.trucks.filter(
    (t) => t.currentWarehouse === wh.id && (t.yardState === "Arrived" || t.yardState === "Docked"),
  );
  const expected = state.trucks.filter(
    (t) => t.currentWarehouse === wh.id && t.yardState === "Expected",
  );

  return (
    <main className="mx-auto max-w-[1600px] px-4 py-6">
      <Link
        to="/dashboard"
        className="mb-3 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-3.5" /> All warehouses
      </Link>
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <h1 className="text-xl font-bold tracking-tight">{wh.name}</h1>
        <StatusPill status="Operational" />
        <span className="font-mono text-xs text-muted-foreground">
          {wh.opensAt} — {wh.closesAt}
        </span>
        <span className="text-xs text-muted-foreground">{wh.gates.length} gates</span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <ResourceCard
          icon={Users}
          title="Drivers"
          rows={[
            ["Available", s.driversAvailable],
            ["In Transit", s.driversTransit],
          ]}
        />
        <ResourceCard
          icon={TruckIcon}
          title="Trucks"
          rows={[
            ["Available", s.trucksAvailable],
            ["In Yard", s.trucksInYard],
            ["In Transit", s.trucksTransit],
          ]}
        />
        <ResourceCard
          icon={HardHat}
          title="Staff"
          rows={[
            ["Available", s.staff.staffAvailable],
            ["Assigned", s.staff.staffAssigned],
          ]}
        />
        <ResourceCard
          icon={Cog}
          title="Machinery"
          rows={[
            ["Available", s.staff.machineryAvailable],
            ["Assigned", s.staff.machineryAssigned],
          ]}
        />
      </div>

      <Panel className="mt-5" title="Slot timeline · gates × hours" icon={Clock}>
        <div className="overflow-x-auto">
          <div className="min-w-[860px]">
            <div className="flex border-b border-border pb-1 pl-14">
              {HOURS.slice(0, 9).map((h) => (
                <div key={h} className="label-xs flex-1">
                  {h}:00
                </div>
              ))}
            </div>
            <div className="mt-2 space-y-1.5">
              {wh.gates.map((gate) => (
                <div key={gate} className="flex items-center">
                  <div className="w-14 font-mono text-xs font-semibold">{gate}</div>
                  <div className="flex flex-1 gap-1">
                    {HOURS.slice(0, 9).map((h) => {
                      const slot = slots.find((x) => x.gate === gate && x.start === `${h}:00`);
                      const status = slot?.status ?? "Available";
                      return (
                        <div
                          key={h}
                          title={`${gate} ${h}:00 · ${status}${slot?.shipmentId ? ` · ${slot.shipmentId}` : ""}`}
                          className={cn(
                            "h-9 flex-1 overflow-hidden rounded-sm border px-1.5 py-1 text-[9px] leading-tight",
                            SLOT_TONE[status],
                          )}
                        >
                          {slot?.shipmentId ? (
                            <>
                              <div className="truncate font-mono">
                                {slot.shipmentId.replace("SHP-2026-", "")}
                              </div>
                              <div className="truncate opacity-80">{slot.operation}</div>
                            </>
                          ) : status !== "Available" ? (
                            <span className="opacity-70">{status}</span>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 flex flex-wrap gap-3 border-t border-border pt-3">
              {Object.keys(SLOT_TONE).map((k) => (
                <span key={k} className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  <span className={cn("size-3 rounded-sm border", SLOT_TONE[k])} />
                  {k}
                </span>
              ))}
            </div>
          </div>
        </div>
      </Panel>

      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <Panel title={`Yard status · ${s.yardOccupancy}/${s.yardCapacity}`} icon={WarehouseIcon}>
          <div className="space-y-2">
            {inYard.length === 0 ? (
              <p className="text-xs text-muted-foreground">Yard empty.</p>
            ) : (
              inYard.map((t) => (
                <div key={t.id} className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-mono">
                    {t.id} {t.gate ? `· ${t.gate}` : ""}
                  </span>
                  <StatusPill status={t.yardState ?? "Arrived"} />
                </div>
              ))
            )}
          </div>
        </Panel>

        <Panel title={`Upcoming arrivals · ${expected.length}`} icon={Clock}>
          <div className="space-y-2">
            {expected.length === 0 ? (
              <p className="text-xs text-muted-foreground">No expected arrivals.</p>
            ) : (
              expected.map((t) => {
                const sh = state.shipments.find((x) => x.id === t.shipmentId);
                return (
                  <div key={t.id} className="flex items-center justify-between gap-2 text-xs">
                    <span className="font-mono">
                      {t.id} · {sh?.id.replace("SHP-2026-", "") ?? "—"}
                    </span>
                    <span className="font-mono text-muted-foreground">
                      {sh?.pickupTime ?? "—"}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </Panel>

        <Panel title="Escalations" icon={AlertTriangle}>
          <div className="space-y-2">
            {s.escalations.length === 0 ? (
              <p className="text-xs text-muted-foreground">No active escalations.</p>
            ) : (
              s.escalations.map((e) => (
                <div key={e.id} className="rounded-md border border-destructive/25 bg-destructive/5 p-2.5">
                  <div className="text-xs font-semibold text-destructive">⚠ {e.title}</div>
                  <div className="font-mono text-[11px]">{e.shipmentId}</div>
                  <p className="text-xs text-muted-foreground">{e.detail}</p>
                </div>
              ))
            )}
          </div>
        </Panel>
      </div>
    </main>
  );
}

function ResourceCard({
  icon: Icon,
  title,
  rows,
}: {
  icon: typeof Users;
  title: string;
  rows: [string, number][];
}) {
  return (
    <article className="panel p-4">
      <div className="flex items-center gap-2">
        <Icon className="size-3.5 text-muted-foreground" />
        <h3 className="label-xs !text-foreground">{title}</h3>
      </div>
      <div className="mt-3 space-y-1.5">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between">
            <span className="text-xs text-muted-foreground">{label}</span>
            <span className="font-mono text-lg leading-none">{value}</span>
          </div>
        ))}
      </div>
    </article>
  );
}
