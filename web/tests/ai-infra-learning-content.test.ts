import test from "node:test";
import assert from "node:assert/strict";

import {
  filterAiInfraCoursePaths,
  getAiInfraCourseContextStats,
  getAiInfraCoverageSummary,
  findAiInfraKnowledgeUnit,
  getAiInfraCourseProgress,
  getAiInfraUnitMasteryState,
  getPriorityAiInfraCoursePaths,
  prioritizeAiInfraContent,
  type AiInfraPluginKnowledge,
} from "../lib/ai-infra-learning-content";
import type { AiInfraLab } from "../lib/ai-infra-twin-api";

const knowledge: AiInfraPluginKnowledge = {
  learning_surface: {
    lesson_cards: [
      {
        lesson_id: "lesson.inference",
        title: "Inference operations",
        lab_refs: ["lab.inference.vllm-triton-readiness"],
      },
      {
        lesson_id: "lesson.container",
        title: "Container lifecycle",
        lab_refs: ["lab.container.docker-lifecycle"],
      },
    ],
    knowledge_unit_cards: [
      {
        unit_id: "unit.inference",
        title: "vLLM and Triton readiness",
        domain: "inference_serving",
        topic_family_id: "serving_readiness",
        source_ids: ["src:ai-infra:vllm-docs"],
        candidate_documents: [
          {
            document_id: "vllm:README.md",
            source_id: "src:ai-infra:vllm-docs",
          },
        ],
        failure_modes: ["endpoint_not_ready"],
        evidence_requirements: ["health_probe"],
        claim_boundaries: ["readiness_not_throughput"],
        lab_refs: ["lab.inference.vllm-triton-readiness"],
      },
      {
        unit_id: "unit.container",
        title: "Docker lifecycle lab pattern",
        domain: "containers",
        topic_family_id: "containers",
        source_ids: ["src:ai-infra:docker-docs"],
        candidate_documents: [
          {
            document_id: "docker:engine.md",
            source_id: "src:ai-infra:docker-docs",
          },
        ],
        failure_modes: ["stale_container"],
        evidence_requirements: ["cleanup_proof"],
        claim_boundaries: ["local_lifecycle_only"],
        lab_refs: ["lab.container.docker-lifecycle"],
        standard_learning: {
          assessment: {
            diagnosis_drills: [{ drill_id: "d1", task: "Diagnose the lifecycle" }],
          },
          twin_practice: {
            lab_refs: ["lab.container.docker-lifecycle"],
          },
        },
      },
    ],
    course_paths: [
      {
        course_path_id: "course.observability",
        domain: "observability",
        title: "Observability",
        unit_refs: ["unit.observability"],
      },
      {
        course_path_id: "course.containers",
        domain: "containers",
        title: "Containers",
        unit_refs: ["unit.container"],
        lab_refs: ["lab.container.docker-lifecycle"],
        source_ids: ["src:ai-infra:containerd-docs"],
      },
      {
        course_path_id: "course.inference",
        domain: "inference_serving",
        title: "Inference",
        unit_refs: ["unit.inference"],
      },
      {
        course_path_id: "course.security",
        domain: "security_governance",
        title: "Security",
        unit_refs: ["unit.security"],
      },
    ],
  },
};

function lab(overrides: Partial<AiInfraLab>): AiInfraLab {
  return {
    labId: "lab.container.docker-lifecycle",
    title: "Docker lifecycle cleanup",
    role: "platform_operator",
    stage: "practice",
    symptom: "container readiness and cleanup",
    learnerTask: "Run a bounded Docker lifecycle lab",
    executionMode: "REAL_LIFECYCLE",
    competencies: ["container lifecycle"],
    requiredEvidence: ["cleanup proof"],
    diagnosisChoices: ["port mapping issue"],
    ...overrides,
  };
}

test("prioritizeAiInfraContent puts selected lab lesson and unit first", () => {
  const content = prioritizeAiInfraContent({
    knowledge,
    selectedLab: lab({}),
  });

  assert.equal(content.lessonCards[0]?.lesson_id, "lesson.container");
  assert.equal(content.knowledgeUnits[0]?.unit_id, "unit.container");
  assert.equal(content.matchedLessonCount, 1);
  assert.equal(content.matchedKnowledgeCount, 1);
});

