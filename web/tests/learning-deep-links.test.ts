import test from "node:test";
import assert from "node:assert/strict";

import {
  learningSpaceGoalHref,
  masteryChatHref,
} from "../lib/cognisphere-learning-api";

test("masteryChatHref preselects mastery_path", () => {
  assert.equal(
    masteryChatHref("csphere-demo"),
    "/home/csphere-demo?capability=mastery_path",
  );
  assert.ok(
    masteryChatHref("csphere-demo", { tutorSessionId: "sess-1" }).includes(
      "tutor_session=sess-1",
    ),
  );
  assert.equal(
    masteryChatHref("csphere-demo", { autoStart: "next" }),
    "/home/csphere-demo?capability=mastery_path&autostart=next",
  );
  assert.equal(
    masteryChatHref("csphere-demo", {
      autoStart: "start",
      startPoint: "apprenticeship_mechanical",
    }),
    "/home/csphere-demo?capability=mastery_path&autostart=start&start_point=apprenticeship_mechanical",
  );
  assert.equal(
    masteryChatHref("csphere-demo", {
      autoStart: "start",
      startPoint: "apprenticeship_math",
      focusModule: "ETI / IBEW Local 11 Apprenticeship Entrance",
      focusObjective: "Mathematical reasoning for aptitude testing",
      launch: "123",
    }),
    "/home/csphere-demo?capability=mastery_path&autostart=start&start_point=apprenticeship_math&focus_module=ETI+%2F+IBEW+Local+11+Apprenticeship+Entrance&focus_objective=Mathematical+reasoning+for+aptitude+testing&launch=123",
  );
});

test("learningSpaceGoalHref carries goal and domains", () => {
  assert.equal(learningSpaceGoalHref(""), "/space/learning");
  assert.equal(
    learningSpaceGoalHref("practice algorithms"),
    "/space/learning?goal=practice+algorithms",
  );
  const href = learningSpaceGoalHref("calculus review", {
    domains: ["ap_calculus", "leetcode"],
  });
  assert.ok(href.includes("goal=calculus+review"));
  assert.ok(href.includes("domains=ap_calculus%2Cleetcode") || href.includes("domains=ap_calculus,leetcode"));
});
