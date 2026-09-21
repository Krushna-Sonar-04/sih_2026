/**
 * Client for the DRISHTI FastAPI backend.
 *
 * The base URL comes from VITE_API_BASE_URL (VITE_DRISHTI_API_URL is accepted
 * as a legacy alias). When running locally without either variable set, the
 * client assumes the standard local backend at http://localhost:8000.
 * No Lovable or hosted URL is ever hard-coded. When the backend is unset or
 * unreachable every call resolves to null and the application falls back to
 * its deterministic demo engine, so the prototype never breaks.
 *
 * No credential is ever held here: tokens live only in the backend environment.
 */
const env = import.meta.env as Record<string, string | undefined>;
const configured = env["VITE_API_BASE_URL"] ?? env["VITE_DRISHTI_API_URL"] ?? "";
const localDefault =
  typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname)
    ? "http://localhost:8000"
    : "";
export const API_BASE = (configured || localDefault).replace(/\/$/, "");
export const backendConfigured = API_BASE.length > 0;

export interface ComponentHealth { component:string; status:string; detail:string; last_operation?:string|null; record_count?:number|null }
export interface IngestionSummary { last_successful_run:string|null; records_processed:number; records_rejected:number; duplicates:number; current_job:string }
export interface ConnectorState { platform:string; status:string; detail:string; configured:boolean; enabled:boolean; schedule:string; identifier:string; last_ingestion:string|null; last_success:string|null; next_ingestion:string|null; records_collected:number; last_error:string|null }
export interface SystemHealth { api:ComponentHealth; database:ComponentHealth; adapters:ComponentHealth[]; analytics:ComponentHealth[]; assistant:ComponentHealth; mode:"demo"|"live"; live_available:boolean; message:string; ingestion?:IngestionSummary|null; connectors?:ConnectorState[] }
export interface PlatformState { platform:string; status:string; detail:string }
export interface Citation { ref:string; evidence_id:string; excerpt:string; platform:string; account_username:string; event_time:string }
export interface AssistantAnswer { answer:string; citations:Citation[]; grounded:boolean; provider:string; watch_id:string; timestamp:string }
export interface IngestionResult { platform:string; status:string; detail:string; records_fetched:number; records_stored:number; analyzed:number; mode:string }
export interface ConnectionTest { platform:string; configured:boolean; authenticated:boolean; source_reachable:boolean; source_accessible?:boolean; api_accessible?:boolean; source_name?:string; account?:string; status:string; identifier:string; last_message_time:string|null; last_success:string|null; error:string|null }
export interface IngestionRunError { reason:string; external_id:string|null; detail:string; event_time:string|null }
export interface IngestionLogDetail extends IngestionLog { errors:IngestionRunError[] }
export interface NarrativeStep { stage:string; platform:string; detail:string; event_time:string|null; records:number }
export interface CrossPlatformRow { platform:string; mentions:number; positive:number; negative:number; first_seen:string|null; role:string; share:number }
export interface TimelineNotes { trends?:string; network?:string; records?:string }
export interface TimelineResponse { watch_id:string; timestamp:string; mode:"demo"|"live"; cross_platform:CrossPlatformRow[]; narrative_movement:NarrativeStep[]; notes:TimelineNotes }
export interface WatchSummary { id:string; name:string; mode:"demo"|"live"; status:string; platforms:string[] }
export interface IngestionSourceResult { platform:string; status:string; detail:string; records_found:number; records_new:number; records_duplicate:number; records_failed:number }
export interface IngestionJobResult { watch_id:string; job_type:string; mode:"demo"|"live"; records_found:number; records_new:number; records_duplicate:number; records_failed:number; started_at:string; completed_at:string; sources:IngestionSourceResult[]; message:string }
export interface IngestionLog { id:string; watch_id:string|null; platform:string; job_type:string; status:string; started_at:string; completed_at:string|null; records_found:number; records_new:number; records_duplicate:number; records_failed:number; detail:string }
export interface SchedulerState { enabled:boolean; interval:string; last_ingestion:string|null; next_ingestion:string|null; status:string }
export interface WatchProvenance { watch_id:string; mode:"demo"|"live"; sources:ConnectorState[]; last_ingestion:string|null; records:number; freshness:string }

