import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowRight,
  Check,
  ClipboardCopy,
  MapPin,
  PackagePlus,
  Search,
  Truck as TruckIcon,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Brand, StatusPill } from "@/components/setuhaul/ui";
import { ShipmentTracker } from "@/components/setuhaul/shipment-tracker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useOps, warehouseName } from "@/lib/setuhaul/store";
import type { Shipment, WarehouseId } from "@/lib/setuhaul/types";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "SetuHaul — Create & Track Container Shipments" },
      {
        name: "description",
        content:
          "Create a container shipment between warehouses and track it in real time from origin to destination with SetuHaul.",
      },
      { property: "og:title", content: "SetuHaul — Create & Track Container Shipments" },
      {
        property: "og:description",
        content: "Create a shipment, get a Shipment ID, and follow it live from origin to destination.",
      },
    ],
  }),
  component: Landing,
});

const GOODS = ["General Cargo", "Liquid", "Perishable", "Fragile", "Hazardous", "Other"];

function Landing() {
  const { state, createShipment } = useOps();
  const [origin, setOrigin] = useState<WarehouseId | "">("");
  const [destination, setDestination] = useState<WarehouseId | "">("");
  const [goods, setGoods] = useState("General Cargo");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [time, setTime] = useState("10:00");
  const [created, setCreated] = useState<Shipment | null>(null);
  const [query, setQuery] = useState("");
  const [tracked, setTracked] = useState<string | null>(null);

  const sameWarehouse = Boolean(origin && destination && origin === destination);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!origin || !destination || sameWarehouse) return;
    const shipment = createShipment({
      origin,
      destination,
      goodsType: goods,
      pickupDate: date,
      pickupTime: time,
    });
    setCreated(shipment);
    setTracked(null);
    toast.success(`Shipment ${shipment.id} created`);
  }

  function track(id: string) {
    const found = state.shipments.find((s) => s.id.toLowerCase() === id.trim().toLowerCase());
    if (!found) {
      toast.error("No shipment found with that ID");
      return;
    }
    setTracked(found.id);
    setTimeout(
      () => document.getElementById("tracking-result")?.scrollIntoView({ behavior: "smooth" }),
      50,
    );
  }

  const trackedShipment = state.shipments.find((s) => s.id === tracked) ?? null;

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <Brand />
          <nav className="flex items-center gap-1 text-[11px]">
            <Link
              to="/yard"
              className="rounded-sm px-3 py-1.5 font-semibold uppercase tracking-wider text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              Yard Engine
            </Link>
            <Link
              to="/dashboard"
              className="rounded-sm px-3 py-1.5 font-semibold uppercase tracking-wider text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              Dashboard
            </Link>
            <Link
              to="/driver"
              className="rounded-sm px-3 py-1.5 font-semibold uppercase tracking-wider text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              Driver Login
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 pb-24">
        <section className="grid gap-10 py-14 md:grid-cols-[1.05fr_1fr] md:items-start">
          <div>
            <span className="status-pill status-live">
              <span className="status-dot" />6 warehouses · live network
            </span>
            <h1 className="mt-5 text-4xl font-bold leading-[1.08] tracking-tight text-foreground md:text-5xl">
              Move your cargo with SetuHaul
            </h1>
            <p className="mt-4 max-w-md text-base text-muted-foreground">
              Create a shipment and get real-time visibility from origin to destination.
            </p>
            <dl className="mt-10 grid max-w-md grid-cols-3 gap-4 border-t border-border pt-6">
              {[
                ["Warehouses", "6"],
                ["Docking gates", "32"],
                ["Avg. dwell", "48m"],
              ].map(([k, v]) => (
                <div key={k}>
                  <dd className="font-mono text-2xl text-foreground">{v}</dd>
                  <dt className="label-xs mt-1">{k}</dt>
                </div>
              ))}
            </dl>
          </div>

          <div className="panel">
            <div className="panel-head">
              <div className="flex items-center gap-2">
                <PackagePlus className="size-3.5 text-muted-foreground" />
                <h2 className="label-xs !text-foreground">Create shipment</h2>
              </div>
            </div>
            <form onSubmit={submit} className="space-y-4 p-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label className="label-xs">Origin warehouse</Label>
                  <Select value={origin} onValueChange={(v) => setOrigin(v as WarehouseId)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select origin" />
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
                <div className="space-y-1.5">
                  <Label className="label-xs">Destination warehouse</Label>
                  <Select
                    value={destination}
                    onValueChange={(v) => setDestination(v as WarehouseId)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select destination" />
                    </SelectTrigger>
                    <SelectContent>
                      {state.warehouses.map((w) => (
                        <SelectItem key={w.id} value={w.id} disabled={w.id === origin}>
                          {w.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              {sameWarehouse ? (
                <p className="text-xs text-destructive">
                  Origin and destination must be different warehouses.
                </p>
              ) : null}

              <div className="space-y-1.5">
                <Label className="label-xs">Goods type</Label>
                <div className="flex flex-wrap gap-1.5">
                  {GOODS.map((g) => (
                    <button
                      key={g}
                      type="button"
                      onClick={() => setGoods(g)}
                      className={
                        goods === g
                          ? "rounded-sm border border-primary bg-primary px-2.5 py-1 text-[11px] font-semibold text-primary-foreground"
                          : "rounded-sm border border-border bg-surface px-2.5 py-1 text-[11px] font-medium text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                      }
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label className="label-xs">Pickup date</Label>
                  <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label className="label-xs">Pickup time</Label>
                  <Input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
                </div>
              </div>

              <Button type="submit" className="w-full" disabled={!origin || !destination || sameWarehouse}>
                Create Shipment
                <ArrowRight className="size-4" />
              </Button>
            </form>
          </div>
        </section>

        {created ? <CreatedCard shipment={created} onTrack={() => track(created.id)} /> : null}

        <section className="panel mt-10">
          <div className="panel-head">
            <div className="flex items-center gap-2">
              <Search className="size-3.5 text-muted-foreground" />
              <h2 className="label-xs !text-foreground">Track your shipment</h2>
            </div>
          </div>
          <div className="flex flex-col gap-3 p-5 sm:flex-row">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="SHP-2026-001024"
              className="font-mono"
              onKeyDown={(e) => e.key === "Enter" && track(query)}
            />
            <Button onClick={() => track(query)} variant="secondary">
              Track Shipment
            </Button>
          </div>
        </section>

        {trackedShipment ? (
          <div id="tracking-result" className="mt-6">
            <ShipmentTracker shipment={trackedShipment} />
          </div>
        ) : null}
      </main>

      <footer className="border-t border-border bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-xs text-muted-foreground">
          <span>SetuHaul Logistics Orchestration System</span>
          <span className="flex items-center gap-1.5">
            <MapPin className="size-3.5" /> Operating window 07:00 — 16:00
          </span>
        </div>
      </footer>
    </div>
  );
}

function CreatedCard({ shipment, onTrack }: { shipment: Shipment; onTrack: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <section className="panel border-success/40">
      <div className="panel-head">
        <div className="flex items-center gap-2">
          <Check className="size-3.5 text-success" />
          <h2 className="label-xs !text-foreground">Shipment created successfully</h2>
        </div>
        <StatusPill status={shipment.status} />
      </div>
      <div className="grid gap-6 p-5 md:grid-cols-[1.2fr_1fr] md:items-center">
        <div>
          <p className="text-sm text-muted-foreground">Your shipment has been created.</p>
          <div className="label-xs mt-4">Shipment ID</div>
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <span className="font-mono text-2xl font-semibold tracking-tight text-foreground">
              {shipment.id}
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                void navigator.clipboard?.writeText(shipment.id);
                setCopied(true);
                toast.success("Shipment ID copied");
              }}
            >
              <ClipboardCopy className="size-3.5" />
              {copied ? "Copied" : "Copy Shipment ID"}
            </Button>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4 border-l-0 border-border md:border-l md:pl-6">
          <div>
            <div className="label-xs">Origin</div>
            <div className="mt-1 text-sm font-medium">{warehouseName(shipment.origin)}</div>
          </div>
          <div>
            <div className="label-xs">Destination</div>
            <div className="mt-1 text-sm font-medium">{warehouseName(shipment.destination)}</div>
          </div>
          <div>
            <div className="label-xs">Pickup</div>
            <div className="mt-1 font-mono text-sm">
              {shipment.pickupDate} · {shipment.pickupTime}
            </div>
          </div>
          <div className="col-span-3">
            <Button onClick={onTrack} className="w-full" variant="secondary">
              <TruckIcon className="size-4" /> Track Shipment
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
