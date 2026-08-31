import type { AiInfraLab } from "./ai-infra-twin-api";
import type { HandshakeResult } from "./cognisphere-learning-api";

export interface AiInfraLessonCard {
  lesson_id?: string;
  track_id?: string;
  title?: string;
  summary?: string;
  outcomes?: string[];
  lab_refs?: string[];
  unit_refs?: string[];
}

export interface AiInfraKnowledgeUnitCard {
  unit_id?: string;
  title?: string;
  level?: string;
  domain?: string;
  body?: string;
  summary?: string;
  teaching_points?: string[];
  topic_family_id?: string;
  source_ids?: string[];
  candidate_documents?: AiInfraCandidateDocument[];
  concepts?: string[];
  failure_modes?: string[];
  evidence_requirements?: string[];
  lab_refs?: string[];
  claim_boundaries?: string[];
  review_status?: string;
  standard_learning?: {
    estimated_minutes?: number;
    learning_mode?: string;
    prerequisites?: string[];
    steps?: { phase?: string; task?: string }[];
    assessment?: {
      quiz?: AiInfraQuizQuestion[];
      diagnosis_drills?: AiInfraDiagnosisDrill[];
      reflection_prompts?: string[];
    };
    twin_practice?: {
      pre_lab_gate?: string[];
      lab_refs?: string[];
      post_lab_evidence?: string[];
    };
  };
}

export interface AiInfraCandidateDocument {
  document_id?: string;
  source_id?: string;
  title?: string;
  relative_path?: string;
  sha256?: string;
}

export interface AiInfraQuizQuestion {
  question_id?: string;
  type?: string;
  prompt?: string;
  choices?: { id?: string; text?: string }[];
  answer?: string;
  rationale?: string;
}

export interface AiInfraDiagnosisDrill {
  drill_id?: string;
  scenario?: string;
  task?: string;
  expected_claim_shape?: Record<string, unknown>;
  rubric?: string[];
}

export interface AiInfraCoursePath {
  course_path_id?: string;
  title?: string;
  domain?: string;
  levels?: string[];
  unit_refs?: string[];
  lab_refs?: string[];
  source_ids?: string[];
  capstone_task?: string;
  review_status?: string;
}

export interface AiInfraPluginKnowledge {
  pack_metadata?: { title?: string; version?: string };
  tracks?: unknown[];
  learning_surface?: {
    lesson_cards?: AiInfraLessonCard[];
    knowledge_unit_cards?: AiInfraKnowledgeUnitCard[];
    trusted_source_coverage?: AiInfraPluginKnowledge["trusted_source_coverage"];
    standard_learning_assets?: AiInfraPluginKnowledge["standard_learning_assets"];
    course_paths?: AiInfraCoursePath[];
  };
  lesson_cards?: AiInfraLessonCard[];
  knowledge_units?: AiInfraKnowledgeUnitCard[];
  topic_families?: unknown[];
  course_paths?: AiInfraCoursePath[];
  twin_backend?: { default_base_url?: string; guided_learning_url?: string };
  trusted_source_coverage?: {
    source_count?: number;
    indexed_documents?: number;
    topic_count?: number;
    expert_unit_count?: number;
    review_status?: string;
    external_corpus_root?: string;
  };
  standard_learning_assets?: {
    course_path_count?: number;
    expert_unit_count?: number;
    quiz_count?: number;
    diagnosis_drill_count?: number;
    review_status?: string;
  };
}

export interface PrioritizedAiInfraContent {
  lessonCards: AiInfraLessonCard[];
  knowledgeUnits: AiInfraKnowledgeUnitCard[];
  matchedLessonCount: number;
  matchedKnowledgeCount: number;
}

export interface AiInfraCourseProgress {
  completed: number;
  total: number;
  pct: number;
}

export interface AiInfraCoverageSummary {
  courseCount: number;
  unitCount: number;
  completedUnitCount: number;
  completionPct: number;
  domainCount: number;
  sourceCount: number;
  labCount: number;
  candidateDocumentCount: number;
  evidenceRequirementCount: number;
  failureModeCount: number;
}

export interface AiInfraCourseContextStats {
  sourceCount: number;
  labCount: number;
  candidateDocumentCount: number;
  evidenceRequirementCount: number;
  failureModeCount: number;
  claimBoundaryCount: number;
}

export type AiInfraUnitMasteryLevel =
  | "not_started"
  | "attempted"
  | "familiar"
  | "proficient"
  | "evidence_ready";

