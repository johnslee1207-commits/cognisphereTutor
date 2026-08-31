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
