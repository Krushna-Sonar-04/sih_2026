import { useState } from "react";
import { MessageSquareText, Send } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";
import { useAnalysis } from "@/lib/analysis-context";
import { useBackendHealth } from "@/lib/use-backend";
import { api } from "@/lib/api-client";
import { askLocalAssistant, type LocalCitation } from "@/lib/local-assistant";

const SUGGESTIONS=["Why did sentiment shift here?","What narrative is rising?","Who is driving this narrative?","How did this narrative spread?","What changed across X and Telegram?","Show evidence for this spike."];

export function AssistantPanel(){
  const {activeWatch,snapshotIndex,selectedTopic,selectedAccountId}=useAnalysis();
  const {connected}=useBackendHealth();
  const [question,setQuestion]=useState("");
  const [busy,setBusy]=useState(false);
  const [answer,setAnswer]=useState<{text:string;grounded:boolean;provider:string;citations:LocalCitation[]}|null>(null);
  const [open,setOpen]=useState<LocalCitation|null>(null);
  const snapshot=activeWatch.snapshots[snapshotIndex]??activeWatch.snapshots[0];

  async function ask(text:string){
    if(!text.trim()||!snapshot)return;
    setBusy(true);setQuestion(text);
    let result:{text:string;grounded:boolean;provider:string;citations:LocalCitation[]}|null=null;
    if(connected){
      const remote=await api.ask(activeWatch.id,snapshotIndex,{question:text,topic:selectedTopic,account_id:selectedAccountId});
      if(remote) result={text:remote.answer,grounded:remote.grounded,provider:remote.provider,
        citations:remote.citations.map(c=>({ref:c.ref,postId:c.evidence_id,excerpt:c.excerpt,platform:c.platform,handle:c.account_username,timestamp:new Date(c.event_time).toUTCString().slice(5,22)}))};
    }
    if(!result){
      const local=askLocalAssistant(text,activeWatch,snapshot,snapshotIndex,selectedTopic,selectedAccountId);
      result={text:local.answer,grounded:local.grounded,provider:local.provider,citations:local.citations};
    }
    setAnswer(result);setBusy(false);
  }

  return <section className="border-t-2 border-primary/25 bg-card px-5 py-5">
    <div className="mb-5 flex items-center justify-between gap-4">
      <h2 className="flex items-center gap-2 text-lg font-semibold"><MessageSquareText className="size-4 text-primary"/>Analyst Assistant</h2>
      <span className="font-mono text-[10px] text-muted-foreground">{connected?"Backend grounded":"Local grounded"} · {snapshot?.shortStamp}</span>
    </div>
    <form className="flex gap-2" onSubmit={event=>{event.preventDefault();void ask(question)}}>
      <Input value={question} onChange={event=>setQuestion(event.target.value)} placeholder="Ask about the selected analysis point" aria-label="Ask the analyst assistant"/>
      <Button type="submit" size="icon" disabled={busy||!question.trim()} aria-label="Send question"><Send/></Button>
    </form>
    <div className="mt-3 flex flex-wrap gap-2">{SUGGESTIONS.map(item=><button key={item} type="button" onClick={()=>void ask(item)} className="border border-border px-2.5 py-1 text-[10px] text-muted-foreground transition hover:border-primary/40 hover:text-primary">{item}</button>)}</div>
    {busy&&<p className="mt-5 text-xs text-muted-foreground">Retrieving evidence for the selected watch and time window…</p>}
    {answer&&!busy&&<div className="mt-5 border-l-2 border-primary bg-accent/40 px-4 py-4">
      <p className="whitespace-pre-line text-sm leading-6">{answer.text}</p>
      {answer.citations.length>0&&<div className="mt-4 border-t border-primary/15 pt-3">
        <div className="text-[10px] font-semibold text-muted-foreground">Citations — open a record to inspect the stored evidence</div>
        <div className="mt-2 flex flex-wrap gap-2">{answer.citations.map(citation=><button key={citation.ref} onClick={()=>setOpen(citation)} className="border border-primary/25 bg-card px-2 py-1 text-[10px] font-semibold text-primary hover:bg-accent">{citation.ref}</button>)}</div>
      </div>}
      <p className="mt-3 text-[10px] text-muted-foreground">{answer.grounded?"Answer restricted to records in the selected watch and time window.":"No supporting records were found for this question."} Response source: {answer.provider}.</p>
    </div>}
    <Dialog open={Boolean(open)} onOpenChange={value=>{if(!value)setOpen(null)}}>
      <DialogContent><DialogHeader><DialogTitle>{open?.ref}</DialogTitle><DialogDescription>Cited record from the selected analysis window.</DialogDescription></DialogHeader>
        {open&&<div className="space-y-4"><div className="grid grid-cols-3 gap-3 border-y border-border py-3 text-xs">
          <div><div className="text-[10px] font-semibold text-muted-foreground">Platform</div><div className="mt-1 font-medium">{open.platform}</div></div>
          <div><div className="text-[10px] font-semibold text-muted-foreground">Account</div><div className="mt-1 font-medium">{open.handle}</div></div>
          <div><div className="text-[10px] font-semibold text-muted-foreground">Timestamp</div><div className="mt-1 font-medium">{open.timestamp}</div></div>
        </div><p className="text-sm leading-7">{open.excerpt}</p></div>}
      </DialogContent>
    </Dialog>
  </section>;
}
