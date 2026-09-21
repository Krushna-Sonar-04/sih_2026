import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { api, backendConfigured } from "@/lib/api-client";
import { useAnalysis } from "@/lib/analysis-context";

/** Compact provenance strip: which sources, which mode, when data last arrived. */
export function DataProvenance(){
  const {activeWatch}=useAnalysis();
  const {data}=useQuery({
    queryKey:["drishti","provenance",activeWatch.id],
    queryFn:()=>api.provenance(activeWatch.id),
    enabled:backendConfigured,
    retry:false,
    refetchInterval:60_000,
  });
  const sources=data?.sources?.length
    ? data.sources.map(source=>`${source.platform} · ${source.status}`).join("   ")
    : activeWatch.platforms.map(platform=>`${platform} · Demo`).join("   ");
  const mode=data?.mode==="live"?"Live":"Demo";
  const freshness=data?.freshness??"Demo snapshot";
  const records=data?.records??activeWatch.posts.length;

  return <section className="mb-8 flex flex-wrap items-center gap-x-8 gap-y-3 border-y border-border bg-muted/25 px-5 py-3.5 text-xs text-muted-foreground" aria-label="Data provenance">
    <span className="font-semibold uppercase tracking-wide text-foreground">Data provenance</span>
    <span><span className="font-semibold text-foreground">Sources:</span> {sources}</span>
    <span><span className="font-semibold text-foreground">Mode:</span> {mode}</span>
    <span><span className="font-semibold text-foreground">Last updated:</span> {freshness}</span>
    <span><span className="font-semibold text-foreground">Records:</span> {records}</span>
    <Link to="/connectors" className="ml-auto font-semibold text-primary hover:underline">Connector Center</Link>
  </section>;
}