export interface AiInfraUnitMasteryCheck {
  id: string;
  label: string;
  done: boolean;
}

export interface AiInfraUnitMasteryState {
  scorePct: number;
  level: AiInfraUnitMasteryLevel;
  nextAction: string;
  checks: AiInfraUnitMasteryCheck[];
}

export interface AiInfraReviewQueueItem {
  unit: AiInfraKnowledgeUnitCard;
  mastery: AiInfraUnitMasteryState;
}

export interface AiInfraReviewLedgerEntry {
  completedAt?: string;
  lastReviewedAt?: string;
}

export type AiInfraSpacedReviewDueStatus = "due" | "soon" | "later";

export interface AiInfraSpacedReviewQueueItem extends AiInfraReviewQueueItem {
  dueAt: string;
  dueStatus: AiInfraSpacedReviewDueStatus;
  dueLabel: string;
  reason: string;
  priority: number;
}

export interface AiInfraDiagnosisResponseAssessment {
  scorePct: number;
  passed: boolean;
  matchedClaimKeys: string[];
  missingClaimKeys: string[];
  rubricSignals: string[];
  feedback: string;
}

export interface AiInfraSourceDocumentDrillAssessment {
  scorePct: number;
  passed: boolean;
  matchedDocuments: string[];
  matchedEvidenceRequirements: string[];
  feedback: string;
}

export interface AiInfraReviewStageSummary {
  displayLabel: string;
  approved: boolean;
  requiredApprovals: string[];
}

export type AiInfraLearningMode =
  | "learn"
  | "guided_practice"
  | "independent_lab"
  | "incident_challenge"
  | "capstone";

export interface AiInfraLearningModeView {
  mode: AiInfraLearningMode;
  label: string;
  requiresEvidenceBundle: boolean;
  showConcepts: boolean;
  showFailureModes: boolean;
  showEvidenceRequirements: boolean;
  showClaimBoundaries: boolean;
  showDiagnosisRubric: boolean;
  showExpectedClaimShape: boolean;
  showTrustedDocuments: boolean;
  prompt: string;
}

const PRIORITY_COURSE_DOMAINS = [
  "containers",
  "kubernetes",
  "observability",
  "inference_serving",
];

export function extractAiInfraPluginKnowledge(
  handshake: HandshakeResult | null,
): AiInfraPluginKnowledge | undefined {
  return (handshake?.export as { bundle?: { knowledge?: unknown } } | undefined)?.bundle
    ?.knowledge as AiInfraPluginKnowledge | undefined;
}

export function getAiInfraCoursePaths(
  knowledge: AiInfraPluginKnowledge | undefined,
): AiInfraCoursePath[] {
  return knowledge?.course_paths || knowledge?.learning_surface?.course_paths || [];
}

export function getPriorityAiInfraCoursePaths(
  knowledge: AiInfraPluginKnowledge | undefined,
): AiInfraCoursePath[] {
  const courses = getAiInfraCoursePaths(knowledge);
  const byDomain = new Map(courses.map((course) => [course.domain, course]));
  return [
    ...PRIORITY_COURSE_DOMAINS.map((domain) => byDomain.get(domain)).filter(
      (course): course is AiInfraCoursePath => Boolean(course),
    ),
    ...courses.filter((course) => !PRIORITY_COURSE_DOMAINS.includes(course.domain || "")),
  ];
}

export function filterAiInfraCoursePaths(
  courses: AiInfraCoursePath[],
  query: string,
): AiInfraCoursePath[] {
  const tokens = textTokens([query]);
  if (tokens.length === 0) return courses;
  return courses.filter((course) => {
    const haystack = new Set(
      textTokens([
        course.course_path_id,
        course.title,
        course.domain,
        course.capstone_task,
        ...(course.levels || []),
        ...(course.lab_refs || []),
        ...(course.unit_refs || []),
      ]),
    );
    return tokens.every((token) => haystack.has(token));
  });
}

export function getAiInfraCourseProgress(
  course: AiInfraCoursePath | null | undefined,
  completedUnitIds: Set<string>,
): AiInfraCourseProgress {
  const refs = course?.unit_refs || [];
  if (refs.length === 0) return { completed: 0, total: 0, pct: 0 };
  const completed = refs.filter((unitId) => completedUnitIds.has(unitId)).length;
  return {
    completed,
    total: refs.length,
    pct: Math.round((completed / refs.length) * 100),
  };
}

