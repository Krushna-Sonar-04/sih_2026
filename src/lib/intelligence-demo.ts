export type Platform = "X" | "Telegram" | "Instagram" | "Facebook";
export type Sentiment = "Positive" | "Neutral" | "Negative";
export type EventKind = "emergence" | "sentiment" | "trend" | "cross-platform" | "influence" | "peak";

export interface DemoAccount { id:string; handle:string; platform:Platform; community:string; influence:number; centrality:number; firstObserved:string; peakActivity:string; reason:string; }
export interface DemoPost { id:string; snapshot:number; accountId:string; platform:Platform; timestamp:string; text:string; sentiment:Sentiment; confidence:number; engagement:number; topic:string; }
export interface Trend { topic:string; mentions:number; previousMentions:number; velocity:number; spark:number[]; }
export interface Demographics { age:Record<string,number>; geography:Record<string,number>; language:Record<string,number>; interests:Record<string,number>; }
export interface Snapshot { id:number; timestamp:string; shortStamp:string; phase:string; event:EventKind|undefined; eventLabel:string; sentiment:{positive:number;neutral:number;negative:number;confidence:number;change:number;annotation:string}; emotions:Record<string,number>; trends:Trend[]; visibleAccounts:string[]; visibleEdges:string[]; demographics:Demographics; summary:string; }
export interface DemoEdge { id:string; source:string; target:string; kind:"reply"|"mention"|"repost"|"forward"|"cross-platform"; strength:number; firstSnapshot:number; }
export interface DemoWatch { id:string; name:string; keywords:string; platforms:Platform[]; range:string; status:string; snapshots:Snapshot[]; accounts:DemoAccount[]; edges:DemoEdge[]; posts:DemoPost[]; }
export interface AnalysisTarget { watchId:string; snapshot:number; topic?:string|undefined; accountId?:string|undefined; postId?:string|undefined; }

const accounts: DemoAccount[] = [
 {id:"aarav",handle:"@AaravIntel",platform:"X",community:"Policy analysts",influence:92,centrality:.88,firstObserved:"03 Sep · 09:10",peakActivity:"10 Sep · 17:20",reason:"High network centrality combined with repeated amplification across connected accounts."},
 {id:"policy",handle:"@PolicyWatch",platform:"X",community:"Policy media",influence:81,centrality:.76,firstObserved:"01 Sep · 10:00",peakActivity:"12 Sep · 12:45",reason:"Consistent bridge activity between policy and technology communities."},
 {id:"rights",handle:"@DataRightsIndia",platform:"X",community:"Digital rights",influence:86,centrality:.82,firstObserved:"05 Sep · 16:20",peakActivity:"08 Sep · 14:30",reason:"Rapid cross-community amplification around privacy safeguards."},
 {id:"tech",handle:"@TechPolicyHub",platform:"Telegram",community:"Technology policy",influence:74,centrality:.69,firstObserved:"02 Sep · 11:40",peakActivity:"09 Sep · 18:05",reason:"Early source of discussion later referenced across X."},
 {id:"open",handle:"@OpenAIObserver",platform:"X",community:"Open technology",influence:67,centrality:.58,firstObserved:"06 Sep · 08:15",peakActivity:"11 Sep · 13:15",reason:"Repeated topical participation across open-source AI discussions."},
 {id:"digital",handle:"@DigitalIndiaForum",platform:"Telegram",community:"Digital governance",influence:78,centrality:.72,firstObserved:"01 Sep · 15:25",peakActivity:"12 Sep · 18:10",reason:"Connects governance channels with wider technology-policy discussion."},
 {id:"jobs",handle:"@FutureSkillsIN",platform:"X",community:"Workforce",influence:59,centrality:.44,firstObserved:"09 Sep · 09:40",peakActivity:"13 Sep · 15:30",reason:"Focused amplification within the employment and skills community."},
 {id:"civic",handle:"@CivicStack",platform:"Telegram",community:"Civic technology",influence:63,centrality:.51,firstObserved:"07 Sep · 19:20",peakActivity:"10 Sep · 10:50",reason:"Cross-platform references connect civic technology conversations."},
];

