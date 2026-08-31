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