export function findAiInfraKnowledgeUnit(
  knowledge: AiInfraPluginKnowledge | undefined,
  unitId: string | undefined,
): AiInfraKnowledgeUnitCard | undefined {
  if (!unitId) return undefined;
  const units =
    knowledge?.knowledge_units ||
    knowledge?.learning_surface?.knowledge_unit_cards ||
    [];
  return units.find((unit) => unit.unit_id === unitId);
}

export function getAiInfraCoverageSummary(
  knowledge: AiInfraPluginKnowledge | undefined,
  completedUnitIds: Set<string> = new Set(),
): AiInfraCoverageSummary {
  const courses = getAiInfraCoursePaths(knowledge);
  const units =
    knowledge?.knowledge_units ||
    knowledge?.learning_surface?.knowledge_unit_cards ||
    [];
  const domains = new Set<string>();
  const sources = new Set<string>();
  const labs = new Set<string>();
  const candidateDocuments = new Set<string>();
  const evidenceRequirements = new Set<string>();
  const failureModes = new Set<string>();

  for (const course of courses) {
    if (course.domain) domains.add(course.domain);
    for (const sourceId of course.source_ids || []) sources.add(sourceId);
    for (const labId of course.lab_refs || []) labs.add(labId);
  }

  for (const unit of units) {
    if (unit.domain) domains.add(unit.domain);
    if (unit.topic_family_id) domains.add(unit.topic_family_id);
    for (const sourceId of unit.source_ids || []) sources.add(sourceId);
    for (const labId of unit.lab_refs || []) labs.add(labId);
    for (const doc of unit.candidate_documents || []) {
      const docId = doc.document_id || `${doc.source_id || ""}:${doc.relative_path || ""}`;
      if (docId !== ":") candidateDocuments.add(docId);
    }
    for (const item of unit.evidence_requirements || []) evidenceRequirements.add(item);
    for (const item of unit.failure_modes || []) failureModes.add(item);
  }

  const completedUnitCount = units.filter(
    (unit) => unit.unit_id && completedUnitIds.has(unit.unit_id),
  ).length;

  return {
    courseCount: courses.length,
    unitCount: units.length,
    completedUnitCount,
    completionPct: units.length ? Math.round((completedUnitCount / units.length) * 100) : 0,
    domainCount: domains.size,
    sourceCount: sources.size,
    labCount: labs.size,
    candidateDocumentCount: candidateDocuments.size,
    evidenceRequirementCount: evidenceRequirements.size,
    failureModeCount: failureModes.size,
  };
}

export function getAiInfraCourseContextStats(
  knowledge: AiInfraPluginKnowledge | undefined,
  course: AiInfraCoursePath | null | undefined,
): AiInfraCourseContextStats {
  if (!course) {
    return {
      sourceCount: 0,
      labCount: 0,
      candidateDocumentCount: 0,
      evidenceRequirementCount: 0,
      failureModeCount: 0,
      claimBoundaryCount: 0,
    };
  }
  const sources = new Set(course.source_ids || []);
  const labs = new Set(course.lab_refs || []);
  const candidateDocuments = new Set<string>();
  const evidenceRequirements = new Set<string>();
  const failureModes = new Set<string>();
  const claimBoundaries = new Set<string>();

  for (const unitId of course.unit_refs || []) {
    const unit = findAiInfraKnowledgeUnit(knowledge, unitId);
    if (!unit) continue;
    for (const sourceId of unit.source_ids || []) sources.add(sourceId);
    for (const labId of unit.lab_refs || []) labs.add(labId);
    for (const doc of unit.candidate_documents || []) {
      const docId = doc.document_id || `${doc.source_id || ""}:${doc.relative_path || ""}`;
      if (docId !== ":") candidateDocuments.add(docId);
    }
    for (const item of unit.evidence_requirements || []) evidenceRequirements.add(item);
    for (const item of unit.failure_modes || []) failureModes.add(item);
    for (const item of unit.claim_boundaries || []) claimBoundaries.add(item);
  }

  return {
    sourceCount: sources.size,
    labCount: labs.size,
    candidateDocumentCount: candidateDocuments.size,
    evidenceRequirementCount: evidenceRequirements.size,
    failureModeCount: failureModes.size,
    claimBoundaryCount: claimBoundaries.size,
  };
}

