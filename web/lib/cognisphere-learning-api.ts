import { apiFetch, apiUrl } from "./api";

export interface CognispherePluginInfo {
  domain: string;
  /** learning = import-and-seed packs; twin = digital-twin runtime packs */
  kind?: "learning" | "twin" | string;
  plugin_id?: string;
  display_name?: string;
  description?: string;
  version?: string;
  lifecycle?: string;
  capabilities: string[];
  distribution?: Record<string, unknown>;
  tutor_pack?: Record<string, unknown>;
  path_id?: string;
  source?: string;
  valid: boolean;
}

export interface AwsTwinMasteryGate {
  ok?: boolean;
  status?: string;
  path?: string;
  domain?: string;
  learning_domain?: string;
  runtime_mode?: string;
  package_id?: string;
  choice_id?: string;
  mastery_path_id?: string;
  continue_in_chat?: string;
  error?: string;
}

export interface CognisphereLearningStatus {
  ok: boolean;
  plugins_root?: string;
  plugin_count?: number;
  issues: string[];
  twin_issues?: string[];
  gates: {
    sandbox?: { authorized?: boolean; env?: string };
    sandbox_authorized?: boolean;
    trusted_context?: {
      phase?: string;
      kit_configured?: boolean;
      mode?: string;
      blocker?: { code?: string; meaning?: string } | null;
    };
    aws_twin_mastery?: AwsTwinMasteryGate;
  };
  plugins: CognispherePluginInfo[];
  tutor_pack?: Record<string, unknown>;
  distribution_catalog?: Record<string, unknown>;
  bundled_distribution?: {
    available?: number;
    domains?: string[];
  };
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
    distribution_source?: string;
  };
  mastery_path?: {
    path_id: string;
    module_count: number;
    kp_count: number;
    knowledge_sparse?: boolean;
    runtime_plan_fallback?: boolean;
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

export interface AbilityRadarAxis {
  id?: string;
  label?: string;
  mastered?: number;
  total?: number;
  pct: number;
}

export interface AbilityRadarWeakArea {
  module_id?: string;
  module_name?: string;
  kp_id?: string;
  kp_name?: string;
  type?: string;
  status?: string;
  mastery?: number;
  mastery_pct?: number;
}

export interface AbilityRadarDomain {
  path_id: string;
  name: string;
  domain?: string | null;
  is_cognisphere?: boolean;
  mastered_pct: number;
  avg_mastery_pct: number;
  kp_count: number;
  weak_count: number;
  axes: AbilityRadarAxis[];
}

export interface AbilityRadarResult {
  ok: boolean;
  contract?: string;
  domain_count: number;
  domains: AbilityRadarDomain[];
  weak_domains: AbilityRadarDomain[];
  selected?: {
    path_id: string;
    name: string;
    domain?: string | null;
    mastered_pct: number;
    avg_mastery_pct: number;
    counts?: { mastered?: number; learning?: number; new?: number; total?: number };
    axes: AbilityRadarAxis[];
    weak_areas: AbilityRadarWeakArea[];
    skill_graph?: Record<string, unknown> | null;
  } | null;
  path_id?: string | null;
}

export async function fetchAbilityRadar(opts?: {
  pathId?: string;
  weakLimit?: number;
  includeSkillGraph?: boolean;
}): Promise<AbilityRadarResult> {
  const params = new URLSearchParams();
  if (opts?.pathId) params.set("path_id", opts.pathId);
  if (opts?.weakLimit != null) params.set("weak_limit", String(opts.weakLimit));
  if (opts?.includeSkillGraph === false) {
    params.set("include_skill_graph", "false");
  }
  const qs = params.toString();
  const res = await apiFetch(
    apiUrl(
      `/api/v1/learning/cognisphere/ability-radar${qs ? `?${qs}` : ""}`,
    ),
  );
  if (!res.ok) throw new Error(`Ability radar failed: ${res.status}`);
  return res.json() as Promise<AbilityRadarResult>;
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

export interface CrossDomainResult {
  ok?: boolean;
  goal?: string;
  required_capabilities?: string[];
  match_count?: number;
  matches?: Array<{
    domain?: string;
    plugin_id?: string;
    lifecycle?: string;
    available?: string[];
    matched?: boolean;
  }>;
  source?: string;
  phase?: string;
  [key: string]: unknown;
}

export interface ComposeResult {
  ok?: boolean;
  domains?: string[];
  contexts?: Array<{
    domain?: string;
    plugin_id?: string;
    matched?: boolean;
    negotiation?: Record<string, unknown>;
  }>;
  issues?: string[];
  source?: string;
  phase?: string;
  [key: string]: unknown;
}

export interface ComposeAndSeedResult {
  ok: boolean;
  phase?: string;
  compose?: ComposeResult;
  seeded_count: number;
  failed_count: number;
  seeds: Array<ImportAndSeedResult | { ok: false; domain: string; error?: unknown }>;
  continue_in_chat?: string | null;
}

export async function queryCognisphereCrossDomain(opts: {
  requiredCapabilities?: string[];
  goal?: string;
}): Promise<CrossDomainResult> {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/cross-domain"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        required_capabilities: opts.requiredCapabilities ?? [],
        goal: opts.goal || null,
      }),
    },
  );
  if (!res.ok) throw new Error(`Cross-domain query failed: ${res.status}`);
  return res.json() as Promise<CrossDomainResult>;
}

