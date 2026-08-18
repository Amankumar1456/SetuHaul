/**
 * Escalation Panel Component
 * Displays open escalations and issues requiring attention
 */

import { AlertTriangle, AlertCircle, Clock } from "lucide-react";
import { Panel } from "@/components/setuhaul/ui";
import { cn } from "@/lib/utils";

interface Escalation {
  escalation_id: string;
  shipment_id?: string;
  driver_id?: string;
  exception_type?: string;
  urgency: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  reason: string;
  reported_at: string;
  status?: string;
}

interface EscalationPanelProps {
  escalations: Escalation[];
  warehouseId?: string;
}

const URGENCY_COLORS: Record<string, string> = {
  CRITICAL:
    "border-red-300 bg-red-50 dark:bg-red-950/30 text-red-900 dark:text-red-300",
  HIGH: "border-orange-300 bg-orange-50 dark:bg-orange-950/30 text-orange-900 dark:text-orange-300",
  MEDIUM:
    "border-yellow-300 bg-yellow-50 dark:bg-yellow-950/30 text-yellow-900 dark:text-yellow-300",
  LOW: "border-blue-300 bg-blue-50 dark:bg-blue-950/30 text-blue-900 dark:text-blue-300",
};

const URGENCY_ICONS: Record<string, typeof AlertTriangle> = {
  CRITICAL: AlertTriangle,
  HIGH: AlertTriangle,
  MEDIUM: AlertCircle,
  LOW: AlertCircle,
};

function getTimeAgo(timestamp: string): string {
  const now = new Date();
  const then = new Date(timestamp);
  const minutes = Math.floor((now.getTime() - then.getTime()) / 60000);

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function EscalationPanel({
  escalations,
  warehouseId,
}: EscalationPanelProps) {
  const sortedEscalations = [...escalations].sort((a, b) => {
    const urgencyOrder = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
    return urgencyOrder[a.urgency] - urgencyOrder[b.urgency];
  });

  if (escalations.length === 0) {
    return (
      <Panel title="Escalations" icon={AlertTriangle}>
        <div className="rounded-md border border-green-200 bg-green-50 p-3 text-center dark:border-green-900/30 dark:bg-green-950/30">
          <span className="text-xs font-semibold text-green-900 dark:text-green-300">
            ✓ No open escalations
          </span>
        </div>
      </Panel>
    );
  }

  return (
    <Panel
      title="Escalations"
      icon={AlertTriangle}
      subtitle={`${escalations.length} open`}
    >
      <div className="space-y-2.5">
        {sortedEscalations.map((escalation) => {
          const Icon = URGENCY_ICONS[escalation.urgency];
          const colorClass = URGENCY_COLORS[escalation.urgency];

          return (
            <div
              key={escalation.escalation_id}
              className={cn(
                "rounded-md border px-3 py-2.5 text-xs",
                colorClass
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex gap-2">
                  <Icon className="size-4 mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="font-semibold">
                      {escalation.exception_type || escalation.reason}
                    </div>
                    {escalation.reason && (
                      <div className="mt-1 opacity-90">{escalation.reason}</div>
                    )}
                    <div className="mt-1.5 flex items-center gap-2 text-[11px] opacity-75">
                      {escalation.shipment_id && (
                        <span className="font-mono">{escalation.shipment_id}</span>
                      )}
                      {escalation.driver_id && (
                        <span className="font-mono">{escalation.driver_id}</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-semibold">{escalation.urgency}</div>
                  <div className="mt-1 flex items-center gap-1 text-[10px]">
                    <Clock className="size-3" />
                    {getTimeAgo(escalation.reported_at)}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