const edges: DemoEdge[] = [
 {id:"e1",source:"tech",target:"policy",kind:"cross-platform",strength:62,firstSnapshot:1},{id:"e2",source:"policy",target:"aarav",kind:"mention",strength:70,firstSnapshot:2},
 {id:"e3",source:"tech",target:"rights",kind:"cross-platform",strength:84,firstSnapshot:3},{id:"e4",source:"rights",target:"aarav",kind:"repost",strength:91,firstSnapshot:3},
 {id:"e5",source:"aarav",target:"digital",kind:"mention",strength:73,firstSnapshot:4},{id:"e6",source:"civic",target:"rights",kind:"forward",strength:67,firstSnapshot:4},
 {id:"e7",source:"policy",target:"open",kind:"reply",strength:58,firstSnapshot:5},{id:"e8",source:"aarav",target:"jobs",kind:"mention",strength:52,firstSnapshot:6},
 {id:"e9",source:"digital",target:"jobs",kind:"cross-platform",strength:64,firstSnapshot:6},{id:"e10",source:"open",target:"digital",kind:"repost",strength:61,firstSnapshot:7},
];

const snapshotSeeds = [
 ["01 SEP 2026 · 09:00","01 Sep · 09:00","Low activity",35,53,12,0,"Monitoring baseline"],
 ["04 SEP 2026 · 18:00","04 Sep · 18:00","Early discussion",34,50,16,4,"Narrative emergence"],
 ["06 SEP 2026 · 11:20","06 Sep · 11:20","Discussion accelerating",31,47,22,6,"Discussion velocity increasing"],
 ["08 SEP 2026 · 14:30","08 Sep · 14:30","Narrative ignition",21,37,42,21,"Sentiment shift detected"],
 ["09 SEP 2026 · 18:05","09 Sep · 18:05","Cross-platform acceleration",20,35,45,3,"Telegram discussion amplified on X"],
 ["10 SEP 2026 · 16:40","10 Sep · 16:40","Influence expansion",19,33,48,3,"High-centrality accounts expanding reach"],
 ["12 SEP 2026 · 18:10","12 Sep · 18:10","Peak activity",22,29,49,1,"Narrative reached peak activity"],
 ["14 SEP 2026 · 20:00","14 Sep · 20:00","Sustained discussion",25,31,44,-5,"Activity stabilizing after peak"],
] as const;
const eventKinds:(EventKind|undefined)[]=[undefined,"emergence","trend","sentiment","cross-platform","influence","peak",undefined];
const trendOrders = [
 [["AI Regulation",32,28],["Government Policy",24,22],["Open Source AI",18,17],["Data Privacy",12,11],["AI Jobs",8,8]],
 [["AI Regulation",48,32],["Government Policy",31,24],["Data Privacy",20,12],["Open Source AI",19,18],["AI Jobs",11,8]],
 [["AI Regulation",71,48],["Data Privacy",38,20],["Government Policy",39,31],["AI Jobs",18,11],["Open Source AI",23,19]],
 [["Data Privacy",61,38],["AI Regulation",76,71],["Government Policy",46,39],["AI Jobs",25,18],["Open Source AI",28,23]],
 [["Data Privacy",83,61],["AI Regulation",91,76],["Government Policy",57,46],["Open Source AI",35,28],["AI Jobs",29,25]],
 [["Government Policy",74,46],["AI Regulation",104,91],["Data Privacy",88,83],["AI Jobs",42,29],["Open Source AI",39,35]],
 [["AI Regulation",132,104],["Government Policy",96,74],["Data Privacy",101,88],["AI Jobs",53,42],["Open Source AI",47,39]],
 [["Government Policy",99,96],["AI Regulation",128,132],["Data Privacy",94,101],["Open Source AI",52,47],["AI Jobs",55,53]],
] as const;
const visible=[2,3,4,5,6,7,8,8];
function demographics(i:number):Demographics{return {age:{"18–24":34+i,"25–34":36-i,"35–44":20,"45+":10},geography:{North:31+i,West:29,South:25-i,East:15},language:{English:45-i,Hindi:29+i,Marathi:14,"Mixed / Code-Mixed":12},interests:{Technology:39-i,Policy:26+i,Students:22,Business:13}}}
const snapshots:Snapshot[]=snapshotSeeds.map((s,i)=>{const count=visible[i]??2;const trends=trendOrders[i]??trendOrders[0];const eventLabel=i===3?"Narrative ignition · Sentiment shift":i===4?"Cross-platform acceleration":i===5?"Influence activity":i===6?"Peak activity":s[7];return {id:i,timestamp:s[0],shortStamp:s[1],phase:s[2],event:eventKinds[i],eventLabel,sentiment:{positive:s[3],neutral:s[4],negative:s[5],confidence:Number((.78+i*.015).toFixed(2)),change:s[6],annotation:s[7]},emotions:{Support:s[3],Opposition:s[5],Anxiety:Math.min(48,13+i*5),Excitement:Math.max(12,27-i*2),Sarcasm:8+i},trends:trends.map(([topic,mentions,previousMentions])=>({topic,mentions,previousMentions,velocity:Math.round(((mentions-previousMentions)/Math.max(previousMentions,1))*100),spark:[Math.max(3,previousMentions-8),previousMentions,Math.round((previousMentions+mentions)/2),mentions]})).sort((a,b)=>b.mentions-a.mentions),visibleAccounts:accounts.slice(0,count).map(a=>a.id),visibleEdges:edges.filter(e=>e.firstSnapshot<=i).map(e=>e.id),demographics:demographics(i),summary:i===3?"Privacy safeguards became the bridge from policy discussion to negative sentiment.":i===4?"Telegram-origin discussion crossed into X and attracted new amplifiers.":i===6?"Policy discussion reached its highest observed volume in the demo window.":s[7]}});