export async function composeCognisphereContexts(opts: {
  domains?: string[];
  requiredCapabilities?: string[];
}): Promise<ComposeResult> {
  const res = await apiFetch(apiUrl("/api/v1/learning/cognisphere/compose"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      domains: opts.domains ?? [],
      required_capabilities: opts.requiredCapabilities ?? [],
    }),
  });
  if (!res.ok) throw new Error(`Compose failed: ${res.status}`);
  return res.json() as Promise<ComposeResult>;
}

export interface RecommendFromGoalResult {
  ok: boolean;
  goal?: string;
  recommended_domains: string[];
  match_count: number;
  matches?: Array<{ domain?: string; plugin_id?: string; available?: string[] }>;
  compose_seed?: ComposeAndSeedResult | null;
  continue_in_chat?: string | null;
  seeded_count?: number;
  failed_count?: number;
  [key: string]: unknown;
}

export async function recommendCognisphereFromGoal(opts: {
  goal: string;
  requiredCapabilities?: string[];
  composeAndSeed?: boolean;
}): Promise<RecommendFromGoalResult> {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/recommend-from-goal"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        goal: opts.goal,
        required_capabilities: opts.requiredCapabilities ?? ["deeptutor_export"],
        compose_and_seed: opts.composeAndSeed ?? false,
      }),
    },
  );
  if (!res.ok) {
    let message = `Recommend failed: ${res.status}`;
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
  return res.json() as Promise<RecommendFromGoalResult>;
}

export async function composeAndSeedCognisphere(opts: {
  domains: string[];
  requiredCapabilities?: string[];
  stopOnError?: boolean;
}): Promise<ComposeAndSeedResult> {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/compose-and-seed"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domains: opts.domains,
        required_capabilities: opts.requiredCapabilities ?? [],
        seed_mastery_path: true,
        persist_import: true,
        stop_on_error: opts.stopOnError ?? false,
      }),
    },
  );
  if (!res.ok) {
    let message = `Compose-and-seed failed: ${res.status}`;
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
  return res.json() as Promise<ComposeAndSeedResult>;
}

export async function suggestCognisphereFocus(opts: {
  domain: string;
  slug?: string;
  pathId?: string;
}) {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/suggest-focus"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain: opts.domain,
        slug: opts.slug || null,
        path_id: opts.pathId || null,
      }),
    },
  );
  if (!res.ok) throw new Error(`Suggest focus failed: ${res.status}`);
  return res.json();
}

export async function planCognispherePath(opts: {
  domain: string;
  learnerId?: string;
  pathId?: string;
}) {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/plan-path"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain: opts.domain,
        learner_id: opts.learnerId || "offline-learner",
        path_id: opts.pathId || null,
      }),
    },
  );
  if (!res.ok) throw new Error(`Plan path failed: ${res.status}`);
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

