/**
 * Slot Timeline Component
 * Displays hourly slot availability across all gates
 * with visual indicators for slot status
 */

import { Clock, AlertTriangle } from "lucide-react";
import { Panel } from "@/components/setuhaul/ui";
import { cn } from "@/lib/utils";

interface SlotData {
  slot_id: string;
  gate_id: string;
  slot_start_ts: string;
  slot_end_ts: string;
  status: string;
  shipment_id?: string;
}

interface SlotTimelineProps {
  slots: SlotData[];
  warehouseId: string;
  gateList?: string[];
}

const SLOT_STATUS_COLORS: Record<string, string> = {
  AVAILABLE: "bg-green-50 border-green-200 dark:bg-green-950/20",
  BOOKED: "bg-blue-50 border-blue-200 dark:bg-blue-950/20",
  IN_USE: "bg-purple-50 border-purple-200 dark:bg-purple-950/20",
  HELD: "bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20",
  CANCELLED: "bg-red-50 border-red-200 dark:bg-red-950/20 line-through",
};

function getHourBuckets(hoursShown: number = 12): string[] {
  const now = new Date();
  const hours = [];
  for (let i = 0; i < hoursShown; i++) {
    const hour = new Date(now);
    hour.setHours(now.getHours() + i);
    hours.push(hour.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
  }
  return hours;
}

function getSlotForHourAndGate(
  slots: SlotData[],
  gate: string,
  hour: string
): SlotData | null {
  return (
    slots.find(
      (s) =>
        s.gate_id === gate &&
        s.slot_start_ts.includes(hour.substring(0, 5)) // Match HH:MM
    ) || null
  );
}

export function SlotTimeline({
  slots,
  warehouseId,
  gateList = ["A1", "A2", "A3", "A4", "A5", "A6"],
}: SlotTimelineProps) {
  const hours = getHourBuckets(9); // Show next 9 hours

  return (
    <Panel title="Slot Timeline · Gates × Hours" icon={Clock}>
      <div className="overflow-x-auto">
        <div className="min-w-[900px] space-y-2">
          {/* Hour Header */}
          <div className="flex border-b border-border pb-2">
            <div className="w-16 font-mono text-xs font-semibold text-muted-foreground">
              Gate
            </div>
            <div className="flex flex-1 gap-1">
              {hours.map((h) => (
                <div
                  key={h}
                  className="label-xs flex-1 text-center font-mono font-semibold"
                >
                  {h}
                </div>
              ))}
            </div>
          </div>

          {/* Gate Rows */}
          {gateList.map((gate) => (
            <div key={gate} className="flex items-stretch gap-2">
              <div className="w-16 flex items-center">
                <span className="font-mono text-xs font-semibold">{gate}</span>
              </div>
              <div className="flex flex-1 gap-1">
                {hours.map((h) => {
                  const slot = getSlotForHourAndGate(slots, gate, h);
                  const status = slot?.status || "AVAILABLE";
                  const colorClass = SLOT_STATUS_COLORS[status] || SLOT_STATUS_COLORS.AVAILABLE;

                  return (
                    <div
                      key={`${gate}-${h}`}
                      className={cn(
                        "flex-1 rounded-sm border px-1.5 py-2 text-[9px] leading-tight font-mono",
                        colorClass
                      )}
                      title={
                        slot
                          ? `${gate} ${h} · ${status}${slot.shipment_id ? ` · ${slot.shipment_id}` : ""}`
                          : `${gate} ${h} · Available`
                      }
                    >
                      {slot && (
                        <>
                          <div className="font-semibold">{slot.status[0]}</div>
                          {slot.shipment_id && (
                            <div className="truncate text-[8px] opacity-75">
                              {slot.shipment_id.substring(0, 8)}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Status Legend */}
      <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-3 text-xs">
        <div className="flex items-center gap-1">
          <div className="h-2.5 w-2.5 rounded-sm bg-green-100 border border-green-200" />
          <span className="text-muted-foreground">Available</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-2.5 w-2.5 rounded-sm bg-blue-100 border border-blue-200" />
          <span className="text-muted-foreground">Booked</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-2.5 w-2.5 rounded-sm bg-purple-100 border border-purple-200" />
          <span className="text-muted-foreground">In Use</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-2.5 w-2.5 rounded-sm bg-yellow-100 border border-yellow-200" />
          <span className="text-muted-foreground">Held</span>
        </div>
      </div>
    </Panel>
  );
}
