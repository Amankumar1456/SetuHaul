import { Bot, LogOut, RefreshCw, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { InternalTopBar, Panel, StatusPill } from "@/components/setuhaul/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_BASE } from "@/lib/api";
import type { RealDriver } from "@/routes/driver";

interface Msg {
  role: "driver" | "assistant";
  text: string;
}

interface RealShipment {
  shipment_id: string;
  current_status: string;
  destination_facility_id?: string;
  required_dock_type?: string;
  priority_code?: string;
  cargo_desc?: string;
  [key: string]: unknown;
}

const QUICK = [
  "I can't make my current slot",
  "Where do I need to go?",
  "Which shipment am I taking?",
  "Where is my truck?",
  "What is my next booking?",
];

export function DriverWorkspace({
  driver,
  onLogout,
}: {
  driver: RealDriver;
  onLogout?: () => void;
}) {
  const [shipments, setShipments] = useState<RealShipment[]>([]);
  const [shipmentsLoading, setShipmentsLoading] = useState(true);
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      role: "assistant",
      text: `Hi ${driver.driver_name.split(" ")[0]}. Tell me about a delay, ask what's next, or ask about your booking.`,
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  async function loadShipments() {
    setShipmentsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/driver/shipments/${driver.driver_id}`);
      const data = await res.json();
      setShipments(data.shipments ?? []);
    } catch (e) {
      setShipments([]);
    }
    setShipmentsLoading(false);
  }

  useEffect(() => {
    loadShipments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [driver.driver_id]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  const push = (m: Msg) => setMsgs((prev) => [...prev, m]);

  async function handle(text: string) {
    if (!text.trim() || sending) return;
    push({ role: "driver", text });
    setInput("");
    setSending(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ driver_id: driver.driver_id, message: text }),
      });
      const data = await res.json();
      push({ role: "assistant", text: data.response ?? "No response received." });
      // Refresh bookings in case the message resulted in a booking change
      loadShipments();
    } catch (e) {
      push({ role: "assistant", text: "⚠️ Could not reach the assistant. Please try again." });
    }
    setSending(false);
  }

  return (
    <div className="min-h-screen bg-background">
      <InternalTopBar
        subtitle="Driver Portal"
        right={
          onLogout ? (
            <Button size="sm" variant="ghost" onClick={onLogout} className="ml-2">
              <LogOut className="size-3.5" /> Sign out
            </Button>
          ) : null
        }
      />
      <main className="mx-auto max-w-[1400px] px-4 py-6">
        <div className="mb-5 flex flex-wrap items-center gap-4">
          <h1 className="text-xl font-bold tracking-tight">Driver: {driver.driver_name}</h1>
          <span className="font-mono text-xs text-muted-foreground">{driver.driver_id}</span>
          <StatusPill status={driver.driver_status ?? "ACTIVE"} />
          {driver.carrier_id ? (
            <span className="font-mono text-xs text-muted-foreground">{driver.carrier_id}</span>
          ) : null}
        </div>

        <div className="grid gap-4 lg:grid-cols-[380px_minmax(0,1fr)]">
          <Panel
            title="Active Shipments"
            action={
              <button
                onClick={loadShipments}
                className="text-muted-foreground hover:text-foreground"
                title="Refresh"
              >
                <RefreshCw className={sending ? "size-3.5 animate-spin" : "size-3.5"} />
              </button>
            }
          >
            {shipmentsLoading ? (
              <p className="text-xs text-muted-foreground">Loading...</p>
            ) : shipments.length === 0 ? (
              <p className="text-xs text-muted-foreground">No active shipments right now.</p>
            ) : (
              <div className="space-y-2">
                {shipments.map((s) => (
                  <div key={s.shipment_id} className="w-full rounded-md border border-border bg-surface p-3 text-left">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold">{s.shipment_id}</span>
                      <StatusPill status={s.current_status} />
                    </div>
                    {s.cargo_desc ? (
                      <div className="mt-1.5 text-xs text-muted-foreground">{s.cargo_desc}</div>
                    ) : null}
                    <div className="mt-1 flex flex-wrap items-center gap-2 font-mono text-[11px] text-muted-foreground">
                      {s.destination_facility_id ? <span>{s.destination_facility_id}</span> : null}
                      {s.required_dock_type ? <span>· {s.required_dock_type}</span> : null}
                      {s.priority_code ? <span>· {s.priority_code}</span> : null}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="AI assistant" icon={Bot} className="flex min-h-[560px] flex-col">
            <div className="flex h-full flex-col">
              <div className="flex-1 space-y-3 overflow-y-auto pr-1">
                {msgs.map((m, i) => (
                  <div
                    key={i}
                    className={
                      m.role === "driver"
                        ? "ml-auto max-w-[75%] rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
                        : "max-w-[85%] whitespace-pre-line rounded-md bg-muted px-3 py-2 text-sm"
                    }
                  >
                    {m.text}
                  </div>
                ))}
                {sending ? (
                  <div className="max-w-[85%] rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
                    Thinking...
                  </div>
                ) : null}
                <div ref={endRef} />
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border pt-3">
                {QUICK.map((s) => (
                  <button
                    key={s}
                    onClick={() => handle(s)}
                    disabled={sending}
                    className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground hover:border-foreground/30 hover:text-foreground disabled:opacity-50"
                  >
                    {s}
                  </button>
                ))}
              </div>

              <div className="mt-3 flex gap-2">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handle(input)}
                  placeholder="Type only if you need to…"
                  disabled={sending}
                />
                <Button onClick={() => handle(input)} disabled={sending}>
                  <Send className="size-4" />
                </Button>
              </div>
            </div>
          </Panel>
        </div>
      </main>
    </div>
  );
}