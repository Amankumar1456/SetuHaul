import { Link, createFileRoute } from "@tanstack/react-router";
import { Activity, AlertTriangle, ArrowUpRight, Boxes, Radio } from "lucide-react";

import { Panel, StatusPill } from "@/components/setuhaul/ui";
import { Button } from "@/components/ui/button";
import { useOps, warehouseStats } from "@/lib/setuhaul/store";

export const Route = createFileRoute("/dashboard/")({
  head: () => ({
    meta: [
      { title: "Operations Dashboard — SetuHaul" },
      {
        name: "description",
        content:
          "Global control tower across six warehouses: drivers, trucks, yard occupancy, slot capacity, escalations and live activity.",
      },
      { property: "og:title", content: "Operations Dashboard — SetuHaul" },
      {
        property: "og:description",
        content: "Monitor warehouses, resources, slots and shipments across the SetuHaul network.",
      },
    ],
  }),
  component: GlobalDashboard,
});

function GlobalDashboard() {
  const { state } = useOps();

  const totals = {
    shipments: state.shipments.filter((s) => s.status !== "Completed").length,
    inTransit: state.trucks.filter((t) => t.status === "In Transit").length,
    escalations: state.escalations.length,
    driversAvailable: state.drivers.filter((d) => d.status === "Available").length,
  };

  return (
    <main className="mx-auto max-w-[1600px] px-4 py-6">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Global Operations</h1>
          <p className="text-xs text-muted-foreground">
            Six warehouses · one operational state · live event stream
          </p>
        </div>
        <div className="grid grid-cols-4 gap-6">
          {[
            ["Active shipments", totals.shipments],
            ["Trucks in transit", totals.inTransit],
            ["Drivers available", totals.driversAvailable],
            ["Escalations", totals.escalations],
          ].map(([label, value]) => (
            <div key={label as string} className="text-right">
              <div className="font-mono text-2xl leading-none">{value as number}</div>
              <div className="label-xs mt-1">{label as string}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
          {state.warehouses.map((w) => {
            const s = warehouseStats(state, w.id);
            return (
              <article key={w.id} className="panel flex flex-col">
                <div className="panel-head">
                  <span className="text-sm font-semibold">{w.name}</span>
                  <StatusPill status="Operational" />
                </div>
                <div className="grid flex-1 grid-cols-2 gap-x-4 gap-y-3 p-4 text-xs">
                  <Stat
                    label="Drivers"
                    main={`${s.driversAvailable} avail`}
                    sub={`${s.driversTransit} inbound`}
                  />
                  <Stat
                    label="Trucks"
                    main={`${s.trucksAvailable} avail`}
                    sub={`${s.trucksInYard} in yard`}
                  />
                  <Stat
                    label="Yard"
                    main={`${s.yardOccupancy} / ${s.yardCapacity}`}
                    sub="occupied"
                  />
                  <Stat
                    label="Slots"
                    main={`${s.slotsAvailable} avail`}
                    sub={`${s.slotsBooked} booked · ${s.slotsOccupied} live`}
                  />
                  <Stat label="Upcoming arrivals" main={String(s.upcomingArrivals)} sub="next window" />
                  <Stat
                    label="Escalations"
                    main={String(s.escalations.length)}
                    sub={s.escalations.length ? "action needed" : "clear"}
                    warn={s.escalations.length > 0}
                  />
                </div>
                <div className="border-t border-border p-3">
                  <Button asChild size="sm" variant="secondary" className="w-full">
                    <Link to="/dashboard/$warehouseId" params={{ warehouseId: w.id }}>
                      Open Warehouse <ArrowUpRight className="size-3.5" />
                    </Link>
                  </Button>
                </div>
              </article>
            );
          })}
        </div>

        <div className="space-y-4">
          <Panel title="Active escalations" icon={AlertTriangle}>
            <div className="space-y-2">
              {state.escalations.map((e) => (
                <div
                  key={e.id}
                  className="rounded-md border border-destructive/25 bg-destructive/5 p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-destructive">⚠ {e.title}</span>
                    <span className="label-xs">{e.severity}</span>
                  </div>
                  <div className="mt-1 font-mono text-[11px]">{e.shipmentId}</div>
                  <p className="mt-1 text-xs text-muted-foreground">{e.detail}</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Activity feed" icon={Activity}>
            <ol className="space-y-2.5">
              {state.activity.slice(0, 14).map((a) => (
                <li key={a.id} className="flex gap-3 text-xs">
                  <span className="font-mono text-muted-foreground">{a.time}</span>
                  <span
                    className={
                      a.kind === "warn"
                        ? "text-destructive"
                        : a.kind === "success"
                          ? "text-success"
                          : "text-foreground"
                    }
                  >
                    {a.text}
                  </span>
                </li>
              ))}
            </ol>
          </Panel>

          <Panel title="Network shipments" icon={Boxes}>
            <ul className="space-y-2">
              {state.shipments.slice(0, 8).map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-mono">{s.id}</span>
                  <StatusPill status={s.status} />
                </li>
              ))}
            </ul>
          </Panel>

          <div className="flex items-center gap-2 px-1 text-[11px] text-muted-foreground">
            <Radio className="size-3.5 text-success" /> Live state — events propagate to yard,
            driver and customer views instantly.
          </div>
        </div>
      </div>
    </main>
  );
}

function Stat({
  label,
  main,
  sub,
  warn,
}: {
  label: string;
  main: string;
  sub: string;
  warn?: boolean;
}) {
  return (
    <div>
      <div className="label-xs">{label}</div>
      <div
        className={
          warn
            ? "mt-0.5 font-mono text-sm font-semibold text-destructive"
            : "mt-0.5 font-mono text-sm font-semibold text-foreground"
        }
      >
        {main}
      </div>
      <div className="text-[10px] text-muted-foreground">{sub}</div>
    </div>
  );
}
