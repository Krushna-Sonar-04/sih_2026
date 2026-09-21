import { Link, useRouterState } from "@tanstack/react-router";
import { Bell, Clock3, Crosshair, Gauge, History, LayoutDashboard, Plug, Settings } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "./ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./ui/tooltip";
import { useBackendHealth } from "@/lib/use-backend";

const primary = [
  ["/dashboard", "Dashboard", LayoutDashboard], ["/watches", "Watches", Crosshair],
  ["/time-machine", "Narrative Time-Machine", Clock3], ["/alerts", "Alerts", Bell], ["/history", "History", History],
] as const;
const secondary = [["/connectors", "Connector Center", Plug], ["/system-health", "System Health", Gauge], ["/settings", "Settings", Settings]] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const { mode, message, connected } = useBackendHealth();
  return <TooltipProvider delayDuration={300}>
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b border-border bg-card/95 backdrop-blur-md">
        <div className="mx-auto flex h-18 max-w-[1800px] items-center gap-8 px-5 lg:px-8">
          <Link to="/dashboard" className="flex shrink-0 items-center gap-3" aria-label="DRISHTI Dashboard">
            <div className="relative grid size-9 place-items-center rounded-sm bg-primary text-primary-foreground"><span className="size-3.5 rounded-full border-2 border-primary-foreground"/><span className="absolute bottom-1.5 right-1.5 size-1.5 rounded-full bg-signal-warning"/></div>
            <div><div className="text-base font-extrabold text-primary">DRISHTI</div><div className="text-[10px] font-semibold text-muted-foreground">NARRATIVE INTELLIGENCE</div></div>
          </Link>
          <nav className="hidden h-full items-center gap-1 md:flex" aria-label="Primary navigation">
            {primary.map(([to,label,Icon]) => <NavItem key={to} to={to} label={label} active={path===to} icon={<Icon/>}/>) }
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Tooltip><TooltipTrigger asChild><span className={`hidden border px-2.5 py-1.5 text-[10px] font-bold lg:inline ${mode==="LIVE MODE"?"border-signal-positive/30 bg-signal-positive/10 text-signal-positive":"border-primary/20 bg-accent text-primary"}`}>{mode}</span></TooltipTrigger><TooltipContent>{message}</TooltipContent></Tooltip>
            <span className="hidden items-center gap-2 px-2 text-xs text-muted-foreground xl:flex"><span className={`size-1.5 rounded-full ${connected?"bg-signal-positive":"bg-signal-warning"}`}/>{connected?"Backend connected":"Prototype operational"}</span>
            <span className="hidden px-2 text-xs text-muted-foreground 2xl:inline">21 Sep 2026 · 12:37 IST</span>
            {secondary.map(([to,label,Icon]) => <Tooltip key={to}><TooltipTrigger asChild><Button variant="ghost" size="icon" asChild className={path===to?"bg-accent text-primary":"text-muted-foreground"}><Link to={to} aria-label={label}><Icon/></Link></Button></TooltipTrigger><TooltipContent>{label}</TooltipContent></Tooltip>)}
            <Tooltip><TooltipTrigger asChild><div className="ml-1 flex items-center gap-2 border-l border-border pl-3"><div className="grid size-9 place-items-center rounded-full bg-primary text-xs font-bold text-primary-foreground">AS</div><div className="hidden 2xl:block"><div className="text-xs font-semibold">Analyst Sonar</div><div className="text-[10px] text-muted-foreground">Analyst</div></div></div></TooltipTrigger><TooltipContent>Analyst Sonar · Analyst</TooltipContent></Tooltip>
          </div>
        </div>
        <nav className="flex h-11 items-center gap-1 overflow-x-auto border-t border-border px-4 md:hidden" aria-label="Mobile navigation">
          {primary.map(([to,label,Icon]) => <NavItem key={to} to={to} label={label} active={path===to} icon={<Icon/>}/>) }
        </nav>
      </header>
      <main className="min-h-[calc(100vh-4.5rem)]"><div className="mx-auto max-w-[1800px] px-5 py-8 lg:px-8 lg:py-10">{children}</div></main>
    </div>
  </TooltipProvider>;
}

function NavItem({to,label,active,icon}:{to:string;label:string;active:boolean;icon:ReactNode}) {
  return <Link to={to} className={`relative flex h-full shrink-0 items-center gap-2 px-3 text-xs font-medium transition-colors ${active?"text-primary":"text-muted-foreground hover:text-foreground"}`}>{active&&<span className="absolute inset-x-3 bottom-0 h-0.5 bg-primary"/>}<span className={`[&_svg]:size-3.5 ${active?"text-primary":""}`}>{icon}</span><span>{label}</span></Link>;
}