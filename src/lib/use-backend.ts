import { useQuery } from "@tanstack/react-query";
import { api, backendConfigured, type SystemHealth } from "./api-client";

/** Backend connection state. `connected` false keeps the app in Demo Mode. */
export function useBackendHealth(){
  const query=useQuery<SystemHealth|null>({
    queryKey:["drishti","system-health"],
    queryFn:()=>api.health(),
    enabled:backendConfigured,
    refetchInterval:60_000,
    retry:false,
    staleTime:30_000,
  });
  const health=query.data ?? null;
  return {
    configured:backendConfigured,
    connected:Boolean(health),
    health,
    mode:(health?.mode==="live"?"LIVE MODE":"DEMO MODE") as "LIVE MODE"|"DEMO MODE",
    message:health?.message ?? "Live integrations are not configured. Demo Mode remains available.",
    isLoading:query.isLoading,
  };
}
