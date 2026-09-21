import { createFileRoute, Link } from "@tanstack/react-router";
import { CircleAlert, CircleCheck, CircleDashed, Database, FlaskConical, MessageSquareText, Server, Workflow } from "lucide-react";
import { PageHeading } from "@/components/page-heading";
import { useBackendHealth } from "@/lib/use-backend";
import type { ComponentHealth } from "@/lib/api-client";

const demoAdapters:ComponentHealth[]=[
  {component:"X adapter",status:"Not configured",detail:"No X credentials configured. Demo dataset in use."},
  {component:"Telegram adapter",status:"Not configured",detail:"No Telegram credentials configured. Demo dataset in use."},
  {component:"Instagram adapter",status:"Planned",detail:"Adapter interface reserved; not implemented."},
  {component:"Facebook adapter",status:"Planned",detail:"Adapter interface reserved; not implemented."},
  {component:"Reddit adapter",status:"Planned",detail:"Adapter interface reserved; not implemented."},
  {component:"YouTube adapter",status:"Planned",detail:"Adapter interface reserved; not implemented."},
];
const demoAnalytics:ComponentHealth[]=[
  {component:"Sentiment engine",status:"Demo",detail:"Deterministic seeded sentiment and emotion indicators."},
  {component:"Trend engine",status:"Demo",detail:"Seeded mention counts and velocity comparisons."},
  {component:"Network engine",status:"Demo",detail:"Seeded relationships, centrality and community grouping."},
  {component:"Demographic engine",status:"Demo",detail:"Aggregate cohort estimates only; no individual attributes."},
];

export const Route=createFileRoute("/system-health")({head:()=>({meta:[{title:"System Health — DRISHTI"},{name:"description",content:"Live backend component, adapter and analysis-engine status for the DRISHTI workspace."},{property:"og:title",content:"System Health — DRISHTI"},{property:"og:description",content:"Adapter, storage and analysis-engine status with honest connection labelling."},{property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"}]}),component:HealthPage});

function StatusIcon({status}:{status:string}){
  if(status==="Operational"||status==="Connected")return <CircleCheck className="size-4 text-signal-positive"/>;
  if(status==="Error"||status==="Unavailable")return <CircleAlert className="size-4 text-signal-negative"/>;
  return <CircleDashed className="size-4 text-signal-warning"/>;
}
function Group({title,icon,items}:{title:string;icon:React.ReactNode;items:ComponentHealth[]}){
  return <section className="border-t-2 border-primary/25 bg-card">
    <div className="flex items-center gap-3 border-b border-border px-5 py-5">{icon}<h2 className="text-lg font-semibold">{title}</h2></div>
    {items.map(item=><div key={item.component} className="border-b border-border px-5 py-4 last:border-b-0">
      <div className="flex items-center gap-3"><span className="text-sm font-medium">{item.component}</span>
        <span className="ml-auto flex items-center gap-2 text-xs text-muted-foreground"><StatusIcon status={item.status}/>{item.status}</span></div>
      <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{item.detail}</p>
      {(item.record_count!=null||item.last_operation)&&<div className="mt-2 flex gap-5 font-mono text-[10px] text-muted-foreground">
        {item.record_count!=null&&<span>{item.record_count} records</span>}
        {item.last_operation&&<span>last operation {new Date(item.last_operation).toUTCString().slice(5,22)}</span>}
      </div>}
    </div>)}
  </section>;
}

function HealthPage(){
  const {connected,health,configured}=useBackendHealth();
  const adapters=health?.adapters??demoAdapters;
  const analytics=health?.analytics??demoAnalytics;
  const platform:ComponentHealth[]=health
    ?[health.api,health.database]
    :[{component:"API",status:configured?"Unavailable":"Demo",detail:configured?"Backend configured but not reachable. Demo Mode remains available.":"No backend configured. The workspace runs on the deterministic demo engine."},
      {component:"Database",status:"Demo",detail:"Records served from the seeded in-app dataset."}];
  const assistant:ComponentHealth=health?.assistant??{component:"Analyst assistant",status:"Demo",detail:"Deterministic grounded responses composed from the seeded dataset."};

  const ingestion=health?.ingestion;
  const stamp=(value?:string|null)=>value?new Date(value).toUTCString().slice(5,22)+" UTC":"No successful run recorded";

  return <><PageHeading title="System Health" description="Adapter, storage and analysis-engine status. Live labels are used only when an integration is actually connected."
    actions={<span className={`border px-2.5 py-1.5 text-xs font-semibold ${connected&&health?.mode==="live"?"border-signal-positive/30 bg-signal-positive/10 text-signal-positive":"border-signal-warning/30 bg-signal-warning/10 text-signal-warning"}`}>{connected?(health?.mode==="live"?"LIVE MODE":"DEMO MODE · BACKEND CONNECTED"):"DEMO MODE"}</span>}/>
    <div className="grid gap-8 lg:grid-cols-2">
      <Group title="Platform services" icon={<Server className="size-5 text-primary"/>} items={platform}/>
      <Group title="Data sources" icon={<Database className="size-5 text-primary"/>} items={adapters}/>
      <Group title="Analysis services" icon={<FlaskConical className="size-5 text-primary"/>} items={analytics}/>
      <Group title="Assistant" icon={<MessageSquareText className="size-5 text-primary"/>} items={[assistant]}/>
    </div>
    <section className="mt-8 border-t-2 border-primary/25 bg-card">
      <div className="flex items-center gap-3 border-b border-border px-5 py-5"><Workflow className="size-5 text-primary"/><h2 className="text-lg font-semibold">Ingestion</h2>
        <Link to="/connectors" className="ml-auto text-xs font-semibold text-primary hover:underline">Open Connector Center</Link></div>
      <dl className="grid gap-x-8 gap-y-4 px-5 py-5 text-sm sm:grid-cols-2 lg:grid-cols-5">
        {[["Last successful run",stamp(ingestion?.last_successful_run)],
          ["Records processed",String(ingestion?.records_processed??0)],
          ["Records rejected",String(ingestion?.records_rejected??0)],
          ["Duplicates",String(ingestion?.duplicates??0)],
          ["Current job",ingestion?.current_job??"Idle"]].map(([label,value])=>
          <div key={label}><dt className="text-xs font-semibold text-muted-foreground">{label}</dt><dd className="mt-1 font-mono text-xs">{value}</dd></div>)}
      </dl>
    </section>
    <p className="mt-8 max-w-3xl text-sm leading-6 text-muted-foreground">{health?.message??"Live integrations are not configured. Demo Mode remains available."} Platform status is reported as Connected, Not configured, Demo, Planned or Unavailable — a live label is never shown unless an adapter actually returned data.</p></>;
}
