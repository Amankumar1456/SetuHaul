import { Bot, Send, X } from "lucide-react";
import { useState } from "react";
import { API_BASE as API } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useOps, warehouseName, warehouseStats } from "@/lib/setuhaul/store";
import type { OpsState } from "@/lib/setuhaul/types";

interface Msg {
  role: "user" | "assistant";
  text: string;
}

const SUGGESTIONS = [
  "Show Warehouse A status",
  "Which trucks are in transit?",
  "Which shipments are delayed?",
  "Available drivers at Warehouse B",
  "Where is SHP-2026-001024?",
];

export function answerOpsQuery(state: OpsState, q: string): string {
  const text = q.toLowerCase();

  const shipmentMatch = q.match(/SHP-\d{4}-\d{6}/i);
  if (shipmentMatch) {
    const sh = state.shipments.find((s) => s.id.toLowerCase() === shipmentMatch[0].toLowerCase());
    if (!sh) return `No shipment found with ID ${shipmentMatch[0]}.`;
    const dr = state.drivers.find((d) => d.id === sh.driverId);
    return [
      `${sh.id} · ${sh.status}`,
      `Route: ${warehouseName(sh.origin)} → ${warehouseName(sh.destination)}`,
      `Truck: ${sh.truckId ?? "unassigned"} · Driver: ${dr?.name ?? "unassigned"}`,
      `Latest ETA: ${sh.eta ?? "being scheduled"}`,
    ].join("\n");
  }

  const driverName = state.drivers.find((d) => text.includes(d.name.split(" ")[0]!.toLowerCase()));
  if (driverName && (text.includes("where") || text.includes("driver"))) {
    const sh = state.shipments.find((s) => s.driverId === driverName.id && s.status !== "Completed");
    return [
      `Driver ${driverName.name} · ${driverName.status}`,
      `Current location: ${driverName.currentWarehouse ? warehouseName(driverName.currentWarehouse) : "In transit"}`,
      sh ? `Current shipment: ${sh.id} (${warehouseName(sh.origin)} → ${warehouseName(sh.destination)})` : "No active shipment",
      driverName.etaMinutes ? `Latest ETA: ${driverName.etaMinutes} min` : "",
    ]
      .filter(Boolean)
      .join("\n");
  }

  const wh = state.warehouses.find((w) => text.includes(w.name.toLowerCase()) || text.includes(w.code.toLowerCase() + " "));
  if (wh) {
    const s = warehouseStats(state, wh.id);
    if (text.includes("driver")) {
      const list = state.drivers.filter((d) => d.currentWarehouse === wh.id && d.status === "Available");
      return list.length
        ? `Available drivers at ${wh.name}:\n${list.map((d) => `• ${d.name} (${d.id})`).join("\n")}`
        : `No available drivers at ${wh.name}.`;
    }
    return [
      `${wh.name} · Operational (${wh.opensAt}–${wh.closesAt})`,
      `Drivers: ${s.driversAvailable} available · ${s.driversTransit} inbound`,
      `Trucks: ${s.trucksAvailable} available · ${s.trucksInYard} in yard`,
      `Yard: ${s.yardOccupancy}/${s.yardCapacity} occupied`,
      `Slots: ${s.slotsAvailable} available · ${s.slotsBooked} booked · ${s.slotsOccupied} in progress`,
      `Escalations: ${s.escalations.length}`,
    ].join("\n");
  }

  if (text.includes("transit")) {
    const list = state.trucks.filter((t) => t.status === "In Transit");
    return list.length
      ? `Trucks in transit:\n${list
          .map((t) => `• ${t.id} · ${t.shipmentId ?? "no shipment"}`)
          .join("\n")}`
      : "No trucks currently in transit.";
  }

  if (text.includes("delay") || text.includes("escalat") || text.includes("exception")) {
    return state.escalations.length
      ? `Active escalations:\n${state.escalations
          .map((e) => `⚠ ${e.title} · ${e.shipmentId ?? ""} — ${e.detail}`)
          .join("\n")}`
      : "No active escalations.";
  }

  if (text.includes("yard")) {
    return state.warehouses
      .map((w) => {
        const s = warehouseStats(state, w.id);
        return `${w.name}: ${s.yardOccupancy}/${s.yardCapacity} occupied · ${s.upcomingArrivals} inbound`;
      })
      .join("\n");
  }

  return "I can report warehouse status, yard occupancy, resources, escalations, truck/driver locations and shipment state. Try “Show Warehouse A status” or paste a shipment ID.";
}

export function OpsAssistant() {
  const { state } = useOps();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "assistant", text: "Operations assistant online. Ask about warehouses, trucks, drivers or shipments." },
  ]);

  async function ask(q: string) {
  if (!q.trim()) return;
  setMsgs((m) => [...m, { role: "user", text: q }]);
  setInput("");

  try {
    const res = await fetch(`${API}/ops/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ driver_id: "ADMIN-OPS", message: q }),
    });
    const data = await res.json();
    setMsgs((m) => [...m, { role: "assistant", text: data.response ?? "No response received." }]);
  } catch (e) {
    setMsgs((m) => [...m, { role: "assistant", text: "⚠️ Could not reach the assistant." }]);
  }
}

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full bg-primary px-4 py-3 text-xs font-semibold uppercase tracking-wider text-primary-foreground shadow-lg transition-transform hover:scale-[1.03]"
      >
        <Bot className="size-4" /> Ops Assistant
      </button>
    );
  }

  return (
    <div className="panel fixed bottom-5 right-5 z-40 flex h-[520px] w-[380px] max-w-[calc(100vw-2rem)] flex-col shadow-xl">
      <div className="panel-head">
        <div className="flex items-center gap-2">
          <Bot className="size-3.5 text-muted-foreground" />
          <span className="label-xs !text-foreground">Operations assistant</span>
        </div>
        <button onClick={() => setOpen(false)} aria-label="Close assistant">
          <X className="size-4 text-muted-foreground hover:text-foreground" />
        </button>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {msgs.map((m, i) => (
          <div
            key={i}
            className={
              m.role === "user"
                ? "ml-auto max-w-[85%] rounded-md bg-primary px-3 py-2 text-xs text-primary-foreground"
                : "max-w-[92%] whitespace-pre-line rounded-md bg-muted px-3 py-2 text-xs"
            }
          >
            {m.text}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5 border-t border-border p-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => ask(s)}
            className="rounded-full border border-border px-2 py-1 text-[10px] text-muted-foreground hover:border-foreground/30 hover:text-foreground"
          >
            {s}
          </button>
        ))}
      </div>
      <div className="flex gap-2 border-t border-border p-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(input)}
          placeholder="Ask operations…"
          className="h-9 text-xs"
        />
        <Button size="sm" className="h-9" onClick={() => ask(input)}>
          <Send className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}
