"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BookOpenCheck,
  CalendarClock,
  CheckCircle2,
  Cpu,
  ExternalLink,
  GraduationCap,
  ListChecks,
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
  assessAiInfraDiagnosisResponse,
  assessAiInfraSourceDocumentDrill,
  filterAiInfraCoursePaths,
  findAiInfraKnowledgeUnit,
  extractAiInfraPluginKnowledge,
  getAiInfraCourseContextStats,
  getAiInfraCourseProgress,
  getAiInfraCoverageSummary,
  getAiInfraImprovementRoadmap,
  getAiInfraImprovementRoadmapSummary,
  getAiInfraReviewQueue,
  getAiInfraReviewStageSummary,
  getAiInfraLearningModeView,
  getAiInfraSpacedReviewQueue,
  getAiInfraUnitMasteryState,
  getPriorityAiInfraCoursePaths,
  prioritizeAiInfraContent,
  type AiInfraLearningMode,
  type AiInfraReviewLedgerEntry,
} from "@/lib/ai-infra-learning-content";
import {
  runCognisphereHandshake,
  type HandshakeResult,
} from "@/lib/cognisphere-learning-api";
import { loadFromStorage, removeFromStorage, saveToStorage } from "@/lib/persistence";

const AI_INFRA_WORKSPACE_STORAGE_KEY = "ai_infra_learning_workspace_v1";
const AI_INFRA_WORKSPACE_ID = "default";

type AiInfraWorkspaceTab = "learn" | "labs" | "roadmap" | "review" | "sources";