export interface AuthUser { id:string; email:string; display_name:string; role:string; active:boolean; last_login_at:string|null }
export interface AuthToken { access_token:string; token_type:string; expires_in:number; user:AuthUser }
export interface AuthStatus { auth_required:boolean; users_provisioned:number; roles:string[] }
export interface AuditEntry { id:number; created_at:string; action:string; actor:string; watch_id:string|null; detail:string; record_hash:string }

const TOKEN_KEY="drishti.auth.token";
export function storedToken():string|null{ try{ return localStorage.getItem(TOKEN_KEY) }catch{ return null } }
export function setStoredToken(token:string|null){ try{ token?localStorage.setItem(TOKEN_KEY,token):localStorage.removeItem(TOKEN_KEY) }catch{ /* storage unavailable */ } }

async function request<T>(path:string, init?:RequestInit):Promise<T|null>{
  if(!backendConfigured) return null;
  try{
    const token=storedToken();
    const headers:Record<string,string>={"Content-Type":"application/json",...(token?{Authorization:`Bearer ${token}`}:{})};
    const response=await fetch(`${API_BASE}${path}`,{headers,...init});
    if(!response.ok) return null;
    return await response.json() as T;
  }catch{ return null }
}

export const api={
  health:()=>request<SystemHealth>("/api/system-health"),
  adapters:()=>request<PlatformState[]>("/api/adapters"),
  refresh:(watchId:string)=>request<IngestionResult[]>(`/api/watches/${watchId}/refresh`,{method:"POST"}),
  ask:(watchId:string,snapshot:number,body:{question:string;topic?:string|undefined;account_id?:string|undefined})=>
    request<AssistantAnswer>(`/api/watches/${watchId}/assistant/query?snapshot=${snapshot}`,{method:"POST",body:JSON.stringify(body)}),
  connectors:()=>request<ConnectorState[]>("/api/connectors"),
  testConnector:(platform:string)=>request<ConnectionTest>(`/api/connectors/${platform}/test`,{method:"POST"}),
  ingest:(watchId:string)=>request<IngestionJobResult>(`/api/watches/${watchId}/ingest`,{method:"POST"}),
  backfill:(watchId:string,from:string,to:string)=>
    request<IngestionJobResult>(`/api/watches/${watchId}/backfill`,{method:"POST",body:JSON.stringify({from,to})}),
  provenance:(watchId:string)=>request<WatchProvenance>(`/api/watches/${watchId}/provenance`),
  ingestionLogs:()=>request<IngestionLog[]>("/api/ingestion/logs?limit=25"),
  ingestionLog:(runId:string)=>request<IngestionLogDetail>(`/api/ingestion/logs/${runId}`),
  timeline:(watchId:string,snapshot:number)=>
    request<TimelineResponse>(`/api/watches/${watchId}/timeline?snapshot=${snapshot}`),
  createWatch:(body:{name:string;keywords:string;platforms:string[];range_from:string;range_to:string;mode:"demo"|"live"})=>
    request<WatchSummary>("/api/watches",{method:"POST",body:JSON.stringify(body)}),
  updateWatch:(watchId:string,body:{status?:string;mode?:"demo"|"live"})=>
    request<WatchSummary>(`/api/watches/${watchId}`,{method:"PATCH",body:JSON.stringify(body)}),
  scheduler:()=>request<SchedulerState>("/api/scheduler"),
  updateScheduler:(body:{enabled?:boolean;interval?:string})=>
    request<SchedulerState>("/api/scheduler",{method:"PUT",body:JSON.stringify(body)}),
  authStatus:()=>request<AuthStatus>("/api/auth/status"),
  login:(email:string,password:string)=>
    request<AuthToken>("/api/auth/login",{method:"POST",body:JSON.stringify({email,password})}),
  me:()=>request<AuthUser>("/api/auth/me"),
  auditLog:()=>request<AuditEntry[]>("/api/audit?limit=50"),
  briefing:(watchId:string,snapshot:number)=>
    request<Record<string,unknown>>(`/api/watches/${watchId}/briefing?snapshot=${snapshot}`),
};
