import { createFileRoute } from "@tanstack/react-router";
import { LogIn, MapPin } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { DriverWorkspace } from "@/components/setuhaul/driver-workspace";
import { InternalTopBar, Panel } from "@/components/setuhaul/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_BASE } from "@/lib/api";

export const Route = createFileRoute("/driver")({
  head: () => ({
    meta: [
      { title: "Driver Portal — SetuHaul" },
      {
        name: "description",
        content:
          "Drivers sign in to see ongoing, upcoming and recent bookings and change slots through the SetuHaul assistant.",
      },
      { property: "og:title", content: "Driver Portal — SetuHaul" },
      {
        property: "og:description",
        content: "Bookings, slot changes and location updates for SetuHaul drivers.",
      },
    ],
  }),
  component: DriverPortal,
});

export interface RealDriver {
  driver_id: string;
  driver_name: string;
  carrier_id: string;
  driver_status: string;
  phone?: string;
  licence_number?: string;
  home_base_city?: string;
}

function DriverPortal() {
  const [mode, setMode] = useState<"welcome" | "login">("welcome");
  const [loggedInDriver, setLoggedInDriver] = useState<RealDriver | null>(null);

  if (loggedInDriver) return <DriverWorkspace driver={loggedInDriver} />;

  return (
    <div className="min-h-screen bg-background">
      <InternalTopBar subtitle="Driver Portal" />
      <main className="mx-auto max-w-md px-4 py-16">
        {mode === "welcome" ? (
          <Panel title="Welcome driver" icon={MapPin}>
            <p className="text-sm text-muted-foreground">
              Sign in with your driver ID to see your bookings.
            </p>
            <div className="mt-5 grid gap-2">
              <Button onClick={() => setMode("login")}>
                <LogIn className="size-4" /> Login
              </Button>
            </div>
          </Panel>
        ) : (
          <LoginForm onLoggedIn={setLoggedInDriver} onBack={() => setMode("welcome")} />
        )}
      </main>
    </div>
  );
}

function LoginForm({
  onLoggedIn,
  onBack,
}: {
  onLoggedIn: (driver: RealDriver) => void;
  onBack: () => void;
}) {
  const [driverId, setDriverId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const id = driverId.trim().toUpperCase();
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/driver/${id}`);
      if (!res.ok) {
        setError("Driver not found. Check your driver ID and try again.");
        setLoading(false);
        return;
      }
      const driver = (await res.json()) as RealDriver;
      onLoggedIn(driver);
      toast.success(`Signed in as ${driver.driver_name}`);
    } catch (e) {
      setError("Could not reach the server. Please try again.");
    }
    setLoading(false);
  }

  return (
    <Panel title="Driver login" icon={LogIn}>
      <p className="mb-4 text-xs text-muted-foreground">
        Enter your driver ID to continue (e.g. DRV001).
      </p>
      <Input
        value={driverId}
        onChange={(e) => setDriverId(e.target.value)}
        placeholder="DRV001"
        className="font-mono"
        autoFocus
        onKeyDown={(e) => e.key === "Enter" && submit()}
      />
      {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
      <Button className="mt-4 w-full" onClick={submit} disabled={loading}>
        {loading ? "Checking..." : "Continue"}
      </Button>
      <Button variant="ghost" className="mt-2 w-full" onClick={onBack}>
        Back
      </Button>
    </Panel>
  );
}