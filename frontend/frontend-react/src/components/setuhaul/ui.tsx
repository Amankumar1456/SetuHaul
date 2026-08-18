import { Link } from "@tanstack/react-router";
import { Container, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const TONE: Record<string, string> = {
  Available: "status-good",
  Completed: "status-good",
  Confirmed: "status-good",
  Active: "status-good",
  Online: "status-good",
  Operational: "status-good",
  "In Progress": "status-live",
  "In Transit": "status-live",
  Loading: "status-live",
  Unloading: "status-live",
  Docked: "status-live",
  Departed: "status-live",
  Assigned: "status-info",
  Scheduled: "status-info",
  Created: "status-info",
  Expected: "status-info",
  Pending: "status-warn",
  "On Hold": "status-warn",
  Arrived: "status-warn",
  "Origin Arrival": "status-warn",
  "Destination Arrival": "status-warn",
  Conflict: "status-bad",
  Cancelled: "status-bad",
  Inactive: "status-muted",
  "Non-operational": "status-bad",
};

export function StatusPill({ status, className }: { status: string; className?: string }) {
  return (
    <span className={cn("status-pill", TONE[status] ?? "status-muted", className)}>
      <span className="status-dot" />
      {status}
    </span>
  );
}

export function Metric({
  label,
  value,
  sub,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
}) {
  return (
    <div>
      <div className="label-xs">{label}</div>
      <div className="mt-0.5 font-mono text-lg leading-none tracking-tight text-foreground">
        {value}
      </div>
      {sub ? <div className="mt-1 text-[11px] text-muted-foreground">{sub}</div> : null}
    </div>
  );
}

export function Panel({
  title,
  icon: Icon,
  action,
  children,
  className,
}: {
  title: string;
  icon?: LucideIcon;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("panel", className)}>
      <header className="panel-head">
        <div className="flex items-center gap-2">
          {Icon ? <Icon className="size-3.5 text-muted-foreground" /> : null}
          <h2 className="label-xs !text-foreground">{title}</h2>
        </div>
        {action}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Brand({ subtitle = "Logistics Orchestration" }: { subtitle?: string }) {
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <span className="grid size-8 place-items-center rounded-sm bg-primary text-primary-foreground">
        <Container className="size-4" />
      </span>
      <span className="leading-tight">
        <span className="block text-sm font-bold tracking-[0.18em] text-foreground">SETUHAUL</span>
        <span className="block text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
          {subtitle}
        </span>
      </span>
    </Link>
  );
}

export function InternalTopBar({
  subtitle,
  right,
}: {
  subtitle: string;
  right?: ReactNode;
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-surface/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center justify-between gap-4 px-4">
        <Brand subtitle={subtitle} />
        <nav className="flex items-center gap-1 text-xs">
          <NavLink to="/yard">Yard Engine</NavLink>
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/driver">Driver Portal</NavLink>
          {right}
        </nav>
      </div>
    </header>
  );
}

export function NavLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="rounded-sm px-3 py-1.5 font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      activeProps={{ className: "bg-accent text-foreground" }}
    >
      {children}
    </Link>
  );
}
