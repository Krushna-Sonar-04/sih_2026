import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { api, backendConfigured } from "@/lib/api-client";
import { useAnalysis } from "@/lib/analysis-context";

function stamp(value:string|null){ return value?new Date(value).toUTCString().slice(5,22)+" UTC":"—" }

/**
 * Observed cross-platform sequence for the selected Watch and timeline point.
 * Rendered only when stored records on more than one platform support it, and
 * worded as correlation — adjacency in time is never reported as causation.
 */
export function NarrativeMovement(){
  const {activeWatch,snapshotIndex}=useAnalysis();
  const {data}=useQuery({
    queryKey:["drishti","timeline",activeWatch.id,snapshotIndex],
    queryFn:()=>api.timeline(activeWatch.id,snapshotIndex),
    enabled:backendConfigured,
    retry:false,
  });
  const steps=data?.narrative_movement??[];
  const notes=data?.notes??{};
  if(steps.length===0&&!notes.network&&!notes.trends)return null;

  return <section className="mb-10 border-t-2 border-primary/25 bg-card">
    <div className="flex flex-wrap items-center gap-3 border-b border-border px-5 py-5">
      <h2 className="text-lg font-semibold">Narrative movement</h2>
      <span className="text-xs text-muted-foreground">Observed sequence across platforms · correlation, not causation</span>
      <span className="ml-auto border border-border px-2 py-1 font-mono text-[10px] uppercase text-muted-foreground">{data?.mode==="live"?"Live records":"Demo dataset"}</span>
    </div>
    {steps.length>0&&<ol className="flex flex-wrap items-stretch gap-3 px-5 py-5">
      {steps.map((step,index)=><li key={`${step.stage}-${step.platform}-${index}`} className="flex items-stretch gap-3">
        <div className="min-w-56 max-w-72 border border-border bg-muted/20 px-4 py-3">
          <div className="text-[10px] font-bold uppercase tracking-wide text-primary">{step.stage}</div>
          <div className="mt-1 text-sm font-semibold">{step.platform}</div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{step.detail}</p>
          <div className="mt-2 font-mono text-[10px] text-muted-foreground">{stamp(step.event_time)}</div>
        </div>
        {index<steps.length-1&&<ArrowRight className="size-4 self-center text-muted-foreground"/>}
      </li>)}
    </ol>}
    {(notes.network||notes.trends)&&<div className="border-t border-border px-5 py-4 text-xs text-muted-foreground">
      {notes.network&&<p>{notes.network}</p>}
      {notes.trends&&<p className="mt-1">{notes.trends}</p>}
    </div>}
  </section>;
}
