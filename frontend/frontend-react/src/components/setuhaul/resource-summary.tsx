/**
 * Resource Summary Component
 * Displays driver, truck, staff, and machinery availability
 * with visual indicators for utilization
 */

import { HardHat, Truck, Users } from "lucide-react";
import { Panel } from "@/components/setuhaul/ui";

interface ResourceData {
  resource_type: string;
  available_count: number;
  total_count: number;
  assigned_count?: number;
  in_transit_count?: number;
}

interface ResourceSummaryProps {
  resources: ResourceData[];
  warehouseId: string;
}

function UtilizationBar({
  available,
  total,
}: {
  available: number;
  total: number;
}) {
  const utilization = ((total - available) / total) * 100;
  const utilizationColor =
    utilization > 80
      ? "bg-destructive"
      : utilization > 60
        ? "bg-warning"
        : utilization > 30
          ? "bg-info"
          : "bg-success";

  return (
    <div className="mt-1 flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full ${utilizationColor} transition-all duration-300`}
          style={{ width: `${utilization}%` }}
        />
      </div>
      <span className="font-mono text-xs text-muted-foreground">
        {available} / {total}
      </span>
    </div>
  );
}

export function ResourceSummary({ resources, warehouseId }: ResourceSummaryProps) {
  const resourceIcons: Record<string, typeof Users> = {
    DRIVER: Users,
    TRUCK: Truck,
    STAFF: HardHat,
    MACHINERY: Truck,
  };

  return (
    <Panel title="Resource Availability" className="space-y-4">
      {resources.map((res) => {
        const Icon = resourceIcons[res.resource_type] || Users;
        const available = res.available_count || 0;
        const total = res.total_count || 0;
        const assigned = res.assigned_count || 0;
        const inTransit = res.in_transit_count || 0;

        return (
          <div key={res.resource_type} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Icon className="size-4 text-muted-foreground" />
                <span className="text-sm font-semibold capitalize">
                  {res.resource_type.toLowerCase()}s
                </span>
              </div>
              <span className="font-mono text-xs text-muted-foreground">
                {available} available
              </span>
            </div>

            <UtilizationBar available={available} total={total} />

            {(assigned > 0 || inTransit > 0) && (
              <div className="flex gap-3 text-xs text-muted-foreground">
                {assigned > 0 && <span>· {assigned} assigned</span>}
                {inTransit > 0 && <span>· {inTransit} in transit</span>}
              </div>
            )}
          </div>
        );
      })}
    </Panel>
  );
}