export interface AwsTwinMasteryResult {
  ok: boolean;
  status?: string;
  path?: string;
  domain?: string;
  runtime_mode?: string;
  package_id?: string;
  choice_id?: string;
  steps?: unknown;
  step_results?: unknown;
  issues?: string[];
  error?: string;
  [key: string]: unknown;
}

/** Offline AWS digital twin mastery readiness (CP-04→06→12 façade). */
export async function fetchAwsTwinMasteryStatus(): Promise<AwsTwinMasteryResult> {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/aws-twin-mastery"),
  );
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `AWS twin mastery status failed: ${res.status}`);
  }
  return res.json() as Promise<AwsTwinMasteryResult>;
}

/** Run offline AWS digital twin Practitioner mastery (fixture by default). */
export async function runAwsTwinMastery(opts?: {
  packageId?: string;
  choiceId?: string;
  includeTutor?: boolean;
  includeAcceptance?: boolean;
  includeMvpProduct?: boolean;
}): Promise<AwsTwinMasteryResult> {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/aws-twin-mastery"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        package_id: opts?.packageId,
        choice_id: opts?.choiceId,
        include_tutor: opts?.includeTutor ?? true,
        include_acceptance: opts?.includeAcceptance ?? true,
        include_mvp_product: opts?.includeMvpProduct ?? false,
      }),
    },
  );
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `AWS twin mastery run failed: ${res.status}`);
  }
  return res.json() as Promise<AwsTwinMasteryResult>;
}

export interface HandshakeResult {
  ok: boolean;
  domain?: string;
  source?: string;
  contract?: string;
  sot_docs?: string;
  issues?: string[];
  error?: string;
  [key: string]: unknown;
}

export interface LearningTwinFlowResult {
  ok?: boolean;
  flow?: string;
  composition_intent?: string | null;
  summary?: Record<string, unknown>;
  learning?: Record<string, unknown>;
  twin?: Record<string, unknown>;
  contract?: string;
  issues?: string[];
  error?: string;
  [key: string]: unknown;
}

/** Guided Learning thin handshake for a learning-domain pack. */
export async function runCognisphereHandshake(opts: {
  domain: string;
  goal?: string;
  topic?: string;
  checkMode?: string;
}): Promise<HandshakeResult> {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/handshake"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain: opts.domain,
        goal: opts.goal,
        topic: opts.topic,
        check_mode: opts.checkMode ?? "full",
      }),
    },
  );
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Handshake failed: ${res.status}`);
  }
  return res.json() as Promise<HandshakeResult>;
}

/** Learning → twin combined flow (composition_intent pass-through). */
export async function runLearningTwinFlow(opts: {
  learningDomain: string;
  goal?: string;
  topic?: string;
  compositionIntent?: "learn_then_practice" | "failure_drill" | string;
  acceptTwinStubs?: boolean;
}): Promise<LearningTwinFlowResult> {
  const res = await apiFetch(
    apiUrl("/api/v1/learning/cognisphere/handshake/learning-twin"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        learning_domain: opts.learningDomain,
        goal: opts.goal,
        topic: opts.topic,
        composition_intent: opts.compositionIntent,
        accept_twin_stubs: opts.acceptTwinStubs ?? true,
      }),
    },
  );
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Learning-twin flow failed: ${res.status}`);
  }
  return res.json() as Promise<LearningTwinFlowResult>;
}

/** Learning Space deep-link carrying an NL goal (+ optional recommended domains). */
export function learningSpaceGoalHref(
  goal: string,
  opts?: { domains?: string[] },
): string {
  const params = new URLSearchParams();
  const text = goal.trim();
  if (text) params.set("goal", text);
  const domains = (opts?.domains || []).map((d) => d.trim()).filter(Boolean);
  if (domains.length) params.set("domains", domains.join(","));
  const qs = params.toString();
  return qs ? `/space/learning?${qs}` : "/space/learning";
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
