"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BookOpenCheck,
  CheckCircle2,
  Cpu,
  ExternalLink,
  GraduationCap,
  Loader2,
  Network,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";

import {
  fetchAiInfraEvidence,
  fetchAiInfraLab,
  fetchAiInfraLearningWorkspace,
  fetchAiInfraLabs,
  fetchAiInfraStatus,
  deleteAiInfraLearningWorkspace,
  runAiInfraLab,
  saveAiInfraLearningWorkspace,
  submitAiInfraDiagnosis,
  type AiInfraDiagnosisAssessment,
  type AiInfraEvidence,
  type AiInfraLab,
  type AiInfraLearningWorkspaceState as ServerAiInfraLearningWorkspaceState,
  type AiInfraStatus,
} from "@/lib/ai-infra-twin-api";
import {
  filterAiInfraCoursePaths,
  findAiInfraKnowledgeUnit,
  extractAiInfraPluginKnowledge,
  getAiInfraCourseProgress,
  getPriorityAiInfraCoursePaths,
  prioritizeAiInfraContent,
} from "@/lib/ai-infra-learning-content";
import {
  runCognisphereHandshake,
  type HandshakeResult,
} from "@/lib/cognisphere-learning-api";
import { loadFromStorage, removeFromStorage, saveToStorage } from "@/lib/persistence";

const AI_INFRA_WORKSPACE_STORAGE_KEY = "ai_infra_learning_workspace_v1";
const AI_INFRA_WORKSPACE_ID = "default";

interface AiInfraLearningWorkspaceState {
  selectedCourseId: string | null;
  selectedUnitId: string | null;
  quizAnswers: Record<string, string>;
  completedUnits: Record<string, boolean>;
  reflectionNotes: Record<string, string>;
}