export function getAiInfraUnitMasteryState(params: {
  unit: AiInfraKnowledgeUnitCard | null | undefined;
  quizCorrect?: boolean;
  diagnosisPassed?: boolean;
  sourceDocumentPassed?: boolean;
  diagnosisNote?: string;
  reflectionNote?: string;
  completed?: boolean;
  hasLabEvidence?: boolean;
}): AiInfraUnitMasteryState {
  const unit = params.unit;
  if (!unit) {
    return {
      scorePct: 0,
      level: "not_started",
      nextAction: "Select a learning unit",
      checks: [],
    };
  }

  const hasDiagnosisDrill = Boolean(
    unit.standard_learning?.assessment?.diagnosis_drills?.length,
  );
  const hasTwinPractice = Boolean(
    (unit.standard_learning?.twin_practice?.lab_refs || unit.lab_refs || []).length,
  );
  const hasSourceDocuments = Boolean(unit.candidate_documents?.length);
  const diagnosisReady =
    params.diagnosisPassed ?? normalizedLength(params.diagnosisNote) >= 20;
  const sourceDocumentReady = params.sourceDocumentPassed ?? !hasSourceDocuments;
  const reflectionReady = normalizedLength(params.reflectionNote) >= 20;
  const labEvidenceReady = Boolean(params.hasLabEvidence);
  const checks: AiInfraUnitMasteryCheck[] = [
    {
      id: "active_recall",
      label: "Pass active-recall quiz",
      done: Boolean(params.quizCorrect),
    },
    {
      id: "reflection",
      label: "Reflect with evidence",
      done: reflectionReady,
    },
    {
      id: "complete",
      label: "Mark unit complete",
      done: Boolean(params.completed),
    },
  ];
  if (hasDiagnosisDrill) {
    checks.splice(1, 0, {
      id: "diagnosis",
      label: "Write bounded diagnosis",
      done: diagnosisReady,
    });
  }
  if (hasSourceDocuments) {
    checks.splice(checks.length - 1, 0, {
      id: "source_document",
      label: "Ground answer in trusted source",
      done: sourceDocumentReady,
    });
  }
  if (hasTwinPractice) {
    checks.splice(checks.length - 1, 0, {
      id: "lab_evidence",
      label: "Bind Evidence Bundle",
      done: labEvidenceReady,
    });
  }
  const doneCount = checks.filter((check) => check.done).length;
  const scorePct = Math.round((doneCount / checks.length) * 100);
  const next = checks.find((check) => !check.done);

  return {
    scorePct,
    level: masteryLevelForScore(scorePct),
    nextAction: next?.label || "Start spaced review or next unit",
    checks,
  };
}

export function getAiInfraReviewQueue(params: {
  units: AiInfraKnowledgeUnitCard[];
  quizAnswers?: Record<string, string>;
  completedUnits?: Record<string, boolean>;
  reflectionNotes?: Record<string, string>;
  diagnosisNotes?: Record<string, string>;
  sourceDocumentNotes?: Record<string, string>;
  labEvidenceByUnitId?: Record<string, boolean>;
  limit?: number;
}): AiInfraReviewQueueItem[] {
  const quizAnswers = params.quizAnswers || {};
  const completedUnits = params.completedUnits || {};
  const reflectionNotes = params.reflectionNotes || {};
  const diagnosisNotes = params.diagnosisNotes || {};
  const labEvidenceByUnitId = params.labEvidenceByUnitId || {};
  const sourceDocumentNotes = params.sourceDocumentNotes || {};
  const items = params.units
    .map((unit, index) => {
      const quiz = unit.standard_learning?.assessment?.quiz?.[0];
      const answer = quiz?.question_id ? quizAnswers[quiz.question_id] : undefined;
      const drill = unit.standard_learning?.assessment?.diagnosis_drills?.[0];
      const diagnosisNote = unit.unit_id ? diagnosisNotes[unit.unit_id] : "";
      const diagnosisAssessment = drill
        ? assessAiInfraDiagnosisResponse(drill, diagnosisNote)
        : null;
      const sourceDocumentAssessment = assessAiInfraSourceDocumentDrill(
        unit,
        unit.unit_id ? sourceDocumentNotes[unit.unit_id] : "",
      );
      return {
        index,
        unit,
        mastery: getAiInfraUnitMasteryState({
          unit,
          quizCorrect: Boolean(answer && answer === quiz?.answer),
          diagnosisPassed: diagnosisAssessment?.passed,
          sourceDocumentPassed: sourceDocumentAssessment.passed,
          diagnosisNote,
          reflectionNote: unit.unit_id ? reflectionNotes[unit.unit_id] : "",
          hasLabEvidence: unit.unit_id ? labEvidenceByUnitId[unit.unit_id] : false,
          completed: Boolean(unit.unit_id && completedUnits[unit.unit_id]),
        }),
      };
    })
    .filter((item) => item.mastery.level !== "evidence_ready")
    .sort((a, b) => {
      if (a.mastery.scorePct !== b.mastery.scorePct) {
        return a.mastery.scorePct - b.mastery.scorePct;
      }
      return a.index - b.index;
    });
  return items.slice(0, params.limit ?? 5).map(({ unit, mastery }) => ({
    unit,
    mastery,
  }));
}

