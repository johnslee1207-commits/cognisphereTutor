import { apiFetch, apiUrl } from "./api";

export interface AiInfraLab {
  labId: string;
  title: string;
  role: string;
  roleLabel?: string;
  stage: string;
  symptom: string;
  learnerTask: string;
  scenarioId?: string;
  executionMode: string;
  competencies: string[];
  requiredEvidence: string[];
  diagnosisChoices: string[];
  latestRun?: { runId: string; status: string; mode: string; path: string; createdAt?: string } | null;
  runCount?: number;
  embed_url?: string;
}

export interface AiInfraEvidence {
  runId: string;
  scenarioId: string;
  mode: string;
  status: string;
  createdAt?: string;
  path: string;
}

export interface AiInfraDiagnosisAssessment {
  assessmentPath?: string;
  spec?: {
    labId?: string;
    selectedDiagnosis?: string;
    score?: number;
    passed?: boolean;
    feedback?: string;
    competencyEvidence?: {
      spec?: {
        skills?: string[];
        level?: string;
        evidenceRefs?: string[];
      };
    };
  };
  [key: string]: unknown;
}

export interface AiInfraLearningWorkspaceState {
  selected_course_id: string | null;
  selected_unit_id: string | null;
  quiz_answers: Record<string, string>;
  completed_units: Record<string, boolean>;
  reflection_notes: Record<string, string>;
  diagnosis_notes: Record<string, string>;
  source_document_notes: Record<string, string>;
  evidence_bundles: Record<string, string[]>;
  review_ledger: Record<string, { completedAt?: string; lastReviewedAt?: string }>;
}

export interface AiInfraLearningWorkspaceResult {
  ok: boolean;
  workspace_id: string;
  state: AiInfraLearningWorkspaceState;
  updated_at?: number | null;
}

export interface AiInfraStatus {
  ok: boolean;
  base_url: string;
  embed_url: string;
  summary: {
    counts?: {
      labs?: number;
      scenarios?: number;
      evidence?: number;
      simulations?: number;
    };
    profile?: string;
  };
  curriculum: {
    spec?: {
      tracks?: { id: string; title: string; roles: string[] }[];
      modules?: {
        id: string;
        title: string;
        track: string;
        outcomes: string[];
        labs: string[];
      }[];
    };
  };
  maturity: {
    spec?: {
      counts?: Record<string, number>;
      labs?: {
        labId: string;
        title: string;
        role: string;
        executionMode: string;
        maturityLevel: string;
        upgradeTarget: string;
        latestRun?: AiInfraLab["latestRun"];
      }[];
    };
  };
  issues: string[];
}

export async function fetchAiInfraStatus(): Promise<AiInfraStatus> {
  const res = await apiFetch(apiUrl("/api/v1/learning/ai-infra-twin/status"));
  if (!res.ok) throw new Error(`AI Infra Twin status failed: ${res.status}`);
  return res.json() as Promise<AiInfraStatus>;
}

export async function fetchAiInfraLabs(): Promise<AiInfraLab[]> {
  const res = await apiFetch(apiUrl("/api/v1/learning/ai-infra-twin/labs"));
  if (!res.ok) throw new Error(`AI Infra Twin labs failed: ${res.status}`);
  return res.json() as Promise<AiInfraLab[]>;
}

export async function fetchAiInfraLab(labId: string): Promise<AiInfraLab> {
  const res = await apiFetch(
    apiUrl(`/api/v1/learning/ai-infra-twin/labs/${encodeURIComponent(labId)}`),
  );
  if (!res.ok) throw new Error(`AI Infra Twin lab failed: ${res.status}`);
  return res.json() as Promise<AiInfraLab>;
}

export async function fetchAiInfraEvidence(): Promise<AiInfraEvidence[]> {
  const res = await apiFetch(apiUrl("/api/v1/learning/ai-infra-twin/evidence"));
  if (!res.ok) throw new Error(`AI Infra Twin evidence failed: ${res.status}`);
  return res.json() as Promise<AiInfraEvidence[]>;
}

export async function runAiInfraLab(labId: string) {
  const res = await apiFetch(
    apiUrl(`/api/v1/learning/ai-infra-twin/labs/${encodeURIComponent(labId)}/run`),
    { method: "POST" },
  );
  if (!res.ok) throw new Error(`AI Infra Twin lab run failed: ${res.status}`);
  return res.json();
}

export async function submitAiInfraDiagnosis(opts: {
  labId: string;
  selectedDiagnosis: string;
  evidenceRefs?: string[];
  notes?: string;
}): Promise<AiInfraDiagnosisAssessment> {
  const res = await apiFetch(
    apiUrl(`/api/v1/learning/ai-infra-twin/labs/${encodeURIComponent(opts.labId)}/diagnosis`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        selected_diagnosis: opts.selectedDiagnosis,
        evidence_refs: opts.evidenceRefs || [],
        notes: opts.notes || "",
      }),
    },
  );
  if (!res.ok) throw new Error(`AI Infra Twin diagnosis failed: ${res.status}`);
  return res.json() as Promise<AiInfraDiagnosisAssessment>;
}

export async function fetchAiInfraLearningWorkspace(
  workspaceId = "default",
): Promise<AiInfraLearningWorkspaceResult> {
  const res = await apiFetch(
    apiUrl(`/api/v1/learning/ai-infra-twin/workspace/${encodeURIComponent(workspaceId)}`),
  );
  if (!res.ok) throw new Error(`AI Infra workspace failed: ${res.status}`);
  return res.json() as Promise<AiInfraLearningWorkspaceResult>;
}

export async function saveAiInfraLearningWorkspace(
  state: AiInfraLearningWorkspaceState,
  workspaceId = "default",
): Promise<AiInfraLearningWorkspaceResult> {
  const res = await apiFetch(
    apiUrl(`/api/v1/learning/ai-infra-twin/workspace/${encodeURIComponent(workspaceId)}`),
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state }),
    },
  );
  if (!res.ok) throw new Error(`AI Infra workspace save failed: ${res.status}`);
  return res.json() as Promise<AiInfraLearningWorkspaceResult>;
}

export async function deleteAiInfraLearningWorkspace(
  workspaceId = "default",
): Promise<AiInfraLearningWorkspaceResult> {
  const res = await apiFetch(
    apiUrl(`/api/v1/learning/ai-infra-twin/workspace/${encodeURIComponent(workspaceId)}`),
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(`AI Infra workspace delete failed: ${res.status}`);
  return res.json() as Promise<AiInfraLearningWorkspaceResult>;
}
