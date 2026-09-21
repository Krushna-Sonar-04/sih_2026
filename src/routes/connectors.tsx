import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CircleAlert, CircleCheck, CircleDashed, Clock3, Plug, ShieldCheck } from "lucide-react";
import { PageHeading } from "@/components/page-heading";
import { ModeSwitch } from "@/components/mode-switch";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, backendConfigured, type ConnectionTest, type ConnectorState, type IngestionLog, type IngestionLogDetail, type SchedulerState } from "@/lib/api-client";

export const Route=createFileRoute("/connectors")({head:()=>({meta:[
  {title:"Connector Center — DRISHTI"},
  {name:"description",content:"Platform connector status, ingestion activity and connection testing for the DRISHTI workspace."},
  {property:"og:title",content:"Connector Center — DRISHTI"},
  {property:"og:description",content:"Honest connector status: connected, not configured, planned or error — with ingestion history."},
  {property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"},
]}),component:ConnectorCenter});

/** Offline view: shown when the backend is not reachable. Never claims a live connection. */
const offlineConnectors:ConnectorState[]=[
  {platform:"Telegram",status:"Not configured",detail:"Backend not reachable. Configure TELEGRAM_BOT_TOKEN in the backend environment.",configured:false,enabled:true,schedule:"manual",identifier:"",last_ingestion:null,last_success:null,next_ingestion:null,records_collected:0,last_error:null},
  {platform:"X",status:"Not configured",detail:"Backend not reachable. Configure X_BEARER_TOKEN in the backend environment.",configured:false,enabled:true,schedule:"manual",identifier:"",last_ingestion:null,last_success:null,next_ingestion:null,records_collected:0,last_error:null},
  ...["Instagram","Facebook","Reddit","YouTube"].map(platform=>({platform,status:"Planned",detail:"Adapter interface reserved; integration not implemented in this prototype.",configured:false,enabled:false,schedule:"manual",identifier:"",last_ingestion:null,last_success:null,next_ingestion:null,records_collected:0,last_error:null})),
];

const configurationHelp:Record<string,string[]>={
  Telegram:["TELEGRAM_BOT_TOKEN","TELEGRAM_CHANNEL_ID","TELEGRAM_POLL_SECONDS"],
  X:["X_BEARER_TOKEN","X_CLIENT_ID","X_CLIENT_SECRET"],
};

function stamp(value:string|null|undefined){ return value?new Date(value).toUTCString().slice(5,22)+" UTC":"—" }

function StatusPill({status}:{status:string}){
  const positive=status==="Connected";
  const negative=["Error","Unauthorized","Invalid credentials","Unavailable","No accessible source"].includes(status);
  const tone=positive?"border-signal-positive/30 bg-signal-positive/10 text-signal-positive"
    :negative?"border-signal-negative/30 bg-signal-negative/10 text-signal-negative"
    :"border-signal-warning/30 bg-signal-warning/10 text-signal-warning";
  const Icon=positive?CircleCheck:negative?CircleAlert:CircleDashed;
  return <span className={`inline-flex items-center gap-1.5 border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${tone}`}><Icon className="size-3"/>{status}</span>;
}

function ConnectorCard({state}:{state:ConnectorState}){
  const [testing,setTesting]=useState(false);
  const [result,setResult]=useState<ConnectionTest|null>(null);
  const planned=state.status==="Planned";
  const fields=configurationHelp[state.platform];
  async function test(){
    setTesting(true);
    const outcome=await api.testConnector(state.platform);
    setResult(outcome??{platform:state.platform,configured:false,authenticated:false,source_reachable:false,status:"Unavailable",identifier:"",last_message_time:null,last_success:null,error:"Backend not reachable. Demo Mode remains available."});
    setTesting(false);
  }
  return <section className="border-t-2 border-primary/25 bg-card">
    <div className="flex flex-wrap items-center gap-3 border-b border-border px-5 py-4">
      <Plug className="size-4 text-primary"/>
      <h3 className="text-base font-semibold">{state.platform}</h3>
      <div className="ml-auto flex items-center gap-3"><StatusPill status={state.status}/></div>
    </div>
    <div className="px-5 py-4">
      <p className="text-xs leading-5 text-muted-foreground">{state.detail}</p>
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 font-mono text-[10px] text-muted-foreground lg:grid-cols-4">
        <div><dt className="font-sans font-semibold text-foreground">Configuration</dt><dd>{state.configured?`Configured ${state.identifier}`:"Not configured"}</dd></div>
        <div><dt className="font-sans font-semibold text-foreground">Last ingestion</dt><dd>{stamp(state.last_ingestion)}</dd></div>
        <div><dt className="font-sans font-semibold text-foreground">Records collected</dt><dd>{state.records_collected}</dd></div>
        <div><dt className="font-sans font-semibold text-foreground">Next ingestion</dt><dd>{state.next_ingestion?stamp(state.next_ingestion):state.schedule==="manual"?"Manual":"—"}</dd></div>
      </dl>
      {state.last_error&&<p className="mt-3 border-l-2 border-signal-negative/40 bg-signal-negative/5 px-3 py-2 text-xs text-signal-negative">{state.last_error}</p>}
      {fields&&<p className="mt-3 text-[11px] leading-5 text-muted-foreground">Configure locally in <code className="font-mono">backend/.env</code>: {fields.join(" · ")}. Credentials stay server-side and are never sent to this page.</p>}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button variant="outline" size="sm" disabled={planned||testing} onClick={()=>void test()}>{testing?"Testing…":"Test connection"}</Button>
        {planned&&<span className="text-[11px] text-muted-foreground">Planned integration — no connection is attempted.</span>}
        {result&&<span className="font-mono text-[10px] text-muted-foreground">
          {result.status} · configured {String(result.configured)} · authenticated {String(result.authenticated)} · source {String(result.source_accessible??result.source_reachable)}
          {result.source_name?` · ${result.source_name}`:""}{result.account?` · ${result.account}`:""}{result.error?` · ${result.error}`:""}
        </span>}
      </div>
    </div>
  </section>;
}

function ConnectorCenter(){
  const connectors=useQuery({queryKey:["drishti","connectors"],queryFn:()=>api.connectors(),enabled:backendConfigured,retry:false,refetchInterval:60_000});
  const logs=useQuery({queryKey:["drishti","ingestion-logs"],queryFn:()=>api.ingestionLogs(),enabled:backendConfigured,retry:false,refetchInterval:60_000});
  const scheduler=useQuery<SchedulerState|null>({queryKey:["drishti","scheduler"],queryFn:()=>api.scheduler(),enabled:backendConfigured,retry:false});
  const [runId,setRunId]=useState<string|null>(null);
  const detail=useQuery<IngestionLogDetail|null>({queryKey:["drishti","ingestion-log",runId],queryFn:()=>api.ingestionLog(runId as string),enabled:Boolean(runId)&&backendConfigured,retry:false});
  const states=connectors.data??offlineConnectors;
  const entries:IngestionLog[]=logs.data??[];
  const live=states.some(state=>state.status==="Connected");

  return <><PageHeading title="Connector Center"
    description="Platform connection state, ingestion activity and connection testing. Credentials are held only in the backend environment — no token is ever displayed here."
    actions={<div className="flex flex-wrap items-center gap-4">
      <span className={`border px-2.5 py-1.5 text-xs font-semibold ${live?"border-signal-positive/30 bg-signal-positive/10 text-signal-positive":"border-signal-warning/30 bg-signal-warning/10 text-signal-warning"}`}>{live?"LIVE SOURCES AVAILABLE":"DEMO MODE"}</span>
      <ModeSwitch connectors={states}/>
    </div>}/>

    <div className="mb-8 flex flex-wrap items-center gap-5 border-y border-border bg-muted/25 px-5 py-4 text-xs text-muted-foreground">
      <span className="inline-flex items-center gap-2 font-semibold text-foreground"><ShieldCheck className="size-4 text-primary"/>Server-side credentials only</span>
      <span className="inline-flex items-center gap-2"><Clock3 className="size-3.5"/>Scheduler: {scheduler.data?`${scheduler.data.status} · ${scheduler.data.interval}`:"Manual"}</span>
      <span>Ingestion order of priority: Telegram → X → Instagram → Facebook → Reddit → YouTube</span>
    </div>

    <div className="grid gap-8 lg:grid-cols-2">{states.map(state=><ConnectorCard key={state.platform} state={state}/>)}</div>

    <section className="mt-10 border-t-2 border-primary/25 bg-card">
      <div className="flex items-center gap-3 border-b border-border px-5 py-5"><h2 className="text-lg font-semibold">Ingestion activity</h2>
        <span className="ml-auto text-xs text-muted-foreground">{entries.length?`${entries.length} recent runs`:"No ingestion runs recorded"}</span></div>
      {entries.length===0
        ? <p className="px-5 py-6 text-sm text-muted-foreground">No ingestion has run yet. Demo Mode continues to serve the deterministic seeded dataset.</p>
        : <div className="overflow-x-auto"><div className="min-w-[880px]">
            <div className="grid grid-cols-[1fr_.8fr_.8fr_.6fr_.6fr_.6fr_.6fr] gap-4 border-b border-border bg-muted/45 px-5 py-3 text-xs font-semibold text-muted-foreground">
              <span>Started</span><span>Platform</span><span>Status</span><span>Found</span><span>New</span><span>Duplicate</span><span>Failed</span></div>
            {entries.map((entry,i)=><button type="button" key={entry.id} onClick={()=>setRunId(entry.id)} className={`grid w-full grid-cols-[1fr_.8fr_.8fr_.6fr_.6fr_.6fr_.6fr] gap-4 border-b border-border px-5 py-3 text-left text-xs last:border-b-0 hover:bg-accent/60 ${i%2?"bg-muted/15":"bg-card"}`}>
              <span className="font-mono text-[10px] text-muted-foreground">{stamp(entry.started_at)}</span>
              <span className="font-medium">{entry.platform}</span><span>{entry.status}</span>
              <span>{entry.records_found}</span><span>{entry.records_new}</span><span>{entry.records_duplicate}</span><span>{entry.records_failed}</span>
            </button>)}
          </div></div>}
    </section>

    <Dialog open={Boolean(runId)} onOpenChange={open=>!open&&setRunId(null)}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Ingestion run</DialogTitle>
          <DialogDescription>{detail.data?`${detail.data.platform} · ${detail.data.job_type} · ${detail.data.status}`:"Loading run detail…"}</DialogDescription></DialogHeader>
        {detail.data&&<div className="grid gap-4 text-xs">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 font-mono text-[10px] text-muted-foreground">
            <div><dt className="font-sans font-semibold text-foreground">Run</dt><dd>{detail.data.id}</dd></div>
            <div><dt className="font-sans font-semibold text-foreground">Watch</dt><dd>{detail.data.watch_id??"—"}</dd></div>
            <div><dt className="font-sans font-semibold text-foreground">Started</dt><dd>{stamp(detail.data.started_at)}</dd></div>
            <div><dt className="font-sans font-semibold text-foreground">Completed</dt><dd>{stamp(detail.data.completed_at)}</dd></div>
            <div><dt className="font-sans font-semibold text-foreground">Found / new</dt><dd>{detail.data.records_found} / {detail.data.records_new}</dd></div>
            <div><dt className="font-sans font-semibold text-foreground">Duplicate / failed</dt><dd>{detail.data.records_duplicate} / {detail.data.records_failed}</dd></div>
          </dl>
          <p className="border-l-2 border-primary bg-accent/40 px-3 py-2 leading-5 text-muted-foreground">{detail.data.detail||"No additional detail recorded."}</p>
          <div>
            <h4 className="mb-2 text-sm font-semibold">Rejected records</h4>
            {detail.data.errors.length===0
              ? <p className="text-muted-foreground">No records were rejected in this run.</p>
              : <ul className="grid gap-2">{detail.data.errors.map((error,index)=><li key={index} className="border border-border px-3 py-2">
                  <span className="font-semibold">{error.reason}</span>
                  <span className="ml-2 font-mono text-[10px] text-muted-foreground">{error.external_id??"—"}</span>
                  {error.detail&&<p className="mt-1 text-muted-foreground">{error.detail}</p>}
                </li>)}</ul>}
          </div>
        </div>}
      </DialogContent>
    </Dialog>

    <p className="mt-8 max-w-3xl text-sm leading-6 text-muted-foreground">
      A connector is labelled Connected only when it authenticated and returned data. Not configured, Planned, Unauthorized, Rate limited and Error states are reported exactly as the adapter observed them, and a failure in one platform never stops the others.
    </p></>;
}
