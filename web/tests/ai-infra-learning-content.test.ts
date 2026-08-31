import test from "node:test";
import assert from "node:assert/strict";

import {
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
        topic_family_id: "serving_readiness",
        lab_refs: ["lab.inference.vllm-triton-readiness"],
      },
      {
        unit_id: "unit.container",
        title: "Docker lifecycle lab pattern",
        topic_family_id: "containers",
        lab_refs: ["lab.container.docker-lifecycle"],
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