export function getAiInfraSpacedReviewQueue(params: {
  units: AiInfraKnowledgeUnitCard[];
  quizAnswers?: Record<string, string>;
  completedUnits?: Record<string, boolean>;
  reflectionNotes?: Record<string, string>;
  diagnosisNotes?: Record<string, string>;
  sourceDocumentNotes?: Record<string, string>;
  labEvidenceByUnitId?: Record<string, boolean>;
  reviewLedger?: Record<string, AiInfraReviewLedgerEntry>;
  now?: Date;
  limit?: number;
}): AiInfraSpacedReviewQueueItem[] {
  const now = params.now || new Date();
  const nowMs = now.getTime();
  const reviewLedger = params.reviewLedger || {};
  const items = params.units
    .map((unit, index) => {
      const unitId = unit.unit_id || "";
      const quiz = unit.standard_learning?.assessment?.quiz?.[0];
      const answer = quiz?.question_id ? params.quizAnswers?.[quiz.question_id] : undefined;
      const drill = unit.standard_learning?.assessment?.diagnosis_drills?.[0];
      const diagnosisNote = unitId ? params.diagnosisNotes?.[unitId] : "";
      const diagnosisAssessment = drill
        ? assessAiInfraDiagnosisResponse(drill, diagnosisNote)
        : null;
      const sourceDocumentAssessment = assessAiInfraSourceDocumentDrill(
        unit,
        unitId ? params.sourceDocumentNotes?.[unitId] : "",
      );
      const mastery = getAiInfraUnitMasteryState({
        unit,
        quizCorrect: Boolean(answer && answer === quiz?.answer),
        diagnosisPassed: diagnosisAssessment?.passed,
        sourceDocumentPassed: sourceDocumentAssessment.passed,
        diagnosisNote,
        reflectionNote: unitId ? params.reflectionNotes?.[unitId] : "",
        hasLabEvidence: unitId ? params.labEvidenceByUnitId?.[unitId] : false,
        completed: Boolean(unitId && params.completedUnits?.[unitId]),
      });
      const ledger = unitId ? reviewLedger[unitId] : undefined;
      const anchor = parseReviewDate(ledger?.lastReviewedAt) || parseReviewDate(ledger?.completedAt);
      const intervalDays = reviewIntervalDays(mastery.scorePct);
      const dueAtMs = anchor ? anchor.getTime() + intervalDays * 86400000 : nowMs;
      const hoursUntilDue = (dueAtMs - nowMs) / 3600000;
      const dueStatus: AiInfraSpacedReviewDueStatus =
        hoursUntilDue <= 0 ? "due" : hoursUntilDue <= 48 ? "soon" : "later";
      const priority =
        (dueStatus === "due" ? 0 : dueStatus === "soon" ? 100 : 200) +
        (100 - mastery.scorePct) +
        index / 100;
      return {
        unit,
        mastery,
        dueAt: new Date(dueAtMs).toISOString(),
        dueStatus,
        dueLabel: formatDueLabel(hoursUntilDue),
        reason: reviewReason(mastery),
        priority,
      };
    })
    .sort((a, b) => a.priority - b.priority);
  return items.slice(0, params.limit ?? 6);
}

