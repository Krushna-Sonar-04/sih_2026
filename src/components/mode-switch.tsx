import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, backendConfigured, type ConnectorState } from "@/lib/api-client";
import { useAnalysis } from "@/lib/analysis-context";

/**
 * Explicit DEMO / LIVE selector for the active Watch.
 *
 * Live can only be selected when a connector is actually configured and the
 * backend accepts the change, so the workspace never displays Live while only
 * demo records exist.
 */
export function ModeSwitch({connectors}:{connectors:ConnectorState[]}){
  const {activeWatch}=useAnalysis();
  const client=useQueryClient();
  const [mode,setMode]=useState<"demo"|"live">("demo");
  const [notice,setNotice]=useState("");
  const configured=connectors.some(state=>state.configured);
  const connected=connectors.some(state=>state.status==="Connected");

  async function choose(next:"demo"|"live"){
    setNotice("");
    if(next==="live"){
      if(!backendConfigured||!configured){
        setNotice("Live integrations are not configured. Demo Mode remains available.");
        return;
      }
      const updated=await api.updateWatch(activeWatch.id,{mode:"live"});
      if(!updated){
        setNotice("Live unavailable. Demo Mode is available.");
        return;
      }
      if(!connected)setNotice("Connector configured but no source returned data yet.");
      setMode("live");
      void client.invalidateQueries({queryKey:["drishti"]});
      return;
    }
    await api.updateWatch(activeWatch.id,{mode:"demo"});
    setMode("demo");
    void client.invalidateQueries({queryKey:["drishti"]});
  }

  return <div className="flex flex-col items-end gap-1.5">
    <div className="flex items-center gap-0 border border-border" role="group" aria-label="Data mode">
      {(["demo","live"] as const).map(option=>
        <button key={option} type="button" onClick={()=>void choose(option)}
          className={`px-3 py-1.5 text-[11px] font-bold uppercase tracking-wide ${mode===option?"bg-primary text-primary-foreground":"text-muted-foreground hover:bg-accent"}`}>
          {option==="demo"?"Demo mode":"Live mode"}
        </button>)}
    </div>
    {notice&&<span className="max-w-72 text-right text-[11px] text-muted-foreground">{notice}</span>}
  </div>;
}
