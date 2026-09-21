/**
 * Deterministic local analyst assistant.
 *
 * Used when the backend is unreachable. It answers only from the demo records
 * already on screen and refuses when nothing supports the question, mirroring
 * the backend's cite-or-refuse contract.
 */
import type { DemoAccount, DemoPost, DemoWatch, Snapshot } from "./intelligence-demo";

export const INSUFFICIENT="Insufficient evidence in the selected data to answer this question.";
const ANALYTICAL=["sentiment","shift","narrative","trend","rising","who","driving","influence","kol","spread","cross","platform","telegram","evidence","spike","change","changed","demographic","moment","timeline","activity","account"];
const STOP=new Set(["the","a","an","is","are","did","why","what","who","how","this","that","here","in","on","of","and","to","for","show"]);

export interface LocalCitation { ref:string; postId:string; excerpt:string; platform:string; handle:string; timestamp:string }
export interface LocalAnswer { answer:string; citations:LocalCitation[]; grounded:boolean; provider:string }

function tokens(text:string){return new Set(text.toLowerCase().match(/[a-z]{3,}/g)?.filter(word=>!STOP.has(word))??[])}

export function askLocalAssistant(
  question:string, watch:DemoWatch, snapshot:Snapshot, snapshotIndex:number,
  topic:string|undefined, accountId:string|undefined,
):LocalAnswer{
  const q=question.toLowerCase();
  const questionTokens=tokens(question);
  const available=watch.posts.filter(post=>post.snapshot<=snapshotIndex
    &&(!topic||post.topic===topic)&&(!accountId||post.accountId===accountId));
  const analytical=ANALYTICAL.some(term=>q.includes(term));
  const overlap=available.some(post=>[...tokens(`${post.text} ${post.topic}`)].some(word=>questionTokens.has(word)));
  if(!available.length||(!analytical&&!overlap)) return {answer:INSUFFICIENT,citations:[],grounded:false,provider:"local-deterministic"};

  const ranked=[...available].sort((a,b)=>{
    const score=(post:DemoPost)=>[...tokens(post.text)].filter(word=>questionTokens.has(word)).length*2+post.snapshot+post.engagement/5000;
    return score(b)-score(a);
  }).slice(0,4);
  const citations=ranked.map((post,index)=>({
    ref:`Evidence ${String(index+1).padStart(2,"0")}`,postId:post.id,excerpt:post.text,
    platform:post.platform,handle:watch.accounts.find(a=>a.id===post.accountId)?.handle??post.accountId,timestamp:post.timestamp,
  }));

  const top=snapshot.trends[0];
  const kol=watch.accounts.filter(a=>snapshot.visibleAccounts.includes(a.id)).sort((a,b)=>b.influence-a.influence)[0] as DemoAccount|undefined;
  const platformCounts=available.reduce<Record<string,number>>((acc,post)=>({...acc,[post.platform]:(acc[post.platform]??0)+1}),{});
  let answer:string;
  if(q.includes("who")||q.includes("driving")||q.includes("kol")||q.includes("influence")){
    answer=kol?`${kol.handle} is the leading KOL candidate at ${snapshot.shortStamp} (influence ${kol.influence}, centrality ${kol.centrality.toFixed(2)}, ${kol.platform}). ${kol.reason} Indicative only — not a verified influencer identification.`:INSUFFICIENT;
  }else if(q.includes("spread")||q.includes("cross")||q.includes("platform")||q.includes("telegram")){
    answer=`Cross-platform position at ${snapshot.shortStamp} — ${Object.entries(platformCounts).map(([p,c])=>`${p}: ${c} records`).join("; ")}. Telegram discussion precedes X amplification, followed by network expansion and the sentiment change.`;
  }else if(q.includes("rising")||q.includes("narrative")||q.includes("trend")){
    answer=top?`'${top.topic}' leads the ranking at ${snapshot.shortStamp} with ${top.mentions} mentions against ${top.previousMentions} in the previous interval (velocity ${top.velocity>=0?"+":""}${top.velocity}%).`:INSUFFICIENT;
  }else if(q.includes("sentiment")||q.includes("shift")||q.includes("why")){
    answer=`At ${snapshot.shortStamp} the distribution is ${snapshot.sentiment.positive}% positive / ${snapshot.sentiment.neutral}% neutral / ${snapshot.sentiment.negative}% negative. ${snapshot.sentiment.annotation} Change compared with the previous analysis interval, concentrated in the '${top?.topic??"leading"}' narrative.`;
  }else{
    answer=`${available.length} records support the current reading at ${snapshot.shortStamp}. ${snapshot.summary}`;
  }
  if(answer===INSUFFICIENT) return {answer,citations:[],grounded:false,provider:"local-deterministic"};
  return {answer:`${answer}\n\nSources: ${citations.map(c=>c.ref).join(", ")}`,citations,grounded:true,provider:"local-deterministic"};
}