const postTexts = [
 ["policy","X","AI Regulation","A practical AI framework needs clear implementation milestones, not only broad principles.","Neutral",280],
 ["tech","Telegram","AI Regulation","Early discussion: members are comparing the draft with existing technology policy frameworks.","Neutral",190],
 ["digital","Telegram","Government Policy","The consultation window should include startups, researchers and citizen groups.","Positive",430],
 ["aarav","X","AI Regulation","Regulatory clarity can support innovation when safeguards and review mechanisms are explicit.","Positive",1100],
 ["rights","X","Data Privacy","Privacy safeguards cannot remain an afterthought in the implementation timeline.","Negative",4800],
 ["tech","Telegram","Data Privacy","Data-retention language is now the central concern across several policy channels.","Negative",1600],
 ["aarav","X","Data Privacy","The discussion has shifted: implementation detail now matters more than headline intent.","Negative",3900],
 ["civic","Telegram","Data Privacy","Forwarded references show the privacy discussion moving from specialist groups to broader civic channels.","Negative",2200],
 ["policy","X","Government Policy","A phased implementation plan could address industry readiness while preserving accountability.","Neutral",3100],
 ["digital","Telegram","Government Policy","Government policy framing is becoming the dominant response to the privacy debate.","Neutral",1800],
 ["open","X","Open Source AI","Open-source developers are asking whether compliance expectations will differ by model access.","Neutral",1700],
 ["aarav","X","Government Policy","Cross-community references indicate policy interpretation is now driving amplification.","Negative",5200],
 ["jobs","X","AI Jobs","Skills and employment effects are entering the discussion as reach expands.","Neutral",1400],
 ["rights","X","Data Privacy","Peak discussion still centres on consent, retention and independent review.","Negative",6100],
 ["digital","Telegram","AI Regulation","Activity is stabilizing, but implementation questions remain unresolved.","Neutral",2400],
] as const;
const postSnapshots=[0,0,1,1,3,3,3,4,4,4,5,5,6,6,7];
const posts:DemoPost[]=postTexts.map((p,i)=>{const snapshot=postSnapshots[i]??0;return {id:`post-${i+1}`,snapshot,accountId:p[0],platform:p[1] as Platform,timestamp:snapshots[snapshot]?.shortStamp??"01 Sep · 09:00",text:p[3],sentiment:p[4] as Sentiment,confidence:Number((.79+(i%6)*.025).toFixed(2)),engagement:p[5],topic:p[2]}});

