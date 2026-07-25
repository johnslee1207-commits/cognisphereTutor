import { apiFetch, apiUrl } from "./api";

export interface CognispherePluginInfo {
  domain: string;
  plugin_id?: string;
  lifecycle?: string;
  capabilities: string[];
  path_id?: string;
  valid: boolean;
}

export interface CognisphereLearningStatus {
  ok: boolean;
  plugins_root?: string;
  plugin_count?: number;
  issues: string[];
  gates: {
    sandbox?: { authorized?: boolean; env?: string };
    sandbox_authorized?: boolean;
    trusted_context?: {
      phase?: string;
      kit_configured?: boolean;
      mode?: string;
      blocker?: { code?: string; meaning?: string } | null;
    };
  };
  plugins: CognispherePluginInfo[];
  defaults?: { chat_capability?: string };
}

export interface ImportAndSeedResult {
  ok: boolean;
  domain: string;
  import: {
    status?: string;
    phase?: string;
    knowledge_summary?: unknown;
    artifact_path?: string;
  };
  mastery_path?: {
    path_id: string;
    module_count: number;
    kp_count: number;
    knowledge_sparse?: boolean;
    note?: string | null;
    continue_in_chat?: string;
    modules: { id: string; name: string; kp_count: number }[];
  };
  is_cognisphere_path?: boolean;
  continue_in_chat?: string;
}

export async function fetchCognisphereLearningStatus(): Promise<CognisphereLearningStatus> {
  const res = await apiFetch(apiUrl("/api/v1/learning/cognisphere/status"));
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Cognisphere status failed: ${res.status}`);
  }
  return res.json() as Promise<CognisphereLearningStatus>;
}

export async function importAndSeedCognisphere(
  domain: string,
  opts?: { pathId?: string; seed?: boolean },
): Promise<ImportAndSeedResult> {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/import-and-seed"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain,
        path_id: opts?.pathId,
        seed_mastery_path: opts?.seed ?? true,
        persist_import: true,
      }),
    },
  );
  if (!res.ok) {
    let message = `Import failed: ${res.status}`;
    try {
      const body = await res.json();
      message =
        body?.detail?.message ||
        body?.detail?.code ||
        (typeof body?.detail === "string" ? body.detail : message);
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  return res.json() as Promise<ImportAndSeedResult>;
}

export async function suggestCognisphereFocus(opts: {
  domain: string;
  slug?: string;
}) {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/suggest-focus"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain: opts.domain,
        slug: opts.slug || null,
      }),
    },
  );
  if (!res.ok) throw new Error(`Suggest focus failed: ${res.status}`);
  return res.json();
}

export async function startCognisphereTutor(opts: {
  domain: string;
  slug: string;
  hintLevel?: number;
  pathId?: string;
}): Promise<{
  ok?: boolean;
  continue_in_chat?: string;
  tutor_session_id?: string;
  events_url?: string;
  chat_capability?: string;
  path_id?: string;
  session?: Record<string, unknown>;
  [key: string]: unknown;
}> {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/tutor/start"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain: opts.domain,
        slug: opts.slug,
        hint_level: opts.hintLevel ?? 0,
        path_id: opts.pathId,
        persist: false,
      }),
    },
  );
  if (!res.ok) throw new Error(`Tutor start failed: ${res.status}`);
  return res.json();
}

/** Chat deep-link that pre-selects Mastery Path mode. */
export function masteryChatHref(
  pathId: string,
  opts?: { tutorSessionId?: string },
): string {
  const params = new URLSearchParams({ capability: "mastery_path" });
  if (opts?.tutorSessionId) {
    params.set("tutor_session", opts.tutorSessionId);
  }
  return `/home/${encodeURIComponent(pathId)}?${params.toString()}`;
}

export function isCognispherePathId(bookId: string): boolean {
  return bookId.startsWith("csphere-");
}

/** Extract domain from ``csphere-{domain}`` mastery path ids. */
export function domainFromCognispherePathId(bookId: string): string | null {
  if (!isCognispherePathId(bookId)) return null;
  const domain = bookId.slice("csphere-".length).trim();
  return domain || null;
}