export function getAiInfraReviewStageSummary(
  reviewStatus: string | undefined,
): AiInfraReviewStageSummary {
  const rawStatus = reviewStatus || "generated_candidate";
  const status = normalizeForSearch(rawStatus);
  const approved = status === "approved";
  const labelByStatus: Record<string, string> = {
    "generated candidate": "generated candidate",
    "source verified": "source verified",
    "source backed draft review required": "source-backed draft",
    "technical reviewed": "technical reviewed",
    "lab validated": "lab validated",
    "assessment validated": "assessment validated",
    approved: "approved",
    deprecated: "deprecated",
  };
  return {
    displayLabel: labelByStatus[status] || rawStatus,
    approved,
    requiredApprovals: approved
      ? []
      : ["technical reviewer", "lab reviewer", "assessment reviewer"],
  };
}

export function getAiInfraLearningModeView(
  mode: AiInfraLearningMode | string | undefined,
): AiInfraLearningModeView {
  const normalized = normalizeForSearch(mode || "learn").replace(/\s+/g, "_");
  const resolved = isAiInfraLearningMode(normalized) ? normalized : "learn";
  const modes: Record<AiInfraLearningMode, AiInfraLearningModeView> = {
    learn: {
      mode: "learn",
      label: "Learn",
      requiresEvidenceBundle: true,
      showConcepts: true,
      showFailureModes: true,
      showEvidenceRequirements: true,
      showClaimBoundaries: true,
      showDiagnosisRubric: true,
      showExpectedClaimShape: true,
      showTrustedDocuments: true,
      prompt: "Use full scaffolding to build the mental model.",
    },
    guided_practice: {
      mode: "guided_practice",
      label: "Guided Practice",
      requiresEvidenceBundle: true,
      showConcepts: true,
      showFailureModes: true,
      showEvidenceRequirements: true,
      showClaimBoundaries: true,
      showDiagnosisRubric: true,
      showExpectedClaimShape: false,
      showTrustedDocuments: true,
      prompt: "Keep partial hints, but write the claim structure yourself.",
    },
    independent_lab: {
      mode: "independent_lab",
      label: "Independent Lab",
      requiresEvidenceBundle: true,
      showConcepts: true,
      showFailureModes: false,
      showEvidenceRequirements: false,
      showClaimBoundaries: false,
      showDiagnosisRubric: false,
      showExpectedClaimShape: false,
      showTrustedDocuments: true,
      prompt: "Solve from task, docs, and observed evidence without diagnosis hints.",
    },
    incident_challenge: {
      mode: "incident_challenge",
      label: "Incident Challenge",
      requiresEvidenceBundle: true,
      showConcepts: false,
      showFailureModes: false,
      showEvidenceRequirements: false,
      showClaimBoundaries: false,
      showDiagnosisRubric: false,
      showExpectedClaimShape: false,
      showTrustedDocuments: false,
      prompt: "Treat this as an unknown incident with noisy or incomplete evidence.",
    },
    capstone: {
      mode: "capstone",
      label: "Capstone",
      requiresEvidenceBundle: true,
      showConcepts: false,
      showFailureModes: false,
      showEvidenceRequirements: false,
      showClaimBoundaries: false,
      showDiagnosisRubric: false,
      showExpectedClaimShape: false,
      showTrustedDocuments: false,
      prompt: "Produce a reviewable engineering artifact and defend the trade-offs.",
    },
  };
  return modes[resolved];
}

export function assessAiInfraSourceDocumentDrill(
  unit: AiInfraKnowledgeUnitCard | null | undefined,
  response: string | undefined,
): AiInfraSourceDocumentDrillAssessment {
  const text = normalizeForSearch(response || "");
  const docs = unit?.candidate_documents || [];
  const evidenceRequirements = unit?.evidence_requirements || [];
  const matchedDocuments = docs
    .filter((doc) => isDocumentReferenced(doc, text))
    .map((doc) => doc.document_id || doc.title || doc.relative_path || doc.source_id || "document");
  const matchedEvidenceRequirements = evidenceRequirements.filter((item) =>
    textTokens([item]).some((token) => text.includes(token)),
  );
  const documentScore = docs.length ? (matchedDocuments.length > 0 ? 1 : 0) : 1;
  const evidenceScore = evidenceRequirements.length
    ? Math.min(1, matchedEvidenceRequirements.length / Math.min(2, evidenceRequirements.length))
    : 1;
  const claimBoundaryScore = textTokens(unit?.claim_boundaries || []).some((token) =>
    text.includes(token),
  )
    ? 1
    : unit?.claim_boundaries?.length
      ? 0
      : 1;
  const substanceScore = Math.min(1, normalizedLength(response) / 120);
  const scorePct = Math.round(
    (documentScore * 0.35 + evidenceScore * 0.3 + claimBoundaryScore * 0.15 + substanceScore * 0.2) *
      100,
  );
  const passed = scorePct >= 70 && (!docs.length || matchedDocuments.length > 0);
  return {
    scorePct,
    passed,
    matchedDocuments,
    matchedEvidenceRequirements,
    feedback: passed
      ? "Source-grounded answer is ready for evidence review"
      : matchedDocuments.length === 0 && docs.length > 0
        ? "Reference at least one trusted document"
        : "Tie the source claim to required evidence and claim boundary",
  };
}

