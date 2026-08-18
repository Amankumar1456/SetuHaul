import { Outlet, createFileRoute } from "@tanstack/react-router";

import { InternalTopBar } from "@/components/setuhaul/ui";
import { OpsAssistant } from "@/components/setuhaul/ops-assistant";

export const Route = createFileRoute("/dashboard")({
  component: DashboardLayout,
});

function DashboardLayout() {
  return (
    <div className="min-h-screen bg-background">
      <InternalTopBar subtitle="Operations Dashboard" />
      <Outlet />
      <OpsAssistant />
    </div>
  );
}
