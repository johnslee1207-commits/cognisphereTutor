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
  };
  plugins: CognispherePluginInfo[];
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
    modules: { id: string; name: string; kp_count: number }[];
  };
  is_cognisphere_path?: boolean;
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

export async function suggestCognisphereFocus(slug?: string) {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/suggest-focus"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug: slug || null }),
    },
  );
  if (!res.ok) throw new Error(`Suggest focus failed: ${res.status}`);
  return res.json();
}

export async function startCognisphereTutor(opts: {
  slug: string;
  hintLevel?: number;
  pathId?: string;
}) {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/tutor/start"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
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

export function isCognispherePathId(bookId: string): boolean {
  return bookId.startsWith("csphere-");
}