test("prioritizeAiInfraContent updates focus when the selected lab changes", () => {
  const content = prioritizeAiInfraContent({
    knowledge,
    selectedLab: lab({
      labId: "lab.inference.vllm-triton-readiness",
      title: "vLLM and Triton readiness probe",
      role: "inference_operator",
      symptom: "serving endpoint cannot be load tested yet",
      competencies: ["serving readiness"],
      requiredEvidence: ["health probe"],
    }),
  });

  assert.equal(content.lessonCards[0]?.lesson_id, "lesson.inference");
  assert.equal(content.knowledgeUnits[0]?.unit_id, "unit.inference");
  assert.equal(content.matchedLessonCount, 1);
  assert.equal(content.matchedKnowledgeCount, 1);
});

test("prioritizeAiInfraContent preserves manifest order when no lab is selected", () => {
  const content = prioritizeAiInfraContent({
    knowledge,
    selectedLab: null,
  });

  assert.deepEqual(
    content.lessonCards.map((lesson) => lesson.lesson_id),
    ["lesson.inference", "lesson.container"],
  );
  assert.deepEqual(
    content.knowledgeUnits.map((unit) => unit.unit_id),
    ["unit.inference", "unit.container"],
  );
});

test("getPriorityAiInfraCoursePaths promotes the first interactive AI infra paths", () => {
  const courses = getPriorityAiInfraCoursePaths(knowledge);

  assert.deepEqual(
    courses.slice(0, 3).map((course) => course.domain),
    ["containers", "observability", "inference_serving"],
  );
  assert.equal(courses[3]?.domain, "security_governance");
});

test("findAiInfraKnowledgeUnit resolves full units from course path refs", () => {
  const unit = findAiInfraKnowledgeUnit(knowledge, "unit.container");

  assert.equal(unit?.title, "Docker lifecycle lab pattern");
});

test("filterAiInfraCoursePaths matches course title, domain, and labs", () => {
  const courses = getPriorityAiInfraCoursePaths(knowledge);

  assert.deepEqual(
    filterAiInfraCoursePaths(courses, "serving").map((course) => course.domain),
    ["inference_serving"],
  );
  assert.deepEqual(
    filterAiInfraCoursePaths(courses, "docker").map((course) => course.domain),
    ["containers"],
  );
});

test("getAiInfraCourseProgress computes completed unit percentage", () => {
  const course = getPriorityAiInfraCoursePaths(knowledge).find(
    (item) => item.domain === "containers",
  );

  assert.deepEqual(getAiInfraCourseProgress(course, new Set(["unit.container"])), {
    completed: 1,
    total: 1,
    pct: 100,
  });
});

test("getAiInfraCoverageSummary counts sources, labs, docs, and completion", () => {
  const summary = getAiInfraCoverageSummary(knowledge, new Set(["unit.container"]));

  assert.equal(summary.courseCount, 4);
  assert.equal(summary.unitCount, 2);
  assert.equal(summary.completedUnitCount, 1);
  assert.equal(summary.completionPct, 50);
  assert.equal(summary.sourceCount, 3);
  assert.equal(summary.labCount, 2);
  assert.equal(summary.candidateDocumentCount, 2);
  assert.equal(summary.evidenceRequirementCount, 2);
  assert.equal(summary.failureModeCount, 2);
});

test("getAiInfraCourseContextStats summarizes the selected path context", () => {
  const course = getPriorityAiInfraCoursePaths(knowledge).find(
    (item) => item.domain === "containers",
  );
  const stats = getAiInfraCourseContextStats(knowledge, course);

  assert.deepEqual(stats, {
    sourceCount: 2,
    labCount: 1,
    candidateDocumentCount: 1,
    evidenceRequirementCount: 1,
    failureModeCount: 1,
    claimBoundaryCount: 1,
  });
});

test("getAiInfraUnitMasteryState guides the next missing learning action", () => {
  const unit = findAiInfraKnowledgeUnit(knowledge, "unit.container");

  const initial = getAiInfraUnitMasteryState({ unit });
  assert.equal(initial.level, "not_started");
  assert.equal(initial.nextAction, "Pass active-recall quiz");

  const partial = getAiInfraUnitMasteryState({
    unit,
    quizCorrect: true,
    diagnosisNote: "container stopped before cleanup proof",
    reflectionNote: "evidence is still too thin",
  });
  assert.equal(partial.level, "familiar");
  assert.equal(partial.nextAction, "Attach Twin lab evidence");

  const complete = getAiInfraUnitMasteryState({
    unit,
    quizCorrect: true,
    diagnosisNote: "container stopped before cleanup proof",
    reflectionNote: "evidence supports only the local lifecycle claim",
    hasLabEvidence: true,
    completed: true,
  });
  assert.equal(complete.level, "evidence_ready");
  assert.equal(complete.scorePct, 100);
});
