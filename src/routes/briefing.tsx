import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAnalysis } from "@/lib/analysis-context";
import { formatEngagement } from "@/lib/intelligence-demo";

export const Route = createFileRoute("/briefing")({
  head: () => ({ meta: [
    { title: "Narrative Intelligence Brief — DRISHTI" },
    { name: "description", content: "Print-ready narrative intelligence brief for the selected watch and analysis point." },
    { property: "og:title", content: "Narrative Intelligence Brief — DRISHTI" },
    { property: "og:description", content: "Executive summary, narrative evolution, evidence and method notes for the selected watch." },
    { property: "og:type", content: "article" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: Briefing,
});

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="mt-9 break-inside-avoid">
    <h2 className="border-b border-border pb-2 text-sm font-bold uppercase tracking-wide text-primary">{title}</h2>
    <div className="mt-4 space-y-3 text-sm leading-6">{children}</div>
  </section>;
}

function Briefing() {
  const { activeWatch, snapshotIndex } = useAnalysis();
  const snapshot = activeWatch.snapshots[snapshotIndex] ?? activeWatch.snapshots[0];
  if (!snapshot) throw new Error("The selected watch has no timeline snapshots");
  const posts = activeWatch.posts.filter((post) => post.snapshot <= snapshotIndex);
  const accounts = activeWatch.accounts.filter((account) => snapshot.visibleAccounts.includes(account.id));
  const kols = [...accounts].sort((a, b) => b.influence - a.influence).slice(0, 3);
  const trends = snapshot.trends.slice(0, 5);
  const byPlatform = activeWatch.platforms.map((platform) => {
    const group = posts.filter((post) => post.platform === platform);
    const negative = group.filter((post) => post.sentiment === "Negative").length;
    return { platform, records: group.length, negative: group.length ? Math.round((100 * negative) / group.length) : 0 };
  }).filter((row) => row.records > 0);
  const evidence = posts.slice(-6).reverse();
  const handleOf = (id: string) => activeWatch.accounts.find((a) => a.id === id)?.handle ?? id;

  return <article className="mx-auto max-w-4xl">
    <div className="mb-8 flex flex-wrap items-center justify-between gap-3 print:hidden">
      <Button variant="ghost" asChild><Link to="/time-machine"><ArrowLeft/>Back to Time-Machine</Link></Button>
      <Button onClick={() => window.print()}><Printer/>Print or save as PDF</Button>
    </div>

    <header className="border-b-2 border-primary pb-5">
      <div className="text-[11px] font-bold tracking-wide text-muted-foreground">DRISHTI · SOCIAL MEDIA NARRATIVE INTELLIGENCE · SIH 2026 (PS 26152)</div>
      <h1 className="mt-2 text-3xl font-bold">DRISHTI Narrative Intelligence Brief</h1>
      <div className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
        <div><span className="text-muted-foreground">Watch: </span><span className="font-semibold">{activeWatch.name}</span></div>
        <div><span className="text-muted-foreground">Analysis point: </span><span className="font-mono font-semibold">{snapshot.timestamp}</span></div>
        <div><span className="text-muted-foreground">Period: </span>{activeWatch.range}</div>
        <div><span className="text-muted-foreground">Sources: </span>{activeWatch.platforms.join(", ")}</div>
      </div>
      <div className="mt-4 inline-block border border-primary/20 bg-accent px-2.5 py-1 text-xs font-bold text-primary">
        DEMO DATASET · SIMULATED SOCIAL ACTIVITY · NOT LIVE DATA
      </div>
    </header>

    <Section title="Executive summary">
      <p>At {snapshot.timestamp} the watch shows {snapshot.sentiment.negative}% negative, {snapshot.sentiment.neutral}% neutral and {snapshot.sentiment.positive}% positive sentiment across {posts.length} stored records.</p>
      <p>{snapshot.sentiment.annotation}</p>
      <p>{snapshot.summary}</p>
    </Section>

    <Section title="Narrative evolution">
      <ol className="space-y-2">
        {activeWatch.snapshots.slice(0, snapshotIndex + 1).map((item) => <li key={item.id} className="flex gap-3">
          <span className="w-32 shrink-0 font-mono text-xs text-muted-foreground">{item.shortStamp}</span>
          <span><span className="font-semibold">{item.eventLabel || item.phase}</span>{item.summary && item.summary !== item.phase ? ` — ${item.summary}` : ""}</span>
        </li>)}
      </ol>
      <p className="text-xs text-muted-foreground">Observed sequence and temporal association only. Ordering does not establish causation.</p>
    </Section>

    <Section title="Sentiment and emotion">
      <p>Positive {snapshot.sentiment.positive}% · Neutral {snapshot.sentiment.neutral}% · Negative {snapshot.sentiment.negative}% (mean confidence {snapshot.sentiment.confidence}).</p>
      <ul className="grid gap-1 sm:grid-cols-2">
        {Object.entries(snapshot.emotions).map(([emotion, value]) => <li key={emotion}>{emotion}: {value}%</li>)}
      </ul>
    </Section>

    <Section title="Rising narratives">
      <table className="w-full text-left text-sm"><thead><tr className="border-b border-border text-xs uppercase text-muted-foreground"><th className="py-2">Topic</th><th>Mentions</th><th>Previous</th><th>Velocity</th></tr></thead>
        <tbody>{trends.map((trend) => <tr key={trend.topic} className="border-b border-border/60"><td className="py-2 font-medium">{trend.topic}</td><td>{trend.mentions}</td><td>{trend.previousMentions}</td><td>{trend.velocity}%</td></tr>)}</tbody></table>
      <p className="text-xs text-muted-foreground">Velocity = current mentions / max(previous mentions, 1). No topic is described as viral.</p>
    </Section>

    <Section title="Influence and KOL candidates">
      <ul className="space-y-2">{kols.map((account) => <li key={account.id}>
        <span className="font-semibold">{account.handle}</span> · {account.platform} · influence {account.influence} · centrality {account.centrality}
        <div className="text-muted-foreground">KOL CANDIDATE — {account.reason}</div>
      </li>)}</ul>
      <p className="text-xs text-muted-foreground">Candidates are ranked for analyst review. DRISHTI does not confirm influencers and does not attribute causation.</p>
    </Section>

    <Section title="Aggregate audience profile">
      <div className="grid gap-4 sm:grid-cols-2">
        {([["Age cohort", snapshot.demographics.age], ["Region", snapshot.demographics.geography], ["Language", snapshot.demographics.language], ["Professional interest", snapshot.demographics.interests]] as const).map(([label, values]) => <div key={label}>
          <div className="text-xs font-bold uppercase text-muted-foreground">{label}</div>
          <ul>{Object.entries(values).map(([cohort, percent]) => <li key={cohort}>{cohort}: {percent >= 5 ? `${percent}%` : "Cohort too small to report"}</li>)}</ul>
        </div>)}
      </div>
    </Section>

    <Section title="Cross-platform activity">
      <ul>{byPlatform.map((row) => <li key={row.platform}>{row.platform}: {row.records} records, {row.negative}% negative</li>)}</ul>
    </Section>

    <Section title="Supporting evidence">
      <ol className="space-y-3">{evidence.map((post, index) => <li key={post.id} className="border-l-2 border-primary/30 pl-3">
        <div className="text-xs text-muted-foreground">[Evidence {String(index + 1).padStart(2, "0")}] {post.platform} · {handleOf(post.accountId)} · {post.timestamp} · {post.sentiment} ({post.confidence}) · {formatEngagement(post.engagement)} engagement</div>
        <div>{post.text}</div>
      </li>)}</ol>
    </Section>

    <Section title="Method and privacy notes">
      <ul className="list-disc space-y-1 pl-5">
        <li>One shared clock drives sentiment, trends, network, demographics and evidence; no panel is computed from a different window.</li>
        <li>Sentiment uses an open-source polarity model with lexicon emotion indicators; unlabelled records are reported, never inferred.</li>
        <li>Network relationships come only from observed replies, mentions, reposts, forwards and references.</li>
        <li>Demographics are aggregate and anonymized; cohorts below the reporting threshold are suppressed.</li>
        <li>This brief is generated from the DRISHTI demo dataset. It is a student/team-developed SIH prototype, not an official government system.</li>
      </ul>
    </Section>
  </article>;
}
