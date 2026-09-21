import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "./ui/button";
import { api } from "@/lib/api-client";
import { useBackendHealth } from "@/lib/use-backend";
import { useAnalysis } from "@/lib/analysis-context";

/** Refreshes configured connectors, or the deterministic demo snapshot when none are configured. */
export function RefreshDataButton(){
  const {activeWatch}=useAnalysis();
  const {connected}=useBackendHealth();
  const [busy,setBusy]=useState(false);
  const [status,setStatus]=useState<string|null>(null);

  async function run(){
    setBusy(true);
    setStatus("Refreshing data…");
    if(connected){
      const job=await api.ingest(activeWatch.id);
      if(job){
        const sources=job.sources.map(source=>`${source.platform}: ${source.status}`).join(", ");
        setStatus(
          `Last ingestion ${new Date(job.completed_at).toUTCString().slice(17,22)} UTC · `+
          `${job.records_found} records fetched · ${job.records_new} new · ${job.records_duplicate} duplicates`+
          `${job.records_failed?` · ${job.records_failed} rejected`:""} · ${sources}`
        );
      }else setStatus("Live source unavailable. Showing the last successful snapshot.");
    }else{
      await new Promise(resolve=>setTimeout(resolve,400));
      setStatus(`Demo snapshot refreshed ${new Date().toUTCString().slice(17,22)} UTC · ${activeWatch.posts.length} demo records · ${activeWatch.platforms.join(", ")} (Demo dataset)`);
    }
    setBusy(false);
  }

  return <div className="flex flex-wrap items-center gap-3">
    <Button variant="outline" size="sm" disabled={busy} onClick={()=>void run()}><RefreshCw className={busy?"animate-spin":""}/>Refresh Data</Button>
    {status&&<span className="font-mono text-[10px] text-muted-foreground">{status}</span>}
  </div>;
}
