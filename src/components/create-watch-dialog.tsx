import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "./ui/dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Checkbox } from "./ui/checkbox";
import { useAnalysis } from "@/lib/analysis-context";
import type { Platform } from "@/lib/intelligence-demo";
import { useBackendHealth } from "@/lib/use-backend";
import { api, backendConfigured, type ComponentHealth, type ConnectionTest } from "@/lib/api-client";

/** Honest per-platform connection label; never claims live data. */
function connectionState(platform:Platform,adapters:ComponentHealth[]){
  const match=adapters.find(item=>item.component.toLowerCase().startsWith(platform.toLowerCase()));
  if(match)return match.status;
  return platform==="X"||platform==="Telegram"?"Not configured":"Planned";
}

const LIVE_PLATFORMS:Platform[]=["X","Telegram"];

export function CreateWatchDialog(){
  const [open,setOpen]=useState(false);
  const [name,setName]=useState("AI Safety India");
  const [keywords,setKeywords]=useState("AI safety, policy, standards");
  const [platforms,setPlatforms]=useState<Platform[]>(["X","Telegram"]);
  const [mode,setMode]=useState<"demo"|"live">("demo");
  const [test,setTest]=useState<ConnectionTest|null>(null);
  const [testing,setTesting]=useState(false);
  const [notice,setNotice]=useState("");
  const {createWatch}=useAnalysis();
  const {health}=useBackendHealth();
  const adapters=health?.adapters??[];
  const navigate=useNavigate();

  const livePlatforms=platforms.filter(platform=>LIVE_PLATFORMS.includes(platform));
  const liveAvailable=livePlatforms.some(platform=>connectionState(platform,adapters)==="Connected");

  function toggle(platform:Platform){
    setPlatforms(current=>current.includes(platform)?current.filter(item=>item!==platform):[...current,platform]);
    setTest(null);
  }

  async function runTest(){
    const platform=livePlatforms[0];
    if(!platform)return;
    setTesting(true);
    setNotice("");
    const outcome=await api.testConnector(platform);
    setTest(outcome??{platform,configured:false,authenticated:false,source_reachable:false,status:"Unavailable",identifier:"",last_message_time:null,last_success:null,error:"Backend not reachable. Demo Mode remains available."});
    setTesting(false);
  }

  async function submit(){
    if(!name.trim()||!keywords.trim()||platforms.length===0)return;
    if(mode==="live"){
      setNotice("Creating live Watch…");
      const now=new Date();
      const created=await api.createWatch({
        name:name.trim(),keywords:keywords.trim(),platforms:livePlatforms,
        range_from:new Date(now.getTime()-7*86_400_000).toISOString(),
        range_to:new Date(now.getTime()+30*86_400_000).toISOString(),
        mode:"live",
      });
      if(!created){
        setNotice("Live integrations are not configured. Demo Mode remains available.");
        return;
      }
      const job=await api.ingest(created.id);
      setNotice(job
        ? `Live Watch created. ${job.records_found} record(s) fetched · ${job.records_new} new · ${job.records_duplicate} duplicate · ${job.records_failed} failed.`
        : "Live Watch created. Ingestion could not be started — see Connector Center.");
      return;
    }
    createWatch({name:name.trim(),keywords:keywords.trim(),platforms,range:"01–14 Sep 2026"});
    setOpen(false);
    void navigate({to:"/time-machine"});
  }

  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button variant="outline"><Plus/>Create Watch</Button></DialogTrigger>
    <DialogContent className="max-h-[92vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>Create Watch</DialogTitle>
        <DialogDescription>Demo Mode creates a deterministic seeded analysis. Live Mode collects only from connectors that are actually configured.</DialogDescription>
      </DialogHeader>
      <div className="grid gap-5 py-2">
        <div className="grid gap-2"><Label htmlFor="watch-name">Watch name</Label><Input id="watch-name" value={name} onChange={event=>setName(event.target.value)}/></div>
        <div className="grid gap-2"><Label htmlFor="watch-keywords">Topic / keyword</Label><Input id="watch-keywords" value={keywords} onChange={event=>setKeywords(event.target.value)}/></div>
        <div className="grid gap-2"><Label>Platforms</Label>
          <div className="grid grid-cols-2 gap-3">{(["X","Telegram","Instagram","Facebook"] as Platform[]).map(platform=>
            <label key={platform} className="flex items-center gap-2 border border-border px-3 py-2.5 text-sm">
              <Checkbox checked={platforms.includes(platform)} onCheckedChange={()=>toggle(platform)}/><span>{platform}</span>
              <span className="ml-auto font-mono text-[9px] text-muted-foreground">{connectionState(platform,adapters)}</span>
            </label>)}
          </div>
        </div>
        <div className="grid gap-2"><Label>Data mode</Label>
          <div className="grid grid-cols-2 gap-3">
            {(["demo","live"] as const).map(option=>{
              const disabled=option==="live"&&(!backendConfigured||!liveAvailable);
              return <button key={option} type="button" disabled={disabled} onClick={()=>setMode(option)}
                className={`border px-3 py-2.5 text-left text-sm disabled:cursor-not-allowed disabled:opacity-55 ${mode===option?"border-primary bg-accent text-primary":"border-border"}`}>
                <span className="font-semibold">{option==="demo"?"Demo Mode":"Live Mode"}</span>
                <span className="mt-0.5 block text-[11px] text-muted-foreground">
                  {option==="demo"?"Deterministic seeded dataset":disabled?"No connector configured":"Configured connectors only"}
                </span>
              </button>;
            })}
          </div>
        </div>
        <div className="grid gap-2"><Label htmlFor="watch-range">Date range</Label>
          <Input id="watch-range" readOnly value={mode==="demo"?"01 Sep 2026 — 14 Sep 2026":"Last 7 days — next 30 days (rolling)"}/>
        </div>
        {mode==="live"
          ? <div className="grid gap-3 border-l-2 border-primary bg-accent/40 px-3 py-3 text-xs text-muted-foreground">
              <p><strong className="text-primary">Live Mode.</strong> Credentials stay in the backend environment. This page never receives a token.</p>
              <div className="flex flex-wrap items-center gap-3">
                <Button type="button" variant="outline" size="sm" disabled={testing||livePlatforms.length===0} onClick={()=>void runTest()}>{testing?"Testing…":"Test connection"}</Button>
                {test&&<span className="font-mono text-[10px]">
                  {test.platform}: {test.status} · authenticated {String(test.authenticated)} · source {String(test.source_accessible??test.source_reachable)}
                  {test.source_name?` · ${test.source_name}`:""}{test.error?` · ${test.error}`:""}
                </span>}
              </div>
            </div>
          : <p className="border-l-2 border-primary bg-accent/50 px-3 py-2 text-xs text-muted-foreground"><strong className="text-primary">Demo analysis.</strong> Records come from the seeded DRISHTI dataset — no platform connection is made.</p>}
        {notice&&<p className="border border-border bg-muted/40 px-3 py-2 text-xs text-foreground">{notice}</p>}
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={()=>setOpen(false)}>Close</Button>
        <Button disabled={!name.trim()||!keywords.trim()||platforms.length===0} onClick={()=>void submit()}>
          {mode==="live"?"Create and start ingestion":"Create and open"}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>;
}