export default function AiInfraTwinPage() {
  const { i18n } = useTranslation();
  const router = useRouter();
  const zh = i18n.language?.toLowerCase().startsWith("zh");
  const tr = useCallback((cn: string, en: string) => (zh ? cn : en), [zh]);
  const [status, setStatus] = useState<AiInfraStatus | null>(null);
  const [labs, setLabs] = useState<AiInfraLab[]>([]);
  const [evidence, setEvidence] = useState<AiInfraEvidence[]>([]);
  const [selected, setSelected] = useState<AiInfraLab | null>(null);
  const [pluginHandshake, setPluginHandshake] = useState<HandshakeResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [diagnosing, setDiagnosing] = useState(false);
  const [diagnosisResult, setDiagnosisResult] = useState<AiInfraDiagnosisAssessment | null>(null);
  const [selectedCourseId, setSelectedCourseId] = useState<string | null>(null);
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [courseQuery, setCourseQuery] = useState("");
  const [completedUnits, setCompletedUnits] = useState<Record<string, boolean>>({});
  const [reflectionNotes, setReflectionNotes] = useState<Record<string, string>>({});
  const [workspaceHydrated, setWorkspaceHydrated] = useState(false);
  const [workspaceSyncState, setWorkspaceSyncState] = useState<"local" | "synced" | "offline">("local");
  const [error, setError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const stored = loadFromStorage<AiInfraLearningWorkspaceState>(
      AI_INFRA_WORKSPACE_STORAGE_KEY,
      {
        selectedCourseId: null,
        selectedUnitId: null,
        quizAnswers: {},
        completedUnits: {},
        reflectionNotes: {},
      },
    );
    setSelectedCourseId(stored.selectedCourseId);
    setSelectedUnitId(stored.selectedUnitId);
    setQuizAnswers(stored.quizAnswers || {});
    setCompletedUnits(stored.completedUnits || {});
    setReflectionNotes(stored.reflectionNotes || {});
    setWorkspaceHydrated(true);
    void fetchAiInfraLearningWorkspace(AI_INFRA_WORKSPACE_ID)
      .then((result) => {
        if (result.updated_at == null) {
          setWorkspaceSyncState("synced");
          return;
        }
        const next = workspaceStateFromServer(result.state);
        setSelectedCourseId(next.selectedCourseId);
        setSelectedUnitId(next.selectedUnitId);
        setQuizAnswers(next.quizAnswers);
        setCompletedUnits(next.completedUnits);
        setReflectionNotes(next.reflectionNotes);
        saveToStorage<AiInfraLearningWorkspaceState>(
          AI_INFRA_WORKSPACE_STORAGE_KEY,
          next,
        );
        setWorkspaceSyncState("synced");
      })
      .catch(() => setWorkspaceSyncState("offline"));
  }, []);

  useEffect(() => {
    if (!workspaceHydrated) return;
    const state = {
      selectedCourseId,
      selectedUnitId,
      quizAnswers,
      completedUnits,
      reflectionNotes,
    };
    saveToStorage<AiInfraLearningWorkspaceState>(AI_INFRA_WORKSPACE_STORAGE_KEY, state);
    void saveAiInfraLearningWorkspace(
      workspaceStateToServer(state),
      AI_INFRA_WORKSPACE_ID,
    )
      .then(() => setWorkspaceSyncState("synced"))
      .catch(() => setWorkspaceSyncState("offline"));
  }, [
    completedUnits,
    quizAnswers,
    reflectionNotes,
    selectedCourseId,
    selectedUnitId,
    workspaceHydrated,
  ]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextStatus, nextLabs, nextEvidence, nextHandshake] = await Promise.all([
        fetchAiInfraStatus(),
        fetchAiInfraLabs(),
        fetchAiInfraEvidence(),
        runCognisphereHandshake({ domain: "ai_infra", checkMode: "full" }),
      ]);
      setStatus(nextStatus);
      setLabs(nextLabs);
      setEvidence(nextEvidence);
      setPluginHandshake(nextHandshake);
      setSelected((prev) => {
        const preferred = prev && nextLabs.find((lab) => lab.labId === prev.labId);
        return preferred || nextLabs[0] || null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI Infra Twin unavailable");
      setStatus(null);
      setLabs([]);
      setEvidence([]);
      setSelected(null);
      setPluginHandshake(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const modules = status?.curriculum?.spec?.modules || [];
  const maturityCounts = status?.maturity?.spec?.counts || {};
  const embedUrl =
    selected?.embed_url ||
    (selected && status?.base_url
      ? `${status.base_url}/embed/${encodeURIComponent(selected.labId)}`
      : status?.embed_url);

  const labsById = useMemo(() => new Map(labs.map((lab) => [lab.labId, lab])), [labs]);
  const handshakeSummary = pluginHandshake?.summary as
    | { tutor_ready?: boolean; issue_count?: number }
    | undefined;
  const pluginKnowledge = useMemo(
    () => extractAiInfraPluginKnowledge(pluginHandshake),
    [pluginHandshake],
  );
  const focusedContent = useMemo(
    () => prioritizeAiInfraContent({ knowledge: pluginKnowledge, selectedLab: selected }),
    [pluginKnowledge, selected],
  );
  const lessonCards = focusedContent.lessonCards;
  const knowledgeUnits = focusedContent.knowledgeUnits;
  const trustedSourceCoverage =
    pluginKnowledge?.trusted_source_coverage ||
    pluginKnowledge?.learning_surface?.trusted_source_coverage;
  const standardLearningAssets =
    pluginKnowledge?.standard_learning_assets ||
    pluginKnowledge?.learning_surface?.standard_learning_assets;
  const coursePaths =
    pluginKnowledge?.course_paths ||
    pluginKnowledge?.learning_surface?.course_paths ||
    [];
  const priorityCoursePaths = useMemo(
    () => getPriorityAiInfraCoursePaths(pluginKnowledge),
    [pluginKnowledge],
  );
  const visibleCoursePaths = useMemo(
    () => filterAiInfraCoursePaths(priorityCoursePaths, courseQuery),
    [courseQuery, priorityCoursePaths],
  );
  const selectedCourse = useMemo(
    () =>
      visibleCoursePaths.find((path) => path.course_path_id === selectedCourseId) ||
      priorityCoursePaths.find((path) => path.course_path_id === selectedCourseId) ||
      visibleCoursePaths[0] ||
      priorityCoursePaths[0] ||
      null,
    [priorityCoursePaths, selectedCourseId, visibleCoursePaths],
  );
  const selectedCourseUnits = useMemo(
    () =>
      (selectedCourse?.unit_refs || [])
        .map((unitId) => findAiInfraKnowledgeUnit(pluginKnowledge, unitId))
        .filter((unit): unit is NonNullable<typeof unit> => Boolean(unit)),
    [pluginKnowledge, selectedCourse?.unit_refs],
  );
  const selectedUnit = useMemo(
    () =>
      selectedCourseUnits.find((unit) => unit.unit_id === selectedUnitId) ||
      selectedCourseUnits[0] ||
      null,
    [selectedCourseUnits, selectedUnitId],
  );
  const selectedQuiz = selectedUnit?.standard_learning?.assessment?.quiz?.[0];
  const selectedQuizAnswer = selectedQuiz?.question_id
    ? quizAnswers[selectedQuiz.question_id]
    : undefined;
  const selectedQuizCorrect = Boolean(
    selectedQuizAnswer && selectedQuizAnswer === selectedQuiz?.answer,
  );
  const completedUnitIds = useMemo(
    () => new Set(Object.entries(completedUnits).filter(([, done]) => done).map(([unitId]) => unitId)),
    [completedUnits],
  );
  const selectedCourseProgress = useMemo(
    () => getAiInfraCourseProgress(selectedCourse, completedUnitIds),
    [completedUnitIds, selectedCourse],
  );
  const selectedReflection = selectedUnit?.unit_id
    ? reflectionNotes[selectedUnit.unit_id] || ""
    : "";
  const selectedUnitLabs = useMemo(() => {
    const labRefs = [
      ...(selectedUnit?.standard_learning?.twin_practice?.lab_refs || []),
      ...(selectedUnit?.lab_refs || []),
    ];
    return Array.from(new Set(labRefs))
      .map((labId) => labsById.get(labId))
      .filter((lab): lab is AiInfraLab => Boolean(lab));
  }, [labsById, selectedUnit]);
  const expertUnits = useMemo(
    () =>
      knowledgeUnits.filter((unit) =>
        String(unit.unit_id || "").startsWith("ai_infra.expert."),
      ),
    [knowledgeUnits],
  );
  const selectedMaturity = useMemo(
    () => status?.maturity?.spec?.labs?.find((lab) => lab.labId === selected?.labId),
    [selected?.labId, status],
  );
  const selectedLatestRun = selected?.latestRun || selectedMaturity?.latestRun || null;
  const selectedEvidence = useMemo(
    () =>
      selected?.scenarioId
        ? evidence.filter((item) => item.scenarioId === selected.scenarioId).slice(0, 4)
        : [],
    [evidence, selected?.scenarioId],
  );

  useEffect(() => {
    if (!selectedCourseId && priorityCoursePaths[0]?.course_path_id) {
      setSelectedCourseId(priorityCoursePaths[0].course_path_id);
    }
  }, [priorityCoursePaths, selectedCourseId]);

  useEffect(() => {
    if (selectedCourseUnits[0]?.unit_id && !selectedCourseUnits.some((unit) => unit.unit_id === selectedUnitId)) {
      setSelectedUnitId(selectedCourseUnits[0].unit_id);
    }
  }, [selectedCourseUnits, selectedUnitId]);

  const handleSelect = useCallback(async (lab: AiInfraLab) => {
    setError(null);
    setLastRun(null);
    setDiagnosisResult(null);
    try {
      setSelected(await fetchAiInfraLab(lab.labId));
    } catch {
      setSelected(lab);
    }
  }, []);

  const handleRun = useCallback(async () => {
    if (!selected) return;
    setRunning(true);
    setError(null);
    try {
      const result = await runAiInfraLab(selected.labId);
      setLastRun(result as Record<string, unknown>);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lab run failed");
    } finally {
      setRunning(false);
    }
  }, [load, selected]);

  const handleDiagnosis = useCallback(
    async (selectedDiagnosis: string) => {
      if (!selected) return;
      setDiagnosing(true);
      setError(null);
      try {
        const result = await submitAiInfraDiagnosis({
          labId: selected.labId,
          selectedDiagnosis,
          evidenceRefs: selectedEvidence.map((item) => item.runId),
        });
        setDiagnosisResult(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Diagnosis failed");
      } finally {
        setDiagnosing(false);
      }
    },
    [selected, selectedEvidence],
  );

  const handleResetLearningWorkspace = useCallback(() => {
    removeFromStorage(AI_INFRA_WORKSPACE_STORAGE_KEY);
    void deleteAiInfraLearningWorkspace(AI_INFRA_WORKSPACE_ID)
      .then(() => setWorkspaceSyncState("synced"))
      .catch(() => setWorkspaceSyncState("offline"));
    setSelectedCourseId(priorityCoursePaths[0]?.course_path_id || null);
    setSelectedUnitId(priorityCoursePaths[0]?.unit_refs?.[0] || null);
    setQuizAnswers({});
    setCompletedUnits({});
    setReflectionNotes({});
  }, [priorityCoursePaths]);

  return (
    <main className="grid h-full min-h-0 grid-cols-[360px_minmax(0,1fr)] bg-[var(--background)]">
      <aside className="min-h-0 overflow-y-auto border-r border-[var(--border)] p-4">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
              <Cpu className="h-3.5 w-3.5" />
              AetherAI-Infra-Twin
            </div>
            <h1 className="mt-1 text-lg font-semibold text-[var(--foreground)]">
              {tr("AI Infra Twin Lab Console", "AI Infra Twin Lab Console")}
            </h1>
          </div>
          <div className="flex gap-1.5">
            <button
              type="button"
              onClick={() => router.push("/space/learning?domains=ai_infra")}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border)] hover:bg-[var(--accent)]"
              title={tr("标准学习", "Standard learning")}
            >
              <GraduationCap className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border)] hover:bg-[var(--accent)]"
              title={tr("刷新", "Refresh")}
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-3 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-500">
            {error}
          </div>
        )}

        <section className="mb-4 grid grid-cols-3 gap-2">
          <Metric label={tr("Labs", "Labs")} value={status?.summary?.counts?.labs ?? labs.length} />
          <Metric label={tr("证据", "Evidence")} value={status?.summary?.counts?.evidence ?? 0} />
          <Metric label={tr("场景", "Scenarios")} value={status?.summary?.counts?.scenarios ?? 0} />
        </section>

        <section className="mb-5 rounded-lg border border-[var(--border)] p-3">
          <div className="flex items-center gap-2">
            <Network className="h-4 w-4 text-[var(--muted-foreground)]" />
            <h2 className="text-sm font-medium text-[var(--foreground)]">
              {tr("Cognisphere 插件", "Cognisphere plugin")}
            </h2>
          </div>
          <div className="mt-2 space-y-1 text-xs text-[var(--muted-foreground)]">
            <div>
              {tr("状态", "Status")}:{" "}
              <span className={handshakeSummary?.tutor_ready ? "text-emerald-500" : "text-amber-500"}>
                {handshakeSummary?.tutor_ready ? "ready" : "checking"}
              </span>
            </div>
            <div>
              {tr("Pack", "Pack")}: {pluginKnowledge?.pack_metadata?.title || "ai_infra"}
            </div>
            <div>
              {tr("学习轨道", "Tracks")}: {pluginKnowledge?.tracks?.length ?? 0} ·{" "}
              {tr("主题族", "Topics")}: {pluginKnowledge?.topic_families?.length ?? 0}
            </div>
            <div>
              {tr("可信来源", "Trusted sources")}: {trustedSourceCoverage?.source_count ?? 0} ·{" "}
              {tr("索引文档", "Indexed docs")}: {trustedSourceCoverage?.indexed_documents ?? 0}
            </div>
            <div>
              {tr("专家单元", "Expert units")}: {trustedSourceCoverage?.expert_unit_count ?? expertUnits.length} ·{" "}
              {tr("测验", "Quizzes")}: {standardLearningAssets?.quiz_count ?? 0}
            </div>
            <div>
              {tr("课程路径", "Course paths")}: {standardLearningAssets?.course_path_count ?? coursePaths.length} ·{" "}
              {trustedSourceCoverage?.review_status || standardLearningAssets?.review_status || "review_required"}
            </div>
            <div>
              {tr("学习状态", "Learning state")}:{" "}
              <span className={workspaceSyncState === "synced" ? "text-emerald-500" : "text-amber-500"}>
                {workspaceSyncState}
              </span>
            </div>
            <button
              type="button"
              onClick={handleResetLearningWorkspace}
              className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-2 py-1 text-[11px] text-[var(--foreground)] hover:bg-[var(--accent)]"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              {tr("重置学习进度", "Reset learning progress")}
            </button>
            <div className="truncate">
              {tr("Twin 后端", "Twin backend")}:{" "}
              {pluginKnowledge?.twin_backend?.default_base_url || status?.base_url || "offline"}
            </div>
          </div>
        </section>

        <section className="mb-5 rounded-lg border border-[var(--border)] p-3">
          <h2 className="text-sm font-medium text-[var(--foreground)]">
            {tr("实验成熟度", "Lab maturity")}
          </h2>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {Object.entries(maturityCounts).map(([key, value]) => (
              <span
                key={key}
                className="rounded-full border border-[var(--border)] px-2 py-1 text-[11px] text-[var(--muted-foreground)]"
              >
                {key}: {value}
              </span>
            ))}
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-medium text-[var(--foreground)]">
            {tr("课程模块", "Curriculum modules")}
          </h2>
          {modules.map((module) => (
            <div key={module.id} className="rounded-lg border border-[var(--border)] p-3">
              <div className="text-[11px] uppercase text-[var(--muted-foreground)]">
                {module.track}
              </div>
              <div className="mt-1 text-sm font-medium text-[var(--foreground)]">
                {module.title}
              </div>
              <div className="mt-2 space-y-1.5">
                {module.labs.map((labId) => {
                  const lab = labsById.get(labId);
                  const active = selected?.labId === labId;
                  return (
                    <button
                      key={labId}
                      type="button"
                      onClick={() => lab && void handleSelect(lab)}
                      disabled={!lab}
                      className={`w-full rounded-md border px-2.5 py-2 text-left text-xs transition-colors ${
                        active
                          ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--foreground)]"
                          : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]"
                      }`}
                    >
                      <span className="block truncate">{lab?.title || labId}</span>
                      {lab && (
                        <span className="mt-0.5 block text-[10px] uppercase">
                          {lab.executionMode} · {lab.stage}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </section>
      </aside>

      <section className="flex min-h-0 flex-col">
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-[var(--foreground)]">
              {selected?.title || tr("选择一个 AI Infra Lab", "Select an AI Infra Lab")}
            </h2>
            <p className="mt-0.5 truncate text-xs text-[var(--muted-foreground)]">
              {selected?.symptom ||
                tr(
                  "Cognisphere 插件提供知识路径，AetherAI-Infra-Twin 执行实验并返回证据。",
                  "The Cognisphere plugin provides the learning path; AetherAI-Infra-Twin runs labs and returns evidence.",
                )}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              onClick={() => void handleRun()}
              disabled={!selected || running}
              className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-sm text-[var(--primary-foreground)] disabled:opacity-50"
            >
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {tr("运行 Lab", "Run Lab")}
            </button>
            {embedUrl && (
              <a
                href={embedUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--accent)]"
              >
                <ExternalLink className="h-4 w-4" />
                {tr("打开 Twin", "Open Twin")}
              </a>
            )}
          </div>
        </header>

        {lastRun && (
          <pre className="mx-4 mt-3 max-h-32 shrink-0 overflow-auto rounded-md border border-[var(--border)] bg-[var(--card)] p-3 text-xs text-[var(--muted-foreground)]">
            {JSON.stringify(lastRun, null, 2)}
          </pre>
        )}

        {selected && (
          <section className="mx-4 mt-3 shrink-0 rounded-lg border border-[var(--border)] p-3">
            <div className="grid grid-cols-4 gap-2">
              <LabFact label={tr("模式", "Mode")} value={selected.executionMode} />
              <LabFact label={tr("阶段", "Stage")} value={selected.stage} />
              <LabFact
                label={tr("成熟度", "Maturity")}
                value={selectedMaturity?.maturityLevel || tr("未标注", "Unlabeled")}
              />
              <LabFact
                label={tr("最近运行", "Latest run")}
                value={selectedLatestRun?.status || tr("未运行", "Not run")}
              />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <EvidenceList
                label={tr("必需证据", "Required evidence")}
                items={selected.requiredEvidence}
              />
              <EvidenceList
                label={tr("能力点", "Competencies")}
                items={selected.competencies}
              />
            </div>
            {selectedEvidence.length > 0 && (
              <div className="mt-3">
                <div className="mb-1.5 text-[11px] font-medium text-[var(--foreground)]">
                  {tr("最近证据", "Recent evidence")}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {selectedEvidence.map((item) => (
                    <div
                      key={item.runId}
                      className="min-w-0 rounded-md border border-[var(--border)] px-2.5 py-2"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-xs font-medium text-[var(--foreground)]">
                          {item.runId}
                        </span>
                        <span className="shrink-0 text-[10px] text-emerald-500">
                          {item.status}
                        </span>
                      </div>
                      <div className="mt-1 truncate text-[10px] text-[var(--muted-foreground)]">
                        {item.mode}
                        {item.createdAt ? ` · ${item.createdAt}` : ""}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="mt-3">
              <div className="mb-1.5 text-[11px] font-medium text-[var(--foreground)]">
                {tr("诊断选项", "Diagnosis choices")}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {selected.diagnosisChoices.map((choice) => (
                  <button
                    key={choice}
                    type="button"
                    onClick={() => void handleDiagnosis(choice)}
                    disabled={diagnosing}
                    className="rounded-md border border-[var(--border)] px-2.5 py-1.5 text-[11px] text-[var(--foreground)] hover:bg-[var(--accent)] disabled:opacity-50"
                  >
                    {choice}
                  </button>
                ))}
              </div>
              {diagnosisResult?.spec && (
                <div className="mt-2 rounded-md border border-[var(--border)] bg-[var(--card)] px-2.5 py-2">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="font-medium text-[var(--foreground)]">
                      {diagnosisResult.spec.passed ? tr("通过", "Passed") : tr("需复盘", "Review")}
                    </span>
                    <span className="text-[var(--muted-foreground)]">
                      {tr("分数", "Score")} {diagnosisResult.spec.score ?? "-"}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-[var(--muted-foreground)]">
                    {diagnosisResult.spec.feedback}
                  </p>
                </div>
              )}
            </div>
          </section>
        )}

        {priorityCoursePaths.length > 0 && (
          <section className="mx-4 mt-3 shrink-0 rounded-lg border border-[var(--border)] p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <BookOpenCheck className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" />
                <h3 className="truncate text-sm font-medium text-[var(--foreground)]">
                  {tr("优先标准学习流", "Priority standard learning flows")}
                </h3>
              </div>
              <span className="shrink-0 text-[11px] text-[var(--muted-foreground)]">
                {tr("路径", "paths")} {coursePaths.length} · {tr("单元", "units")} {expertUnits.length}
              </span>
            </div>

            <label className="mb-2 flex h-8 items-center gap-2 rounded-md border border-[var(--border)] px-2 text-[11px] text-[var(--muted-foreground)]">
              <Search className="h-3.5 w-3.5 shrink-0" />
              <input
                value={courseQuery}
                onChange={(event) => setCourseQuery(event.target.value)}
                placeholder={tr("搜索 19 条路径", "Search 19 paths")}
                className="min-w-0 flex-1 bg-transparent text-xs text-[var(--foreground)] outline-none placeholder:text-[var(--muted-foreground)]"
              />
            </label>

            <div className="grid max-h-28 grid-cols-4 gap-2 overflow-y-auto pr-1">
              {visibleCoursePaths.map((path, index) => {
                const active = selectedCourse?.course_path_id === path.course_path_id;
                const progress = getAiInfraCourseProgress(path, completedUnitIds);
                return (
                  <button
                    key={path.course_path_id || path.title}
                    type="button"
                    onClick={() => {
                      setSelectedCourseId(path.course_path_id || null);
                      setSelectedUnitId(path.unit_refs?.[0] || null);
                    }}
                    className={`min-w-0 rounded-md border p-2 text-left transition-colors ${
                      active
                        ? "border-[var(--primary)] bg-[var(--primary)]/10"
                        : "border-[var(--border)] hover:bg-[var(--accent)]"
                    }`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate text-xs font-medium text-[var(--foreground)]">
                        {path.title}
                      </span>
                      {index < 4 && (
                        <span className="shrink-0 text-[10px] text-[var(--muted-foreground)]">
                          P{index + 1}
                        </span>
                      )}
                    </span>
                    <span className="mt-1 block truncate text-[10px] uppercase text-[var(--muted-foreground)]">
                      {(path.levels || []).join(" · ")}
                    </span>
                    <span className="mt-1 block text-[10px] text-[var(--muted-foreground)]">
                      {tr("完成", "Done")} {progress.completed}/{progress.total} ·{" "}
                      {tr("Labs", "Labs")} {path.lab_refs?.length ?? 0}
                    </span>
                  </button>
                );
              })}
            </div>

            {selectedCourse && (
              <div className="mt-3 grid grid-cols-[minmax(170px,0.45fr)_minmax(0,1fr)] gap-3">
                <div className="min-w-0 rounded-md border border-[var(--border)] p-2">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-[11px] font-medium text-[var(--foreground)]">
                      {tr("层级", "Levels")}
                    </span>
                    <span className="text-[10px] text-[var(--muted-foreground)]">
                      {selectedCourseProgress.pct}%
                    </span>
                  </div>
                  <div className="mb-2 h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
                    <div
                      className="h-full rounded-full bg-[var(--primary)]"
                      style={{ width: `${selectedCourseProgress.pct}%` }}
                    />
                  </div>
                  <div className="space-y-1.5">
                    {selectedCourseUnits.map((unit) => {
                      const active = selectedUnit?.unit_id === unit.unit_id;
                      const done = Boolean(unit.unit_id && completedUnits[unit.unit_id]);
                      return (
                        <button
                          key={unit.unit_id || unit.title}
                          type="button"
                          onClick={() => setSelectedUnitId(unit.unit_id || null)}
                          className={`w-full rounded-md border px-2 py-1.5 text-left text-[11px] transition-colors ${
                            active
                              ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--foreground)]"
                              : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]"
                          }`}
                        >
                          <span className="flex items-center justify-between gap-2">
                            <span className="min-w-0 truncate uppercase">{unit.level || "unit"}</span>
                            {done && <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-500" />}
                          </span>
                          <span className="mt-0.5 block truncate">{unit.title}</span>
                        </button>
                      );
                    })}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {(selectedCourse.lab_refs || []).slice(0, 4).map((labId) => {
                      const lab = labsById.get(labId);
                      return (
                        <button
                          key={labId}
                          type="button"
                          disabled={!lab}
                          onClick={() => lab && void handleSelect(lab)}
                          className="max-w-full truncate rounded-md border border-[var(--border)] px-2 py-1 text-[10px] text-[var(--muted-foreground)] hover:bg-[var(--accent)] disabled:opacity-50"
                        >
                          {lab?.title || labId}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {selectedUnit && (
                  <div className="min-w-0 rounded-md border border-[var(--border)] p-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate text-xs font-medium text-[var(--foreground)]">
                          {selectedUnit.title}
                        </div>
                        <div className="mt-0.5 truncate text-[10px] text-[var(--muted-foreground)]">
                          {selectedUnit.level} · {selectedUnit.standard_learning?.estimated_minutes ?? "-"} min ·{" "}
                          {selectedUnit.review_status || "review_required"}
                        </div>
                      </div>
                      <span className="shrink-0 rounded-md border border-[var(--border)] px-2 py-1 text-[10px] text-[var(--muted-foreground)]">
                        {selectedUnit.topic_family_id}
                      </span>
                    </div>

                    <p className="mt-2 line-clamp-2 text-[11px] text-[var(--muted-foreground)]">
                      {selectedUnit.body || selectedUnit.summary}
                    </p>
                    {selectedCourse.capstone_task && (
                      <p className="mt-1 line-clamp-2 text-[10px] text-[var(--muted-foreground)]">
                        {tr("Capstone", "Capstone")}: {selectedCourse.capstone_task}
                      </p>
                    )}

                    <div className="mt-2 grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.9fr)] gap-2">
                      <div className="min-w-0">
                        <div className="mb-1 text-[10px] font-medium text-[var(--foreground)]">
                          {tr("学习步骤", "Learning steps")}
                        </div>
                        <div className="max-h-64 space-y-1 overflow-y-auto pr-1">
                          {(selectedUnit.standard_learning?.steps || []).map((step) => (
                            <div
                              key={`${selectedUnit.unit_id}:${step.phase}`}
                              className="rounded-md border border-[var(--border)] px-2 py-1"
                            >
                              <div className="text-[10px] uppercase text-[var(--muted-foreground)]">
                                {step.phase}
                              </div>
                              <div className="line-clamp-2 text-[11px] text-[var(--foreground)]">
                                {step.task}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="min-w-0">
                        <div className="mb-1 text-[10px] font-medium text-[var(--foreground)]">
                          {tr("测验与诊断", "Quiz and diagnosis")}
                        </div>
                        {selectedQuiz && (
                          <div className="rounded-md border border-[var(--border)] p-2">
                            <div className="line-clamp-2 text-[11px] text-[var(--foreground)]">
                              {selectedQuiz.prompt}
                            </div>
                            <div className="mt-1.5 grid grid-cols-2 gap-1">
                              {(selectedQuiz.choices || []).map((choice) => {
                                const chosen = selectedQuizAnswer === choice.id;
                                const correct = choice.id === selectedQuiz.answer;
                                return (
                                  <button
                                    key={choice.id || choice.text}
                                    type="button"
                                    onClick={() =>
                                      selectedQuiz.question_id &&
                                      setQuizAnswers((prev) => ({
                                        ...prev,
                                        [selectedQuiz.question_id as string]: choice.id || "",
                                      }))
                                    }
                                    className={`rounded-md border px-2 py-1 text-left text-[10px] transition-colors ${
                                      chosen
                                        ? correct
                                          ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-500"
                                          : "border-amber-500/50 bg-amber-500/10 text-amber-500"
                                        : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]"
                                    }`}
                                  >
                                    <span className="font-medium">{choice.id}</span> {choice.text}
                                  </button>
                                );
                              })}
                            </div>
                            {selectedQuizAnswer && (
                              <p className="mt-1.5 line-clamp-2 text-[10px] text-[var(--muted-foreground)]">
                                {selectedQuiz.rationale}
                              </p>
                            )}
                          </div>
                        )}
                        {selectedUnit.standard_learning?.assessment?.diagnosis_drills?.[0] && (
                          <div className="mt-1.5 rounded-md border border-[var(--border)] p-2">
                            <div className="line-clamp-1 text-[10px] uppercase text-[var(--muted-foreground)]">
                              {tr("诊断任务", "Diagnosis drill")}
                            </div>
                            <div className="mt-0.5 line-clamp-2 text-[11px] text-[var(--muted-foreground)]">
                              {selectedUnit.standard_learning.assessment.diagnosis_drills[0].scenario}
                            </div>
                            <div className="mt-0.5 line-clamp-2 text-[11px] text-[var(--foreground)]">
                              {selectedUnit.standard_learning.assessment.diagnosis_drills[0].task}
                            </div>
                            <ul className="mt-1 space-y-0.5">
                              {(selectedUnit.standard_learning.assessment.diagnosis_drills[0].rubric || [])
                                .slice(0, 3)
                                .map((item) => (
                                  <li
                                    key={item}
                                    className="line-clamp-1 text-[10px] text-[var(--muted-foreground)]"
                                  >
                                    {item}
                                  </li>
                                ))}
                            </ul>
                          </div>
                        )}
                      </div>

                      <div className="min-w-0">
                        <div className="mb-1 text-[10px] font-medium text-[var(--foreground)]">
                          {tr("反思与完成", "Reflect and complete")}
                        </div>
                        <textarea
                          value={selectedReflection}
                          onChange={(event) =>
                            selectedUnit.unit_id &&
                            setReflectionNotes((prev) => ({
                              ...prev,
                              [selectedUnit.unit_id as string]: event.target.value,
                            }))
                          }
                          placeholder={tr(
                            "写下可被当前证据支持的结论，以及还缺什么证明。",
                            "Write the claim supported by current evidence, and what proof is still missing.",
                          )}
                          className="h-24 w-full resize-none rounded-md border border-[var(--border)] bg-transparent p-2 text-[11px] text-[var(--foreground)] outline-none placeholder:text-[var(--muted-foreground)]"
                        />
                        <button
                          type="button"
                          disabled={!selectedUnit.unit_id || !selectedQuizCorrect}
                          onClick={() =>
                            selectedUnit.unit_id &&
                            setCompletedUnits((prev) => ({
                              ...prev,
                              [selectedUnit.unit_id as string]: true,
                            }))
                          }
                          className="mt-1.5 inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-[var(--primary)] px-2 py-1.5 text-[11px] text-[var(--primary-foreground)] disabled:opacity-50"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          {completedUnits[selectedUnit.unit_id || ""]
                            ? tr("已完成", "Completed")
                            : tr("标记完成", "Mark complete")}
                        </button>
                        <div className="mt-1 text-[10px] text-[var(--muted-foreground)]">
                          {selectedQuizCorrect
                            ? tr("测验已通过，可以完成该单元。", "Quiz passed. This unit can be completed.")
                            : tr("先完成测验，再记录学习完成。", "Pass the quiz before completing the unit.")}
                        </div>
                        <div className="mt-2 grid grid-cols-2 gap-1">
                          <EvidenceMiniList
                            label={tr("Lab 门禁", "Lab gates")}
                            items={
                              selectedUnit.standard_learning?.twin_practice?.pre_lab_gate || []
                            }
                          />
                          <EvidenceMiniList
                            label={tr("后置证据", "Post evidence")}
                            items={
                              selectedUnit.standard_learning?.twin_practice?.post_lab_evidence || []
                            }
                          />
                        </div>
                        {selectedUnitLabs.length > 0 && (
                          <div className="mt-2 space-y-1">
                            <div className="text-[10px] font-medium text-[var(--foreground)]">
                              {tr("关联 Twin Lab", "Linked Twin labs")}
                            </div>
                            {selectedUnitLabs.slice(0, 3).map((lab) => (
                              <button
                                key={lab.labId}
                                type="button"
                                disabled={!selectedQuizCorrect}
                                onClick={() => void handleSelect(lab)}
                                className="flex w-full items-center gap-1.5 rounded-md border border-[var(--border)] px-2 py-1 text-left text-[10px] text-[var(--muted-foreground)] hover:bg-[var(--accent)] disabled:opacity-50"
                                title={
                                  selectedQuizCorrect
                                    ? lab.title
                                    : tr("先通过测验再进入实验", "Pass the quiz before entering the lab")
                                }
                              >
                                <Play className="h-3 w-3 shrink-0" />
                                <span className="min-w-0 truncate">{lab.title}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {selectedUnit.source_ids && selectedUnit.source_ids.length > 0 && (
                      <div className="mt-2 truncate text-[10px] text-[var(--muted-foreground)]">
                        {tr("来源", "Sources")}: {selectedUnit.source_ids.slice(0, 4).join(" · ")}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {expertUnits.length > 0 && (
          <section className="mx-4 mt-3 shrink-0 rounded-lg border border-[var(--border)] p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <BookOpenCheck className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" />
                <h3 className="truncate text-sm font-medium text-[var(--foreground)]">
                  {tr("AI Infra 专家覆盖", "AI Infra expert coverage")}
                </h3>
              </div>
              <span className="shrink-0 text-[11px] text-[var(--muted-foreground)]">
                {expertUnits.length}/{knowledgeUnits.length}
              </span>
            </div>
            <div className="grid grid-cols-4 gap-2">
              {expertUnits.slice(0, 8).map((unit) => (
                <article
                  key={unit.unit_id || unit.title}
                  className="min-w-0 rounded-md border border-[var(--border)] p-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[10px] uppercase text-[var(--muted-foreground)]">
                      {unit.level || unit.topic_family_id || "unit"}
                    </span>
                    <span className="shrink-0 text-[10px] text-amber-500">
                      {unit.review_status ? tr("待复核", "review") : ""}
                    </span>
                  </div>
                  <div className="mt-1 line-clamp-2 text-xs font-medium text-[var(--foreground)]">
                    {unit.title}
                  </div>
                  <p className="mt-1 line-clamp-2 text-[11px] text-[var(--muted-foreground)]">
                    {unit.summary || unit.body}
                  </p>
                  {unit.standard_learning?.steps?.[0]?.task && (
                    <p className="mt-1 line-clamp-2 text-[10px] text-[var(--muted-foreground)]">
                      {unit.standard_learning.steps[0].task}
                    </p>
                  )}
                  {unit.source_ids && unit.source_ids.length > 0 && (
                    <div className="mt-1 truncate text-[10px] text-[var(--muted-foreground)]">
                      {unit.source_ids.slice(0, 2).join(" · ")}
                    </div>
                  )}
                </article>
              ))}
            </div>
          </section>
        )}

        {(lessonCards.length > 0 || knowledgeUnits.length > 0) && (
          <div className="mx-4 mt-3 grid max-h-48 shrink-0 grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-3 overflow-hidden">
            <section className="min-w-0 overflow-y-auto rounded-lg border border-[var(--border)] p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="text-sm font-medium text-[var(--foreground)]">
                  {tr("当前 Lab 学习卡片", "Current lab lesson cards")}
                </h3>
                <span className="text-[11px] text-[var(--muted-foreground)]">
                  {tr("关联", "linked")} {focusedContent.matchedLessonCount}/{lessonCards.length}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {lessonCards.slice(0, 6).map((lesson) => (
                  <article
                    key={lesson.lesson_id || lesson.title}
                    className="rounded-md border border-[var(--border)] p-2"
                  >
                    <div className="truncate text-xs font-medium text-[var(--foreground)]">
                      {lesson.title}
                    </div>
                    <p className="mt-1 line-clamp-2 text-[11px] text-[var(--muted-foreground)]">
                      {lesson.summary}
                    </p>
                    <div className="mt-1 truncate text-[10px] text-[var(--muted-foreground)]">
                      {(lesson.lab_refs || []).slice(0, 3).join(" · ")}
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="min-w-0 overflow-y-auto rounded-lg border border-[var(--border)] p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="text-sm font-medium text-[var(--foreground)]">
                  {tr("相关知识单元", "Related knowledge units")}
                </h3>
                <span className="text-[11px] text-[var(--muted-foreground)]">
                  {tr("关联", "linked")} {focusedContent.matchedKnowledgeCount}/{knowledgeUnits.length}
                </span>
              </div>
              <div className="space-y-2">
                {knowledgeUnits.slice(0, 8).map((unit) => (
                  <article key={unit.unit_id || unit.title} className="min-w-0">
                    <div className="truncate text-xs font-medium text-[var(--foreground)]">
                      {unit.title}
                    </div>
                    <p className="mt-0.5 line-clamp-2 text-[11px] text-[var(--muted-foreground)]">
                      {unit.body || unit.summary}
                    </p>
                  </article>
                ))}
              </div>
            </section>
          </div>
        )}

        <div className="min-h-0 flex-1 p-4">
          {embedUrl ? (
            <iframe
              title="AetherAI Infra Twin Lab Console"
              src={embedUrl}
              className="h-full w-full rounded-lg border border-[var(--border)] bg-white"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-[var(--muted-foreground)]">
              {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : tr("Twin 暂不可用", "Twin unavailable")}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-[var(--border)] p-2.5">
      <div className="text-[11px] text-[var(--muted-foreground)]">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums text-[var(--foreground)]">
        {value}
      </div>
    </div>
  );
}

function LabFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md border border-[var(--border)] px-2.5 py-2">
      <div className="text-[10px] text-[var(--muted-foreground)]">{label}</div>
      <div className="mt-1 truncate text-xs font-medium text-[var(--foreground)]">
        {value}
      </div>
    </div>
  );
}

function EvidenceList({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="min-w-0">
      <div className="mb-1.5 text-[11px] font-medium text-[var(--foreground)]">
        {label}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.slice(0, 6).map((item) => (
          <span
            key={item}
            className="max-w-full truncate rounded-full border border-[var(--border)] px-2 py-1 text-[10px] text-[var(--muted-foreground)]"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function workspaceStateFromServer(
  state: ServerAiInfraLearningWorkspaceState,
): AiInfraLearningWorkspaceState {
  return {
    selectedCourseId: state.selected_course_id || null,
    selectedUnitId: state.selected_unit_id || null,
    quizAnswers: state.quiz_answers || {},
    completedUnits: state.completed_units || {},
    reflectionNotes: state.reflection_notes || {},
  };
}

function workspaceStateToServer(
  state: AiInfraLearningWorkspaceState,
): ServerAiInfraLearningWorkspaceState {
  return {
    selected_course_id: state.selectedCourseId,
    selected_unit_id: state.selectedUnitId,
    quiz_answers: state.quizAnswers,
    completed_units: state.completedUnits,
    reflection_notes: state.reflectionNotes,
  };
}

function EvidenceMiniList({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="min-w-0 rounded-md border border-[var(--border)] p-1.5">
      <div className="mb-1 truncate text-[10px] font-medium text-[var(--foreground)]">
        {label}
      </div>
      <div className="space-y-0.5">
        {items.slice(0, 3).map((item) => (
          <div
            key={item}
            className="truncate text-[10px] text-[var(--muted-foreground)]"
            title={item}
          >
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}