function isAiInfraLearningMode(value: string): value is AiInfraLearningMode {
  return [
    "learn",
    "guided_practice",
    "independent_lab",
    "incident_challenge",
    "capstone",
  ].includes(value);
}

export function assessAiInfraDiagnosisResponse(
  drill: AiInfraDiagnosisDrill | null | undefined,
  response: string | undefined,
): AiInfraDiagnosisResponseAssessment {
  const text = normalizeForSearch(response || "");
  const claimKeys = Object.keys(drill?.expected_claim_shape || {});
  const matchedClaimKeys = claimKeys.filter((key) =>
    tokenAliases(key).some((token) => text.includes(token)),
  );
  const missingClaimKeys = claimKeys.filter((key) => !matchedClaimKeys.includes(key));
  const rubricSignals = (drill?.rubric || []).filter((item) =>
    textTokens([item]).some((token) => text.includes(token)),
  );
  const structureScore = claimKeys.length
    ? matchedClaimKeys.length / claimKeys.length
    : normalizedLength(response) >= 20
      ? 1
      : 0;
  const rubricScore = drill?.rubric?.length
    ? Math.min(1, rubricSignals.length / Math.min(3, drill.rubric.length))
    : 1;
  const substanceScore = Math.min(1, normalizedLength(response) / 160);
  const scorePct = Math.round(
    (structureScore * 0.5 + rubricScore * 0.25 + substanceScore * 0.25) * 100,
  );
  const passed = scorePct >= 70 && missingClaimKeys.length === 0;
  return {
    scorePct,
    passed,
    matchedClaimKeys,
    missingClaimKeys,
    rubricSignals,
    feedback: passed
      ? "Diagnosis is structured enough for evidence review"
      : missingClaimKeys.length
        ? `Missing claim fields: ${missingClaimKeys.join(", ")}`
        : "Add more evidence-specific reasoning before marking complete",
  };
}

export function prioritizeAiInfraContent(params: {
  knowledge: AiInfraPluginKnowledge | undefined;
  selectedLab: AiInfraLab | null;
}): PrioritizedAiInfraContent {
  const lessonCards =
    params.knowledge?.lesson_cards ||
    params.knowledge?.learning_surface?.lesson_cards ||
    [];
  const knowledgeUnits =
    params.knowledge?.knowledge_units ||
    params.knowledge?.learning_surface?.knowledge_unit_cards ||
    [];

  if (!params.selectedLab) {
    return {
      lessonCards,
      knowledgeUnits,
      matchedLessonCount: lessonCards.length,
      matchedKnowledgeCount: knowledgeUnits.length,
    };
  }

  const labId = params.selectedLab.labId;
  const contextTokens = tokensForLab(params.selectedLab);
  const scoredLessons = lessonCards.map((lesson, index) => ({
    item: lesson,
    index,
    score: scoreLesson(lesson, labId, contextTokens),
  }));
  const matchedTopicFamilies = new Set(
    scoredLessons
      .filter((entry) => entry.score >= 100)
      .map((entry) => entry.item.track_id)
      .filter((trackId): trackId is string => Boolean(trackId))
      .flatMap(topicHintsFromTrack),
  );

  const scoredUnits = knowledgeUnits.map((unit, index) => ({
    item: unit,
    index,
    score: scoreKnowledgeUnit(unit, labId, contextTokens, matchedTopicFamilies),
  }));

  return {
    lessonCards: rankByScore(scoredLessons),
    knowledgeUnits: rankByScore(scoredUnits),
    matchedLessonCount: scoredLessons.filter((entry) => entry.score >= 100).length,
    matchedKnowledgeCount: scoredUnits.filter((entry) => entry.score >= 100).length,
  };
}

