import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const pageSource = readFileSync(
  join(process.cwd(), "app", "(utility)", "space", "ai-infra", "page.tsx"),
  "utf8",
);

test("AI infra page loads Twin and plugin status independently", () => {
  assert.match(pageSource, /Promise\.allSettled/);
  assert.match(pageSource, /runCognisphereHandshake\(\{ domain: "ai_infra"/);
  assert.match(pageSource, /const nextHandshake =/);
});

test("AI infra Run Lab control is disabled in content-only mode", () => {
  assert.match(pageSource, /const labRuntimeAvailable =/);
  assert.match(pageSource, /disabled=\{!selected \|\| running \|\| !labRuntimeAvailable\}/);
  assert.match(pageSource, /内容学习模式/);
  assert.match(pageSource, /Content-only mode/);
});