interface AiInfraLearningWorkspaceState {
  selectedCourseId: string | null;
  selectedUnitId: string | null;
  assessmentMode: AiInfraLearningMode;
  quizAnswers: Record<string, string>;
  completedUnits: Record<string, boolean>;
  reflectionNotes: Record<string, string>;
  diagnosisNotes: Record<string, string>;
  sourceDocumentNotes: Record<string, string>;
  evidenceBundles: Record<string, string[]>;
  reviewLedger: Record<string, AiInfraReviewLedgerEntry>;
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
  const [activeTab, setActiveTab] = useState<AiInfraWorkspaceTab>("learn");
  const [assessmentMode, setAssessmentMode] = useState<AiInfraLearningMode>("learn");
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [courseQuery, setCourseQuery] = useState("");
  const [completedUnits, setCompletedUnits] = useState<Record<string, boolean>>({});
  const [reflectionNotes, setReflectionNotes] = useState<Record<string, string>>({});
  const [diagnosisNotes, setDiagnosisNotes] = useState<Record<string, string>>({});
  const [sourceDocumentNotes, setSourceDocumentNotes] = useState<Record<string, string>>({});
  const [evidenceBundles, setEvidenceBundles] = useState<Record<string, string[]>>({});
  const [reviewLedger, setReviewLedger] = useState<Record<string, AiInfraReviewLedgerEntry>>({});
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
        assessmentMode: "learn",
        quizAnswers: {},
        completedUnits: {},
        reflectionNotes: {},
        diagnosisNotes: {},
        sourceDocumentNotes: {},
        evidenceBundles: {},
        reviewLedger: {},
      },
    );
    setSelectedCourseId(stored.selectedCourseId);
    setSelectedUnitId(stored.selectedUnitId);
    setAssessmentMode(stored.assessmentMode || "learn");
    setQuizAnswers(stored.quizAnswers || {});
    setCompletedUnits(stored.completedUnits || {});
    setReflectionNotes(stored.reflectionNotes || {});
    setDiagnosisNotes(stored.diagnosisNotes || {});
    setSourceDocumentNotes(stored.sourceDocumentNotes || {});
    setEvidenceBundles(stored.evidenceBundles || {});
    setReviewLedger(stored.reviewLedger || {});
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
        setAssessmentMode(next.assessmentMode);
        setQuizAnswers(next.quizAnswers);
        setCompletedUnits(next.completedUnits);
        setReflectionNotes(next.reflectionNotes);
        setDiagnosisNotes(next.diagnosisNotes);
        setSourceDocumentNotes(next.sourceDocumentNotes);
        setEvidenceBundles(next.evidenceBundles);
        setReviewLedger(next.reviewLedger);
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
      assessmentMode,
      quizAnswers,
      completedUnits,
      reflectionNotes,
      diagnosisNotes,
      sourceDocumentNotes,
      evidenceBundles,
      reviewLedger,
    };
    saveToStorage<AiInfraLearningWorkspaceState>(AI_INFRA_WORKSPACE_STORAGE_KEY, state);
    void saveAiInfraLearningWorkspace(
      workspaceStateToServer(state),
      AI_INFRA_WORKSPACE_ID,
    )
      .then(() => setWorkspaceSyncState("synced"))
      .catch(() => setWorkspaceSyncState("offline"));
  }, [
    assessmentMode,
    completedUnits,
    diagnosisNotes,
    evidenceBundles,
    quizAnswers,
    reviewLedger,
    reflectionNotes,
    sourceDocumentNotes,
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
  const improvementRoadmap = useMemo(() => getAiInfraImprovementRoadmap(), []);
  const improvementSummary = useMemo(
    () => getAiInfraImprovementRoadmapSummary(improvementRoadmap),
    [improvementRoadmap],
  );
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
  const selectedUnitReviewStage = useMemo(
    () => getAiInfraReviewStageSummary(selectedUnit?.review_status),
    [selectedUnit?.review_status],
  );
  const learningModeView = useMemo(
    () => getAiInfraLearningModeView(assessmentMode),
    [assessmentMode],
  );
  const selectedQuiz = selectedUnit?.standard_learning?.assessment?.quiz?.[0];
  const selectedQuizAnswer = selectedQuiz?.question_id
    ? quizAnswers[selectedQuiz.question_id]
    : undefined;
  const selectedQuizCorrect = Boolean(
    selectedQuizAnswer && selectedQuizAnswer === selectedQuiz?.answer,
  );
  const selectedDiagnosisDrill =
    selectedUnit?.standard_learning?.assessment?.diagnosis_drills?.[0];
  const completedUnitIds = useMemo(
    () => new Set(Object.entries(completedUnits).filter(([, done]) => done).map(([unitId]) => unitId)),
    [completedUnits],
  );
  const selectedCourseProgress = useMemo(
    () => getAiInfraCourseProgress(selectedCourse, completedUnitIds),
    [completedUnitIds, selectedCourse],
  );
  const coverageSummary = useMemo(
    () => getAiInfraCoverageSummary(pluginKnowledge, completedUnitIds),
    [completedUnitIds, pluginKnowledge],
  );
  const selectedCourseContextStats = useMemo(
    () => getAiInfraCourseContextStats(pluginKnowledge, selectedCourse),
    [pluginKnowledge, selectedCourse],
  );
  const selectedReflection = selectedUnit?.unit_id
    ? reflectionNotes[selectedUnit.unit_id] || ""
    : "";
  const selectedDiagnosisNote = selectedUnit?.unit_id
    ? diagnosisNotes[selectedUnit.unit_id] || ""
    : "";
  const selectedDiagnosisAssessment = useMemo(
    () => assessAiInfraDiagnosisResponse(selectedDiagnosisDrill, selectedDiagnosisNote),
    [selectedDiagnosisDrill, selectedDiagnosisNote],
  );
  const selectedSourceDocumentNote = selectedUnit?.unit_id
    ? sourceDocumentNotes[selectedUnit.unit_id] || ""
    : "";
  const selectedSourceDocumentAssessment = useMemo(
    () => assessAiInfraSourceDocumentDrill(selectedUnit, selectedSourceDocumentNote),
    [selectedSourceDocumentNote, selectedUnit],
  );
  const selectedUnitEvidenceRefs = selectedUnit?.unit_id
    ? evidenceBundles[selectedUnit.unit_id] || []
    : [];
  const selectedUnitLabs = useMemo(() => {
    const labRefs = [
      ...(selectedUnit?.standard_learning?.twin_practice?.lab_refs || []),
      ...(selectedUnit?.lab_refs || []),
    ];
    return Array.from(new Set(labRefs))
      .map((labId) => labsById.get(labId))
      .filter((lab): lab is AiInfraLab => Boolean(lab));
  }, [labsById, selectedUnit]);
  const selectedUnitHasLabEvidence = useMemo(
    () => selectedUnitEvidenceRefs.length > 0,
    [selectedUnitEvidenceRefs.length],
  );
  const labEvidenceByUnitId = useMemo(() => {
    const result: Record<string, boolean> = {};
    for (const unit of selectedCourseUnits) {
      result[unit.unit_id || ""] = Boolean(unit.unit_id && evidenceBundles[unit.unit_id]?.length);
    }
    return result;
  }, [evidenceBundles, selectedCourseUnits]);
  const reviewQueue = useMemo(
    () =>
      getAiInfraReviewQueue({
        units: selectedCourseUnits,
        quizAnswers,
        completedUnits,
        reflectionNotes,
        diagnosisNotes,
        sourceDocumentNotes,
        labEvidenceByUnitId,
        limit: 4,
      }),
    [
      completedUnits,
      diagnosisNotes,
      labEvidenceByUnitId,
      quizAnswers,
      reflectionNotes,
      sourceDocumentNotes,
      selectedCourseUnits,
    ],
  );
  const spacedReviewQueue = useMemo(
    () =>
      getAiInfraSpacedReviewQueue({
        units: selectedCourseUnits,
        quizAnswers,
        completedUnits,
        reflectionNotes,
        diagnosisNotes,
        sourceDocumentNotes,
        labEvidenceByUnitId,
        reviewLedger,
        limit: 5,
      }),
    [
      completedUnits,
      diagnosisNotes,
      labEvidenceByUnitId,
      quizAnswers,
      reflectionNotes,
      reviewLedger,
      sourceDocumentNotes,
      selectedCourseUnits,
    ],
  );
  const selectedUnitMastery = useMemo(
    () =>
      getAiInfraUnitMasteryState({
        unit: selectedUnit,
        quizCorrect: selectedQuizCorrect,
        diagnosisPassed: selectedDiagnosisAssessment.passed,
        sourceDocumentPassed: selectedSourceDocumentAssessment.passed,
        diagnosisNote: selectedDiagnosisNote,
        reflectionNote: selectedReflection,
        hasLabEvidence: selectedUnitHasLabEvidence,
        completed: Boolean(selectedUnit?.unit_id && completedUnits[selectedUnit.unit_id]),
      }),
    [
      completedUnits,
      selectedDiagnosisNote,
      selectedDiagnosisAssessment.passed,
      selectedQuizCorrect,
      selectedReflection,
      selectedSourceDocumentAssessment.passed,
      selectedUnit,
      selectedUnitHasLabEvidence,
    ],
  );
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
  const selectedUnitEvidenceCandidates = useMemo(() => {
    const refs = new Map<string, { ref: string; label: string }>();
    for (const lab of selectedUnitLabs) {
      if (lab.latestRun?.runId) {
        refs.set(lab.latestRun.runId, {
          ref: lab.latestRun.runId,
          label: `${lab.title}: ${lab.latestRun.status}`,
        });
      }
    }
    for (const item of selectedEvidence) {
      refs.set(item.runId, {
        ref: item.runId,
        label: `${item.runId}: ${item.status}`,
      });
    }
    return Array.from(refs.values());
  }, [selectedEvidence, selectedUnitLabs]);

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
    setAssessmentMode("learn");
    setQuizAnswers({});
    setCompletedUnits({});
    setReflectionNotes({});
    setDiagnosisNotes({});
    setSourceDocumentNotes({});
    setEvidenceBundles({});
    setReviewLedger({});
  }, [priorityCoursePaths]);
  const workspaceTabs: { id: AiInfraWorkspaceTab; label: string }[] = [
    { id: "learn", label: tr("学习", "Learn") },
    { id: "labs", label: tr("实验", "Labs") },
    { id: "roadmap", label: tr("路线图", "Roadmap") },
    { id: "review", label: tr("复习", "Review") },
    { id: "sources", label: tr("来源", "Sources") },
  ];

  return (
    <main className="grid h-full min-h-0 grid-cols-[320px_minmax(0,1fr)] bg-[var(--background)]">
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

        {activeTab === "learn" && (
          <section className="mb-4 rounded-lg border border-[var(--border)] p-3">
            <div className="text-[11px] uppercase text-[var(--muted-foreground)]">
              {tr("学习焦点", "Learning focus")}
            </div>
            <div className="mt-1 text-sm font-medium text-[var(--foreground)]">
              {selectedCourse?.title || tr("选择课程路径", "Select a course path")}
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
              <div
                className="h-full rounded-full bg-[var(--primary)]"
                style={{ width: `${selectedCourseProgress.pct}%` }}
              />
            </div>
            <div className="mt-2 grid grid-cols-2 gap-1">
              <MiniStat label={tr("路径进度", "Path")} value={selectedCourseProgress.pct} />
              <MiniStat label={tr("掌握度", "Mastery")} value={selectedUnitMastery.scorePct} />
            </div>
            <div className="mt-2 rounded-md border border-[var(--border)] px-2 py-1 text-[10px] text-[var(--muted-foreground)]">
              {selectedUnitMastery.nextAction}
            </div>
          </section>
        )}

        {activeTab === "labs" && (
        <section className="mb-4 grid grid-cols-3 gap-2">
          <Metric label={tr("Labs", "Labs")} value={status?.summary?.counts?.labs ?? labs.length} />
          <Metric label={tr("证据", "Evidence")} value={status?.summary?.counts?.evidence ?? 0} />
          <Metric label={tr("场景", "Scenarios")} value={status?.summary?.counts?.scenarios ?? 0} />
        </section>
        )}

        {activeTab === "sources" && (
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
              {tr("覆盖摘要", "Coverage")}: {coverageSummary.domainCount} domains ·{" "}
              {coverageSummary.sourceCount} sources · {coverageSummary.candidateDocumentCount} docs
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
        )}

        {activeTab === "roadmap" && (
        <section className="mb-5 rounded-lg border border-[var(--border)] p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <ListChecks className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" />
              <h2 className="truncate text-sm font-medium text-[var(--foreground)]">
                {tr("专家整改路线图", "Expert improvement roadmap")}
              </h2>
            </div>
            <span className="shrink-0 text-[11px] text-[var(--muted-foreground)]">
              {improvementSummary.done}/{improvementSummary.total}
            </span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
            <div
              className="h-full rounded-full bg-[var(--primary)]"
              style={{ width: `${improvementSummary.donePct}%` }}
            />
          </div>
          <div className="mt-2 grid grid-cols-4 gap-1">
            <MiniStat label={tr("完成", "Done")} value={improvementSummary.done} />
            <MiniStat label={tr("进行中", "Active")} value={improvementSummary.inProgress} />
            <MiniStat label={tr("计划", "Planned")} value={improvementSummary.planned} />
            <MiniStat label={tr("阻塞", "Blocked")} value={improvementSummary.blocked} />
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {Object.entries(improvementSummary.byPriority).map(([priority, value]) => (
              <span
                key={priority}
                className="rounded-md border border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)]"
              >
                {priority} {value.done}/{value.total}
              </span>
            ))}
          </div>
          <div className="mt-2 space-y-1">
            {improvementSummary.nextTasks.map((task) => (
              <div
                key={task.id}
                className="rounded-md border border-[var(--border)] px-2 py-1"
                title={task.acceptance.join("\n")}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-[10px] font-medium text-[var(--foreground)]">
                    {task.priority} · {task.title}
                  </span>
                  <span
                    className={`shrink-0 text-[10px] ${
                      task.status === "in_progress" ? "text-amber-500" : "text-[var(--muted-foreground)]"
                    }`}
                  >
                    {task.status.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="mt-0.5 truncate text-[10px] text-[var(--muted-foreground)]">
                  {task.area} · {task.owner}
                </div>
              </div>
            ))}
          </div>
        </section>
        )}

        {activeTab === "labs" && (
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
        )}

        {activeTab === "labs" && (
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
        )}
      </aside>

      <section className="flex min-h-0 flex-col">
        <header className="shrink-0 border-b border-[var(--border)] px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold text-[var(--foreground)]">
                {activeTab === "learn"
                  ? selectedUnit?.title || tr("选择一个学习单元", "Select a learning unit")
                  : selected?.title || tr("选择一个 AI Infra Lab", "Select an AI Infra Lab")}
              </h2>
              <p className="mt-0.5 truncate text-xs text-[var(--muted-foreground)]">
                {activeTab === "learn"
                  ? selectedCourse?.title || tr("标准学习工作台", "Standard learning workspace")
                  : selected?.symptom ||
                    tr(
                      "Cognisphere 插件提供知识路径，AetherAI-Infra-Twin 执行实验并返回证据。",
                      "The Cognisphere plugin provides the learning path; AetherAI-Infra-Twin runs labs and returns evidence.",
                    )}
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              {activeTab === "labs" && (
                <button
                  type="button"
                  onClick={() => void handleRun()}
                  disabled={!selected || running}
                  className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-sm text-[var(--primary-foreground)] disabled:opacity-50"
                >
                  {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  {tr("运行 Lab", "Run Lab")}
                </button>
              )}
              {activeTab === "labs" && embedUrl && (
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
          </div>
          <div className="mt-3 grid grid-cols-5 gap-1">
            {workspaceTabs.map((tab) => {
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`rounded-md border px-2 py-1.5 text-xs transition-colors ${
                    active
                      ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--foreground)]"
                      : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </header>

        {activeTab === "labs" && lastRun && (
          <pre className="mx-4 mt-3 max-h-32 shrink-0 overflow-auto rounded-md border border-[var(--border)] bg-[var(--card)] p-3 text-xs text-[var(--muted-foreground)]">
            {JSON.stringify(lastRun, null, 2)}
          </pre>
        )}

        {activeTab === "labs" && selected && (
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

        {activeTab === "roadmap" && (
          <section className="mx-4 my-3 min-h-0 flex-1 overflow-y-auto rounded-lg border border-[var(--border)] p-3">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="min-w-0">
                <h3 className="truncate text-sm font-medium text-[var(--foreground)]">
                  {tr("专家评审整改计划", "Expert remediation plan")}
                </h3>
                <p className="mt-0.5 truncate text-[11px] text-[var(--muted-foreground)]">
                  {improvementRoadmap.positioning}
                </p>
              </div>
              <span className="shrink-0 rounded-md border border-[var(--border)] px-2 py-1 text-[11px] text-[var(--muted-foreground)]">
                {improvementRoadmap.version}
              </span>
            </div>
            <div className="mb-3 grid grid-cols-5 gap-2">
              {Object.entries(improvementSummary.byPriority).map(([priority, value]) => (
                <MiniStat key={priority} label={priority} value={value.done} />
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2">
              {improvementRoadmap.tasks.map((task) => (
                <article
                  key={task.id}
                  className="min-w-0 rounded-md border border-[var(--border)] p-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-xs font-medium text-[var(--foreground)]">
                      {task.priority} · {task.title}
                    </span>
                    <span
                      className={`shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] ${
                        task.status === "done"
                          ? "border-emerald-500/40 text-emerald-500"
                          : task.status === "in_progress"
                            ? "border-amber-500/40 text-amber-500"
                            : "border-[var(--border)] text-[var(--muted-foreground)]"
                      }`}
                    >
                      {task.status.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div className="mt-1 truncate text-[10px] text-[var(--muted-foreground)]">
                    {task.area} · {task.owner}
                  </div>
                  <ul className="mt-1 space-y-0.5">
                    {task.acceptance.slice(0, 2).map((item) => (
                      <li key={item} className="line-clamp-1 text-[10px] text-[var(--muted-foreground)]">
                        {item}
                      </li>
                    ))}
                  </ul>
                  {task.evidence.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {task.evidence.map((item) => (
                        <span
                          key={item}
                          className="rounded-md border border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)]"
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  )}
                </article>
              ))}
            </div>
          </section>
        )}

        {activeTab === "review" && (
          <section className="mx-4 my-3 min-h-0 flex-1 overflow-y-auto rounded-lg border border-[var(--border)] p-3">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-sm font-medium text-[var(--foreground)]">
                {tr("复习工作台", "Review workspace")}
              </h3>
              <span className="text-[11px] text-[var(--muted-foreground)]">
                {reviewQueue.length + spacedReviewQueue.length} {tr("项", "items")}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <section className="min-w-0 rounded-md border border-[var(--border)] p-2">
                <div className="mb-2 text-xs font-medium text-[var(--foreground)]">
                  {tr("薄弱项", "Weakest units")}
                </div>
                <div className="space-y-1">
                  {reviewQueue.map((item) => (
                    <button
                      key={item.unit.unit_id || item.unit.title}
                      type="button"
                      onClick={() => {
                        setActiveTab("learn");
                        setSelectedUnitId(item.unit.unit_id || null);
                      }}
                      className="w-full rounded-md border border-[var(--border)] px-2 py-1.5 text-left hover:bg-[var(--accent)]"
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="min-w-0 truncate text-xs font-medium text-[var(--foreground)]">
                          {item.unit.title}
                        </span>
                        <span className="shrink-0 text-[10px] tabular-nums text-[var(--muted-foreground)]">
                          {item.mastery.scorePct}%
                        </span>
                      </span>
                      <span className="mt-0.5 block truncate text-[10px] text-[var(--muted-foreground)]">
                        {item.mastery.nextAction}
                      </span>
                    </button>
                  ))}
                </div>
              </section>
              <section className="min-w-0 rounded-md border border-[var(--border)] p-2">
                <div className="mb-2 text-xs font-medium text-[var(--foreground)]">
                  {tr("间隔复习", "Spaced review")}
                </div>
                <div className="space-y-1">
                  {spacedReviewQueue.map((item) => (
                    <button
                      key={item.unit.unit_id || item.unit.title}
                      type="button"
                      onClick={() => {
                        setActiveTab("learn");
                        setSelectedUnitId(item.unit.unit_id || null);
                      }}
                      className="w-full rounded-md border border-[var(--border)] px-2 py-1.5 text-left hover:bg-[var(--accent)]"
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="min-w-0 truncate text-xs font-medium text-[var(--foreground)]">
                          {item.unit.title}
                        </span>
                        <span className="shrink-0 text-[10px] text-amber-500">
                          {item.dueLabel}
                        </span>
                      </span>
                      <span className="mt-0.5 block truncate text-[10px] text-[var(--muted-foreground)]">
                        {item.reason}
                      </span>
                    </button>
                  ))}
                </div>
              </section>
            </div>
          </section>
        )}

        {activeTab === "learn" && priorityCoursePaths.length > 0 && (
          <section className="mx-4 my-3 min-h-0 flex-1 overflow-y-auto rounded-lg border border-[var(--border)] p-3">
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
            <div className="mb-2 grid grid-cols-7 gap-1">
              <MiniStat label={tr("课程", "Courses")} value={coverageSummary.courseCount} />
              <MiniStat label={tr("单元", "Units")} value={coverageSummary.unitCount} />
              <MiniStat label={tr("已完成", "Done")} value={coverageSummary.completedUnitCount} />
              <MiniStat label={tr("Labs", "Labs")} value={coverageSummary.labCount} />
              <MiniStat label={tr("文档", "Docs")} value={coverageSummary.candidateDocumentCount} />
              <MiniStat label={tr("故障", "Failures")} value={coverageSummary.failureModeCount} />
              <MiniStat label={tr("证据", "Evidence")} value={coverageSummary.evidenceRequirementCount} />
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
                  <div className="mb-2 grid grid-cols-3 gap-1">
                    <MiniStat label={tr("来源", "Sources")} value={selectedCourseContextStats.sourceCount} />
                    <MiniStat label={tr("文档", "Docs")} value={selectedCourseContextStats.candidateDocumentCount} />
                    <MiniStat label={tr("证据", "Evidence")} value={selectedCourseContextStats.evidenceRequirementCount} />
                  </div>
                  {reviewQueue.length > 0 && (
                    <div className="mb-2 rounded-md border border-[var(--border)] p-2">
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <span className="text-[10px] font-medium text-[var(--foreground)]">
                          {tr("个性化复习", "Personalized review")}
                        </span>
                        <span className="text-[10px] text-[var(--muted-foreground)]">
                          {reviewQueue.length}
                        </span>
                      </div>
                      <div className="space-y-1">
                        {reviewQueue.map((item) => (
                          <button
                            key={item.unit.unit_id || item.unit.title}
                            type="button"
                            onClick={() => setSelectedUnitId(item.unit.unit_id || null)}
                            className="w-full rounded-md border border-[var(--border)] px-2 py-1 text-left hover:bg-[var(--accent)]"
                            title={item.mastery.nextAction}
                          >
                            <span className="flex items-center justify-between gap-2">
                              <span className="min-w-0 truncate text-[10px] font-medium text-[var(--foreground)]">
                                {item.unit.title}
                              </span>
                              <span className="shrink-0 text-[10px] tabular-nums text-[var(--muted-foreground)]">
                                {item.mastery.scorePct}%
                              </span>
                            </span>
                            <span className="mt-0.5 block truncate text-[10px] text-[var(--muted-foreground)]">
                              {item.mastery.nextAction}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {spacedReviewQueue.length > 0 && (
                    <div className="mb-2 rounded-md border border-[var(--border)] p-2">
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <span className="inline-flex min-w-0 items-center gap-1 text-[10px] font-medium text-[var(--foreground)]">
                          <CalendarClock className="h-3 w-3 shrink-0" />
                          {tr("间隔复习", "Spaced review")}
                        </span>
                        <span className="text-[10px] text-[var(--muted-foreground)]">
                          {spacedReviewQueue.filter((item) => item.dueStatus === "due").length}{" "}
                          {tr("到期", "due")}
                        </span>
                      </div>
                      <div className="space-y-1">
                        {spacedReviewQueue.map((item) => (
                          <div
                            key={item.unit.unit_id || item.unit.title}
                            className="rounded-md border border-[var(--border)] px-2 py-1"
                          >
                            <button
                              type="button"
                              onClick={() => setSelectedUnitId(item.unit.unit_id || null)}
                              className="w-full text-left"
                              title={item.reason}
                            >
                              <span className="flex items-center justify-between gap-2">
                                <span className="min-w-0 truncate text-[10px] font-medium text-[var(--foreground)]">
                                  {item.unit.title}
                                </span>
                                <span
                                  className={`shrink-0 text-[10px] tabular-nums ${
                                    item.dueStatus === "due"
                                      ? "text-amber-500"
                                      : "text-[var(--muted-foreground)]"
                                  }`}
                                >
                                  {item.dueLabel}
                                </span>
                              </span>
                              <span className="mt-0.5 block truncate text-[10px] text-[var(--muted-foreground)]">
                                {item.reason}
                              </span>
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                item.unit.unit_id &&
                                setReviewLedger((prev) => ({
                                  ...prev,
                                  [item.unit.unit_id as string]: {
                                    ...(prev[item.unit.unit_id as string] || {}),
                                    lastReviewedAt: new Date().toISOString(),
                                  },
                                }))
                              }
                              className="mt-1 rounded-md border border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)] hover:bg-[var(--accent)]"
                            >
                              {tr("记录复习", "Mark reviewed")}
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
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
                  {selectedCourse.source_ids && selectedCourse.source_ids.length > 0 && (
                    <div className="mt-2">
                      <div className="mb-1 text-[10px] font-medium text-[var(--foreground)]">
                        {tr("课程来源", "Course sources")}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {selectedCourse.source_ids.slice(0, 6).map((sourceId) => (
                          <span
                            key={sourceId}
                            className="max-w-full truncate rounded-md border border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)]"
                            title={sourceId}
                          >
                            {sourceId.replace("src:ai-infra:", "")}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
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
                          {selectedUnit.standard_learning?.learning_mode || "standard"} ·{" "}
                          {selectedUnitReviewStage.displayLabel}
                        </div>
                      </div>
                      <span
                        className={`shrink-0 rounded-md border px-2 py-1 text-[10px] ${
                          selectedUnitReviewStage.approved
                            ? "border-emerald-500/40 text-emerald-500"
                            : "border-amber-500/40 text-amber-500"
                        }`}
                        title={selectedUnitReviewStage.requiredApprovals.join(", ")}
                      >
                        {selectedUnitReviewStage.approved
                          ? tr("已批准", "approved")
                          : tr("待三审", "3 reviews")}
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
                    <div className="mt-2 rounded-md border border-[var(--border)] p-2">
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <span className="text-[10px] font-medium text-[var(--foreground)]">
                          {tr("学习模式", "Learning mode")}
                        </span>
                        <span className="truncate text-[10px] text-[var(--muted-foreground)]">
                          {learningModeView.prompt}
                        </span>
                      </div>
                      <div className="grid grid-cols-5 gap-1">
                        {[
                          "learn",
                          "guided_practice",
                          "independent_lab",
                          "incident_challenge",
                          "capstone",
                        ].map((mode) => {
                          const view = getAiInfraLearningModeView(mode);
                          const active = learningModeView.mode === view.mode;
                          return (
                            <button
                              key={view.mode}
                              type="button"
                              onClick={() => setAssessmentMode(view.mode)}
                              className={`min-w-0 rounded-md border px-1.5 py-1 text-[10px] transition-colors ${
                                active
                                  ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--foreground)]"
                                  : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]"
                              }`}
                              title={view.prompt}
                            >
                              <span className="block truncate">{view.label}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                    {selectedUnit.standard_learning?.prerequisites &&
                      selectedUnit.standard_learning.prerequisites.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {selectedUnit.standard_learning.prerequisites.slice(0, 6).map((item) => (
                            <span
                              key={item}
                              className="max-w-full truncate rounded-md border border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)]"
                              title={item}
                            >
                              {item}
                            </span>
                          ))}
                        </div>
                      )}
                    <div className="mt-2 rounded-md border border-[var(--border)] p-2">
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <div className="truncate text-[10px] font-medium text-[var(--foreground)]">
                            {tr("单元掌握度", "Unit mastery")}
                          </div>
                          <div className="mt-0.5 truncate text-[10px] text-[var(--muted-foreground)]">
                            {tr("下一步", "Next")}: {selectedUnitMastery.nextAction}
                          </div>
                        </div>
                        <div className="shrink-0 text-right">
                          <div className="text-sm font-semibold tabular-nums text-[var(--foreground)]">
                            {selectedUnitMastery.scorePct}%
                          </div>
                          <div className="text-[10px] text-[var(--muted-foreground)]">
                            {selectedUnitMastery.level.replace(/_/g, " ")}
                          </div>
                        </div>
                      </div>
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
                        <div
                          className="h-full rounded-full bg-[var(--primary)]"
                          style={{ width: `${selectedUnitMastery.scorePct}%` }}
                        />
                      </div>
                      <div className="mt-2 grid grid-cols-5 gap-1">
                        {selectedUnitMastery.checks.map((check) => (
                          <div
                            key={check.id}
                            className={`min-w-0 rounded-md border px-1.5 py-1 ${
                              check.done
                                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-500"
                                : "border-[var(--border)] text-[var(--muted-foreground)]"
                            }`}
                            title={check.label}
                          >
                            <div className="truncate text-[10px]">{check.label}</div>
                          </div>
                        ))}
                      </div>
                    </div>

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
                            {learningModeView.showDiagnosisRubric && (
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
                            )}
                            {learningModeView.showExpectedClaimShape &&
                              selectedUnit.standard_learning.assessment.diagnosis_drills[0]
                              .expected_claim_shape && (
                              <div className="mt-1 grid grid-cols-2 gap-1">
                                {Object.entries(
                                  selectedUnit.standard_learning.assessment.diagnosis_drills[0]
                                    .expected_claim_shape || {},
                                )
                                  .slice(0, 4)
                                  .map(([key, value]) => (
                                    <div
                                      key={key}
                                      className="min-w-0 rounded-md border border-[var(--border)] px-1.5 py-1"
                                      title={`${key}: ${String(value)}`}
                                    >
                                      <div className="truncate text-[10px] uppercase text-[var(--muted-foreground)]">
                                        {key}
                                      </div>
                                      <div className="truncate text-[10px] text-[var(--foreground)]">
                                        {String(value)}
                                      </div>
                                    </div>
                                  ))}
                              </div>
                            )}
                            <textarea
                              value={selectedDiagnosisNote}
                              onChange={(event) =>
                                selectedUnit.unit_id &&
                                setDiagnosisNotes((prev) => ({
                                  ...prev,
                                  [selectedUnit.unit_id as string]: event.target.value,
                                }))
                              }
                              placeholder={tr(
                                "按 symptom / evidence / claim strength / missing proof 写诊断结论。",
                                "Write the diagnosis as symptom / evidence / claim strength / missing proof.",
                              )}
                              className="mt-1.5 h-16 w-full resize-none rounded-md border border-[var(--border)] bg-transparent p-2 text-[10px] text-[var(--foreground)] outline-none placeholder:text-[var(--muted-foreground)]"
                            />
                            <div className="mt-1 flex items-center justify-between gap-2 text-[10px]">
                              <span
                                className={
                                  selectedDiagnosisAssessment.passed
                                    ? "text-emerald-500"
                                    : "text-amber-500"
                                }
                              >
                                {tr("诊断评分", "Diagnosis score")}{" "}
                                {selectedDiagnosisAssessment.scorePct}%
                              </span>
                              <span className="truncate text-[var(--muted-foreground)]">
                                {selectedDiagnosisAssessment.feedback}
                              </span>
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="min-w-0">
                        <div className="mb-1 text-[10px] font-medium text-[var(--foreground)]">
                          {tr("反思与完成", "Reflect and complete")}
                        </div>
                        {selectedUnit.standard_learning?.assessment?.reflection_prompts &&
                          selectedUnit.standard_learning.assessment.reflection_prompts.length > 0 && (
                            <div className="mb-1 space-y-0.5">
                              {selectedUnit.standard_learning.assessment.reflection_prompts
                                .slice(0, 2)
                                .map((prompt) => (
                                  <div
                                    key={prompt}
                                    className="line-clamp-1 text-[10px] text-[var(--muted-foreground)]"
                                    title={prompt}
                                  >
                                    {prompt}
                                  </div>
                                ))}
                            </div>
                          )}
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
                          disabled={
                            !selectedUnit.unit_id ||
                            !selectedQuizCorrect ||
                            Boolean(selectedDiagnosisDrill && !selectedDiagnosisAssessment.passed) ||
                            Boolean(
                              learningModeView.showTrustedDocuments &&
                              selectedUnit.candidate_documents?.length &&
                                !selectedSourceDocumentAssessment.passed,
                            ) ||
                            Boolean(selectedUnitLabs.length && selectedUnitEvidenceRefs.length === 0) ||
                            selectedReflection.trim().length < 20
                          }
                          onClick={() =>
                            selectedUnit.unit_id &&
                            (() => {
                              const unitId = selectedUnit.unit_id as string;
                              const completedAt = new Date().toISOString();
                              setCompletedUnits((prev) => ({
                                ...prev,
                                [unitId]: true,
                              }));
                              setReviewLedger((prev) => ({
                                ...prev,
                                [unitId]: {
                                  ...(prev[unitId] || {}),
                                  completedAt: prev[unitId]?.completedAt || completedAt,
                                },
                              }));
                            })()
                          }
                          className="mt-1.5 inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-[var(--primary)] px-2 py-1.5 text-[11px] text-[var(--primary-foreground)] disabled:opacity-50"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          {completedUnits[selectedUnit.unit_id || ""]
                            ? tr("已完成", "Completed")
                            : tr("标记完成", "Mark complete")}
                        </button>
                        <div className="mt-1 text-[10px] text-[var(--muted-foreground)]">
                          {selectedUnitMastery.nextAction}
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
                        <div className="mt-2 rounded-md border border-[var(--border)] p-2">
                          <div className="mb-1 flex items-center justify-between gap-2">
                            <span className="text-[10px] font-medium text-[var(--foreground)]">
                              {tr("证据包", "Evidence Bundle")}
                            </span>
                            <span
                              className={
                                selectedUnitEvidenceRefs.length > 0
                                  ? "text-[10px] text-emerald-500"
                                  : "text-[10px] text-amber-500"
                              }
                            >
                              {selectedUnitEvidenceRefs.length}
                            </span>
                          </div>
                          {selectedUnitEvidenceRefs.length > 0 && (
                            <div className="mb-1 flex flex-wrap gap-1">
                              {selectedUnitEvidenceRefs.map((ref) => (
                                <button
                                  key={ref}
                                  type="button"
                                  onClick={() =>
                                    selectedUnit.unit_id &&
                                    setEvidenceBundles((prev) => ({
                                      ...prev,
                                      [selectedUnit.unit_id as string]: (
                                        prev[selectedUnit.unit_id as string] || []
                                      ).filter((item) => item !== ref),
                                    }))
                                  }
                                  className="max-w-full truncate rounded-md border border-emerald-500/40 px-1.5 py-0.5 text-[10px] text-emerald-500"
                                  title={tr("点击移除", "Click to remove")}
                                >
                                  {ref}
                                </button>
                              ))}
                            </div>
                          )}
                          <div className="flex flex-wrap gap-1">
                            {selectedUnitEvidenceCandidates.slice(0, 5).map((candidate) => {
                              const attached = selectedUnitEvidenceRefs.includes(candidate.ref);
                              return (
                                <button
                                  key={candidate.ref}
                                  type="button"
                                  disabled={attached}
                                  onClick={() =>
                                    selectedUnit.unit_id &&
                                    setEvidenceBundles((prev) => ({
                                      ...prev,
                                      [selectedUnit.unit_id as string]: Array.from(
                                        new Set([
                                          ...(prev[selectedUnit.unit_id as string] || []),
                                          candidate.ref,
                                        ]),
                                      ),
                                    }))
                                  }
                                  className="max-w-full truncate rounded-md border border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)] hover:bg-[var(--accent)] disabled:opacity-50"
                                  title={candidate.label}
                                >
                                  {attached ? tr("已绑定", "Bound") : tr("绑定", "Bind")}{" "}
                                  {candidate.ref}
                                </button>
                              );
                            })}
                          </div>
                          {selectedUnitEvidenceCandidates.length === 0 && (
                            <div className="text-[10px] text-[var(--muted-foreground)]">
                              {tr("运行关联 Twin Lab 后可绑定证据。", "Run a linked Twin lab before binding evidence.")}
                            </div>
                          )}
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

                        {learningModeView.showTrustedDocuments &&
                          selectedUnit.source_ids && selectedUnit.source_ids.length > 0 && (
                          <div className="mt-2 truncate text-[10px] text-[var(--muted-foreground)]">
                            {tr("来源", "Sources")}: {selectedUnit.source_ids.slice(0, 4).join(" · ")}
                          </div>
                        )}
                    <div className="mt-2 grid grid-cols-4 gap-2">
                      {learningModeView.showConcepts && (
                        <EvidenceMiniList
                          label={tr("概念", "Concepts")}
                          items={selectedUnit.concepts || []}
                        />
                      )}
                      {learningModeView.showFailureModes && (
                        <EvidenceMiniList
                          label={tr("故障模式", "Failure modes")}
                          items={selectedUnit.failure_modes || []}
                        />
                      )}
                      {learningModeView.showEvidenceRequirements && (
                        <EvidenceMiniList
                          label={tr("证据要求", "Evidence required")}
                          items={selectedUnit.evidence_requirements || []}
                        />
                      )}
                      {learningModeView.showClaimBoundaries && (
                        <EvidenceMiniList
                          label={tr("主张边界", "Claim boundaries")}
                          items={selectedUnit.claim_boundaries || []}
                        />
                      )}
                    </div>
                    {!learningModeView.showFailureModes && (
                      <div className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-[10px] text-amber-500">
                        {tr(
                          "当前模式已隐藏故障模式、证据清单或边界提示，请基于任务、运行结果和可用文档独立判断。",
                          "This mode hides failure, evidence, or boundary hints. Diagnose from the task, runs, and available documents.",
                        )}
                      </div>
                    )}
                    {learningModeView.showTrustedDocuments &&
                      selectedUnit.candidate_documents && selectedUnit.candidate_documents.length > 0 && (
                      <div className="mt-2 rounded-md border border-[var(--border)] p-2">
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <span className="text-[10px] font-medium text-[var(--foreground)]">
                            {tr("可信来源 Drill", "Trusted source drill")}
                          </span>
                          <span className="text-[10px] text-[var(--muted-foreground)]">
                            {selectedSourceDocumentAssessment.scorePct}%
                          </span>
                        </div>
                        <div className="grid max-h-20 grid-cols-2 gap-1 overflow-y-auto pr-1">
                          {selectedUnit.candidate_documents.slice(0, 8).map((doc) => (
                            <div
                              key={doc.document_id || `${doc.source_id}:${doc.relative_path}`}
                              className="min-w-0 rounded-md border border-[var(--border)] px-2 py-1"
                              title={[
                                doc.document_id,
                                doc.relative_path,
                                doc.sha256 ? `sha256:${doc.sha256}` : "",
                              ]
                                .filter(Boolean)
                                .join("\n")}
                            >
                              <div className="truncate text-[10px] font-medium text-[var(--foreground)]">
                                {doc.title || doc.relative_path || doc.document_id}
                              </div>
                              <div className="truncate text-[10px] text-[var(--muted-foreground)]">
                                {doc.source_id?.replace("src:ai-infra:", "") || doc.document_id}
                              </div>
                            </div>
                          ))}
                        </div>
                        <textarea
                          value={selectedSourceDocumentNote}
                          onChange={(event) =>
                            selectedUnit.unit_id &&
                            setSourceDocumentNotes((prev) => ({
                              ...prev,
                              [selectedUnit.unit_id as string]: event.target.value,
                            }))
                          }
                          placeholder={tr(
                            "引用至少一个可信文档，并说明它支持哪项证据要求和主张边界。",
                            "Reference at least one trusted document and tie it to evidence requirements and claim boundaries.",
                          )}
                          className="mt-1.5 h-16 w-full resize-none rounded-md border border-[var(--border)] bg-transparent p-2 text-[10px] text-[var(--foreground)] outline-none placeholder:text-[var(--muted-foreground)]"
                        />
                        <div className="mt-1 flex items-center justify-between gap-2 text-[10px]">
                          <span
                            className={
                              selectedSourceDocumentAssessment.passed
                                ? "text-emerald-500"
                                : "text-amber-500"
                            }
                          >
                            {selectedSourceDocumentAssessment.passed
                              ? tr("来源通过", "Source passed")
                              : tr("来源待补", "Source pending")}
                          </span>
                          <span className="truncate text-[var(--muted-foreground)]">
                            {selectedSourceDocumentAssessment.feedback}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {activeTab === "sources" && expertUnits.length > 0 && (
          <section className="mx-4 mt-3 shrink-0 rounded-lg border border-[var(--border)] p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <BookOpenCheck className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" />
                <h3 className="truncate text-sm font-medium text-[var(--foreground)]">
                  {tr("AI Infra 高阶草案覆盖", "AI Infra advanced draft coverage")}
                </h3>
              </div>
              <span className="shrink-0 text-[11px] text-[var(--muted-foreground)]">
                {expertUnits.length}/{knowledgeUnits.length}
              </span>
            </div>
            <div className="grid grid-cols-4 gap-2">
              {expertUnits.slice(0, 8).map((unit) => {
                const stage = getAiInfraReviewStageSummary(unit.review_status);
                return (
                  <article
                    key={unit.unit_id || unit.title}
                    className="min-w-0 rounded-md border border-[var(--border)] p-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-[10px] uppercase text-[var(--muted-foreground)]">
                        {unit.level || unit.topic_family_id || "unit"}
                      </span>
                      <span
                        className={`shrink-0 text-[10px] ${
                          stage.approved ? "text-emerald-500" : "text-amber-500"
                        }`}
                        title={stage.requiredApprovals.join(", ")}
                      >
                        {stage.displayLabel}
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
                );
              })}
            </div>
          </section>
        )}

        {activeTab === "sources" && (lessonCards.length > 0 || knowledgeUnits.length > 0) && (
          <div className="mx-4 my-3 grid min-h-0 flex-1 grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-3 overflow-hidden">
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

        {activeTab === "labs" && (
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
        )}
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

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-0 rounded-md border border-[var(--border)] px-1.5 py-1">
      <div className="truncate text-[10px] text-[var(--muted-foreground)]">{label}</div>
      <div className="text-xs font-medium tabular-nums text-[var(--foreground)]">
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
    assessmentMode: getAiInfraLearningModeView(state.assessment_mode).mode,
    quizAnswers: state.quiz_answers || {},
    completedUnits: state.completed_units || {},
    reflectionNotes: state.reflection_notes || {},
    diagnosisNotes: state.diagnosis_notes || {},
    sourceDocumentNotes: state.source_document_notes || {},
    evidenceBundles: state.evidence_bundles || {},
    reviewLedger: state.review_ledger || {},
  };
}

function workspaceStateToServer(
  state: AiInfraLearningWorkspaceState,
): ServerAiInfraLearningWorkspaceState {
  return {
    selected_course_id: state.selectedCourseId,
    selected_unit_id: state.selectedUnitId,
    assessment_mode: state.assessmentMode,
    quiz_answers: state.quizAnswers,
    completed_units: state.completedUnits,
    reflection_notes: state.reflectionNotes,
    diagnosis_notes: state.diagnosisNotes,
    source_document_notes: state.sourceDocumentNotes,
    evidence_bundles: state.evidenceBundles,
    review_ledger: state.reviewLedger,
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