function masteryLevelForScore(scorePct: number): AiInfraUnitMasteryLevel {
  if (scorePct >= 100) return "evidence_ready";
  if (scorePct >= 80) return "proficient";
  if (scorePct >= 40) return "familiar";
  if (scorePct > 0) return "attempted";
  return "not_started";
}

function normalizedLength(value: string | undefined): number {
  return (value || "").trim().replace(/\s+/g, " ").length;
}

function normalizeForSearch(value: string): string {
  return value.toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
}

function parseReviewDate(value: string | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function isDocumentReferenced(doc: AiInfraCandidateDocument, text: string): boolean {
  return [doc.document_id, doc.title, doc.relative_path, doc.source_id]
    .map((value) => normalizeForSearch(value || ""))
    .filter((value) => value.length >= 6)
    .some((value) => text.includes(value));
}

function reviewIntervalDays(scorePct: number): number {
  if (scorePct >= 100) return 7;
  if (scorePct >= 80) return 3;
  if (scorePct >= 40) return 1;
  return 0;
}

function formatDueLabel(hoursUntilDue: number): string {
  if (hoursUntilDue <= -24) return `${Math.ceil(Math.abs(hoursUntilDue) / 24)}d overdue`;
  if (hoursUntilDue <= 0) return "due now";
  if (hoursUntilDue < 24) return `in ${Math.ceil(hoursUntilDue)}h`;
  return `in ${Math.ceil(hoursUntilDue / 24)}d`;
}

function reviewReason(mastery: AiInfraUnitMasteryState): string {
  if (mastery.scorePct < 40) return mastery.nextAction;
  if (mastery.scorePct < 80) return "Rebuild weak evidence chain";
  if (mastery.scorePct < 100) return "Close remaining mastery gate";
  return "Retention review after evidence-ready completion";
}

function tokenAliases(key: string): string[] {
  const normalized = normalizeForSearch(key);
  const aliases: Record<string, string[]> = {
    symptom: ["symptom", "observable fact", "现象", "症状"],
    evidence: ["evidence", "proof", "metric", "log", "trace", "证据", "指标", "日志"],
    "claim strength": ["claim strength", "bounded", "confidence", "主张强度", "边界"],
    "missing proof": ["missing proof", "missing", "unknown", "unobserved", "缺失证明", "还缺"],
  };
  return [normalized, ...(aliases[normalized] || [])];
}

function scoreLesson(
  lesson: AiInfraLessonCard,
  labId: string,
  contextTokens: Set<string>,
): number {
  let score = lesson.lab_refs?.includes(labId) ? 100 : 0;
  for (const token of textTokens([
    lesson.lesson_id,
    lesson.track_id,
    lesson.title,
    lesson.summary,
    ...(lesson.outcomes || []),
  ])) {
    if (contextTokens.has(token)) score += 1;
  }
  return score;
}

function scoreKnowledgeUnit(
  unit: AiInfraKnowledgeUnitCard,
  labId: string,
  contextTokens: Set<string>,
  matchedTopicFamilies: Set<string>,
): number {
  let score = unit.lab_refs?.includes(labId) ? 100 : 0;
  if (unit.topic_family_id && matchedTopicFamilies.has(unit.topic_family_id)) {
    score += 12;
  }
  for (const token of textTokens([
    unit.unit_id,
    unit.topic_family_id,
    unit.title,
    unit.summary,
    unit.body,
    ...(unit.teaching_points || []),
  ])) {
    if (contextTokens.has(token)) score += 1;
  }
  return score;
}

function rankByScore<T>(entries: Array<{ item: T; index: number; score: number }>): T[] {
  return [...entries]
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map((entry) => entry.item);
}

function tokensForLab(lab: AiInfraLab): Set<string> {
  return new Set(
    textTokens([
      lab.labId,
      lab.title,
      lab.role,
      lab.roleLabel,
      lab.stage,
      lab.symptom,
      lab.learnerTask,
      lab.executionMode,
      ...(lab.competencies || []),
      ...(lab.requiredEvidence || []),
      ...(lab.diagnosisChoices || []),
    ]),
  );
}

function textTokens(parts: Array<string | undefined>): string[] {
  return parts
    .join(" ")
    .toLowerCase()
    .split(/[^a-z0-9]+/u)
    .filter((token) => token.length >= 3);
}

function topicHintsFromTrack(trackId: string): string[] {
  const parts = trackId.split(".");
  const lastPart = parts[parts.length - 1] || trackId;
  return textTokens([lastPart]);
}
