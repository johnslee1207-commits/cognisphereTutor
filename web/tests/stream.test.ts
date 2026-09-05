import test from "node:test";
import assert from "node:assert/strict";

import { recomputeAnswerContent } from "../lib/stream";
import type { StreamEvent } from "../lib/unified-ws";

function event(
  type: StreamEvent["type"],
  content: string,
  metadata: Record<string, unknown>,
): StreamEvent {
  return {
    type,
    source: "chat",
    stage: "responding",
    content,
    metadata,
    timestamp: 0,
  };
}

test("recomputeAnswerContent preserves lesson text before pending ask_user", () => {
  const events = [
    event("content", "Mini-lesson: fold the paper, then mirror the hole.", {
      call_id: "round-1",
      call_kind: "agent_loop_round",
    }),
    event("progress", "", {
      call_id: "round-1",
      trace_kind: "call_status",
      call_state: "complete",
      call_role: "narration",
    }),
    event("tool_result", "[awaiting user reply to: Where is the second hole?]", {
      tool: "ask_user",
      call_kind: "tool_planning",
    }),
  ];

  assert.equal(
    recomputeAnswerContent(events),
    "Mini-lesson: fold the paper, then mirror the hole.",
  );
});

test("recomputeAnswerContent still removes ordinary narration", () => {
  const events = [
    event("content", "I'll call a tool first.", {
      call_id: "round-1",
      call_kind: "agent_loop_round",
    }),
    event("progress", "", {
      call_id: "round-1",
      trace_kind: "call_status",
      call_state: "complete",
      call_role: "narration",
    }),
    event("content", "Final answer.", {
      call_id: "round-2",
      call_kind: "llm_final_response",
    }),
  ];

  assert.equal(recomputeAnswerContent(events), "Final answer.");
});
