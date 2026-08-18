/**
 * Yard Snapshot Component
 * Displays current trucks in yard with their states
 * and pending arrivals
 */

import { Clock, Truck, AlertCircle } from "lucide-react";
import { Panel, StatusPill } from "@/components/setuhaul/ui";

interface TruckState {
  truck_id: string;
  state: string;
  state_timestamp: string;
  gate_id?: string;
  facility_id: string;
}

interface ArrivingTruck {
  truck_id: string;
  shipment_id: string;
  eta_ts: string;
  status: string;
}

interface YardSnapshotProps {
  trucksInYard: TruckState[];
  arrivingTrucks: ArrivingTruck[];
  warehouseId: string;
}

const STATE_COLORS: Record<string, string> = {
  EXPECTED: "bg-blue-50 text-blue-900 border-blue-200 dark:bg-blue-950/30 dark:text-blue-300",
  ARRIVED: "bg-yellow-50 text-yellow-900 border-yellow-200 dark:bg-yellow-950/30 dark:text-yellow-300",
  DOCKED: "bg-green-50 text-green-900 border-green-200 dark:bg-green-950/30 dark:text-green-300",
  DEPARTED: "bg-gray-50 text-gray-900 border-gray-200 dark:bg-gray-900/30 dark:text-gray-300",
};

export function YardSnapshot({
  trucksInYard,
  arrivingTrucks,
  warehouseId,
}: YardSnapshotProps) {
  return (
    <div className="space-y-4">
      <Panel title="Trucks in Yard" icon={Truck}>
        {trucksInYard.length === 0 ? (
          <p className="text-xs text-muted-foreground">No trucks currently in yard.</p>
        ) : (
          <div className="space-y-2">
            {trucksInYard.map((truck) => (
              <div
                key={truck.truck_id}
                className={`rounded-md border px-3 py-2.5 text-xs ${STATE_COLORS[truck.state] || "bg-muted"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono font-semibold">{truck.truck_id}</span>
                  <StatusPill status={truck.state} />
                </div>
                <div className="mt-1.5 flex items-center gap-2 text-[11px]">
                  {truck.gate_id && (
                    <>
                      <Truck className="size-3" />
                      <span>Gate {truck.gate_id}</span>
                    </>
                  )}
                </div>
                {truck.state_timestamp && (
                  <div className="mt-1 text-[10px] opacity-70">
                    Since {new Date(truck.state_timestamp).toLocaleTimeString()}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Pending Arrivals" icon={Clock}>
        {arrivingTrucks.length === 0 ? (
          <p className="text-xs text-muted-foreground">No trucks scheduled to arrive.</p>
        ) : (
          <div className="space-y-2">
            {arrivingTrucks.map((arrival) => {
              const etaTime = new Date(arrival.eta_ts);
              const now = new Date();
              const minutesUntilArrival = Math.floor(
                (etaTime.getTime() - now.getTime()) / 60000
              );
              const isOverdue = minutesUntilArrival < 0;

              return (
                <div
                  key={arrival.truck_id}
                  className={`rounded-md border px-3 py-2.5 text-xs ${isOverdue ? "border-destructive/50 bg-destructive/5" : "border-border bg-muted/30"}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <span className="font-mono font-semibold">{arrival.truck_id}</span>
                      <div className="mt-0.5 text-[10px] text-muted-foreground">
                        {arrival.shipment_id}
                      </div>
                    </div>
                    {isOverdue && <AlertCircle className="size-4 text-destructive" />}
                  </div>
                  <div className="mt-1.5 flex items-center gap-2 text-[11px]">
                    <Clock className="size-3" />
                    <span>
                      ETA: {etaTime.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                    {isOverdue && (
                      <span className="text-destructive">
                        ({Math.abs(minutesUntilArrival)} mins overdue)
                      </span>
                    )}
                    {minutesUntilArrival > 0 && (
                      <span className="text-muted-foreground">
                        (in {minutesUntilArrival} mins)
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}