const watchSeeds=[
 {id:"ai-regulation-india",name:"AI Regulation India",keywords:"AI Act, regulation, privacy",platforms:["X","Telegram"] as Platform[],range:"01–14 Sep 2026",status:"Rising"},
 {id:"data-privacy-discussion",name:"Data Privacy Discussion",keywords:"data rights, consent, retention",platforms:["X","Telegram"] as Platform[],range:"03–14 Sep 2026",status:"Accelerating"},
 {id:"digital-public-infrastructure",name:"Digital Public Infrastructure",keywords:"DPI, India Stack, governance",platforms:["X"] as Platform[],range:"01–14 Sep 2026",status:"Stable"},
 {id:"emerging-technology-policy",name:"Emerging Technology Policy",keywords:"deeptech, policy, innovation",platforms:["Telegram"] as Platform[],range:"05–14 Sep 2026",status:"Monitoring"},
];
function adaptWatch(seed:typeof watchSeeds[number],offset:number):DemoWatch { const topic=seed.name; return {...seed,snapshots:snapshots.map((s,i)=>({...s,sentiment:{...s.sentiment,positive:Math.max(10,s.sentiment.positive+offset),neutral:s.sentiment.neutral,negative:Math.max(8,s.sentiment.negative-offset)},trends:s.trends.map((t,j)=>j===0?{...t,topic}:t),summary:offset===0?s.summary:`${topic} is ${s.phase.toLowerCase()} across the selected demo sources.`})),accounts,edges,posts:posts.map(p=>({...p,topic:p.topic==="AI Regulation"?topic:p.topic}))}; }
export const initialWatches:DemoWatch[]=watchSeeds.map((w,i)=>adaptWatch(w,i*3));
export const dashboardAlerts=[
 {id:"alert-sentiment",watchId:"ai-regulation-india",snapshot:3,type:"Sentiment shift",detail:"Negative sentiment increased around policy implementation discussion.",severity:"High"},
 {id:"alert-trend",watchId:"ai-regulation-india",snapshot:3,topic:"Data Privacy",type:"Rising narrative",detail:"Data Privacy accelerated across monitored platforms.",severity:"Rising"},
 {id:"alert-influence",watchId:"ai-regulation-india",snapshot:5,accountId:"aarav",type:"Influence activity",detail:"A high-centrality account amplified discussion across connected communities.",severity:"Medium"},
 {id:"alert-cross",watchId:"ai-regulation-india",snapshot:4,topic:"Data Privacy",type:"Cross-platform signal",detail:"Telegram-to-X references increased significantly.",severity:"Signal"},
] as const;
export const historyEntries=[
 {id:"h1",date:"14 Sep 2026",watchId:"ai-regulation-india",snapshot:6,event:"Peak activity review",analyst:"Analyst Sonar",status:"Reviewed"},
 {id:"h2",date:"12 Sep 2026",watchId:"ai-regulation-india",snapshot:6,event:"Network expansion",analyst:"Analyst Sonar",status:"Saved",accountId:"aarav"},
 {id:"h3",date:"08 Sep 2026",watchId:"data-privacy-discussion",snapshot:3,event:"Sentiment shift",analyst:"Meera K.",status:"Reviewed",topic:"Data Privacy"},
 {id:"h4",date:"06 Sep 2026",watchId:"digital-public-infrastructure",snapshot:2,event:"Narrative emergence",analyst:"Rajeev N.",status:"Archived"},
] as const;
export function createSeededWatch(name:string,keywords:string,platforms:Platform[],range:string):DemoWatch { const id=`demo-${name.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"")||"watch"}`; return adaptWatch({id,name,keywords,platforms,range,status:"Demo analysis"},2); }
export function formatEngagement(value:number){return value>=1000?`${(value/1000).toFixed(1)}K`:String(value)}
