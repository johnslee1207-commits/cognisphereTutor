"""Enrich the bundled California Electrical Career pack with Entrance Exam content."""

from __future__ import annotations

import json
from pathlib import Path


PACK_PATH = Path(
    "cognispheretutor/integrations/cognisphere/bundled_packs/"
    "california_electrical_career_bundle.json"
)

SOURCE_REFS = [
    "laett.inside_wireman.2026-01-26",
    "gan.aptitude_test.2026-09-03",
    "cceti.gan_how_to_apply.2026-09-03",
]


def append_unique(knowledge: dict, section: str, items: list[dict]) -> int:
    records = knowledge.setdefault(section, [])
    existing = {item.get("id") or item.get("source_id") for item in records}
    added = 0
    for item in items:
        key = item.get("id") or item.get("source_id")
        if key in existing:
            continue
        records.append(item)
        existing.add(key)
        added += 1
    return added


def lesson_cards() -> list[dict]:
    return [
        {
            "id": "cec-lesson-entrance-exam-format-boundary",
            "title": "Entrance Exam format: practice beyond multiple choice",
            "summary": (
                "Entrance Exam preparation should not assume every exercise is "
                "multiple choice; Tutor uses multiple formats to build speed, "
                "accuracy, and reasoning transfer."
            ),
            "body": (
                "Teach that official selection materials describe tested abilities "
                "and sections, but local administrations may vary in exact item "
                "presentation. Tutor should train with multiple-choice checks for "
                "fast grading, numeric-fill items for arithmetic, short reading "
                "explanations for evidence discipline, and visual/spatial prompts "
                "for paper-folding and mechanical reasoning. Do not present original "
                "Tutor practice as leaked or official exam questions."
            ),
            "teaching_points": [
                "Multiple choice is useful for quick grading, but it is not the only readiness format.",
                "Math and numerical reasoning need no-choice calculation practice.",
                "Reading comprehension needs passage evidence, not outside assumptions.",
                "Mechanical and spatial reasoning need step-by-step tracing before answer-choice selection.",
                "Tutor practice is original and source-grounded; it must not claim to reproduce official questions.",
            ],
            "quick_check_prompts": [
                "Why should an Entrance Exam learner practice numeric-fill and short evidence answers?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-math-fractions-decimals",
            "title": "Entrance math: fractions, decimals, and percent bridges",
            "summary": (
                "Fast aptitude math often depends on converting between fractions, "
                "decimals, and percentages without losing the base quantity."
            ),
            "body": (
                "Teach the bridge method: fraction to decimal, decimal to percent, "
                "percent to multiplier. Always name the base before calculating. "
                "For selection practice, emphasize mental estimates first, exact "
                "arithmetic second, and answer plausibility last."
            ),
            "teaching_points": [
                "One half is 0.5 and 50%; one fourth is 0.25 and 25%; one eighth is 0.125 and 12.5%.",
                "Percent increase uses increase divided by original amount, not the new total.",
                "A decrease uses a multiplier below 1; an increase uses a multiplier above 1.",
                "Estimate before computing so impossible answers are rejected quickly.",
            ],
            "quick_check_prompts": [
                "A length increases from 80 to 100. What is the percent increase, and what base did you use?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-math-equation-from-words",
            "title": "Entrance math: turn words into equations",
            "summary": (
                "Word-problem misses often come from translating the sentence "
                "incorrectly before any arithmetic begins."
            ),
            "body": (
                "Use a four-step setup: define the unknown, mark total/change/rate "
                "words, write one relationship, then solve or test choices. Teach "
                "learners to slow down on words such as remaining, combined, per, "
                "twice, difference, and more than."
            ),
            "teaching_points": [
                "Define x in plain English before writing symbols.",
                "Remaining means total minus used amount.",
                "Per creates a rate: amount divided by unit.",
                "Combined work or production often uses rates, not raw totals.",
            ],
            "quick_check_prompts": [
                "Write an equation for: a worker has 12 more fittings than another worker, and together they have 64."
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-numerical-pattern-map",
            "title": "Entrance numerical reasoning: pattern map",
            "summary": (
                "A repeatable pattern map helps the learner test common sequence "
                "and data patterns before guessing."
            ),
            "body": (
                "Teach a short sequence checklist: constant difference, changing "
                "difference, multiplication/division, alternating two-track pattern, "
                "grouping, and position rule. For tables, compare rates and changes "
                "between rows instead of staring at isolated values."
            ),
            "teaching_points": [
                "First differences reveal many arithmetic sequences.",
                "Alternating patterns split odd and even positions into two mini-sequences.",
                "Table questions often hide the relevant denominator.",
                "If two rules fit, prefer the simpler rule that explains every shown term.",
            ],
            "quick_check_prompts": [
                "For 3, 6, 4, 8, 6, 12, what two-track rule is being used?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-reading-evidence-ladder",
            "title": "Entrance reading: evidence ladder",
            "summary": (
                "Reading comprehension should be answered from passage evidence in "
                "a fixed order: locate, restate, compare, eliminate."
            ),
            "body": (
                "Teach the evidence ladder. First locate the sentence that controls "
                "the answer. Second restate it in simpler words. Third compare each "
                "choice to that sentence. Fourth eliminate choices that add, reverse, "
                "overstate, or ignore a condition."
            ),
            "teaching_points": [
                "Do not answer from trade knowledge if the passage says something narrower.",
                "Watch qualifiers: before, after, unless, except, only, first, required.",
                "A choice can sound reasonable and still be unsupported.",
                "For EXCEPT questions, mark the task before reading choices.",
            ],
            "quick_check_prompts": [
                "What is the danger of choosing an answer because it sounds true but is not stated?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-mechanical-force-distance",
            "title": "Mechanical reasoning: force-distance tradeoff",
            "summary": (
                "Many mechanical items reduce to a tradeoff: less force usually "
                "means more distance, and more distance from a pivot increases turning effect."
            ),
            "body": (
                "Teach learners to identify the moving part, the pivot or support, "
                "the direction of force, and the tradeoff. For levers, farther from "
                "the pivot generally needs less force. For ramps and pulleys, "
                "mechanical advantage usually exchanges force for distance or rope length."
            ),
            "teaching_points": [
                "Draw or imagine the pivot first.",
                "Farther from a pivot gives more turning effect for the same force.",
                "A longer ramp usually lowers required force but increases travel distance.",
                "A pulley system can reduce pulling force while requiring more rope movement.",
            ],
            "quick_check_prompts": [
                "Why does pushing farther from a hinge usually make a door easier to open?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-mechanical-motion-tracing",
            "title": "Mechanical reasoning: trace motion one connection at a time",
            "summary": (
                "Gear, belt, and pulley mistakes often happen when the learner jumps "
                "across the whole mechanism instead of tracing each connection."
            ),
            "body": (
                "Teach one-connection tracing. Adjacent meshed gears reverse direction; "
                "gears connected by an open belt turn the same direction; a crossed belt "
                "reverses direction. Count reversals instead of relying on visual intuition alone."
            ),
            "teaching_points": [
                "Meshed gears reverse direction at each contact.",
                "An even number of gear contacts ends in the same direction as the first gear.",
                "An odd number of gear contacts ends in the opposite direction.",
                "Open belts and crossed belts behave differently; inspect the connection.",
            ],
            "quick_check_prompts": [
                "If gear A meshes with B, and B meshes with C, does C turn the same direction as A?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-spatial-rotation-reflection",
            "title": "Spatial reasoning: rotation is not reflection",
            "summary": "A common spatial trap is treating a mirror image as a rotated object.",
            "body": (
                "Teach feature tracking. Pick an asymmetric feature, track its relative "
                "position, and ask whether clockwise order around the shape stayed the same. "
                "Rotation preserves the order of features; reflection reverses it."
            ),
            "teaching_points": [
                "Rotation changes orientation but preserves left-right handedness.",
                "Reflection reverses the order of features.",
                "Track one marked corner or notch before looking at answer choices.",
                "If a feature swaps sides as in a mirror, it is not just rotated.",
            ],
            "quick_check_prompts": [
                "What stays the same during rotation but changes during reflection?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-paper-folding-unfold-order",
            "title": "Paper folding: unfold in reverse order",
            "summary": (
                "Paper-folding problems become manageable when the learner reverses "
                "the folds one at a time."
            ),
            "body": (
                "Teach reverse unfolding. Label the final folded packet, undo the last "
                "fold first, mirror holes or marks across that fold line, then undo the "
                "previous fold. Do not try to visualize the whole unfolded paper at once."
            ),
            "teaching_points": [
                "Unfold the last fold first.",
                "Each unfolded layer mirrors marks across the fold line.",
                "Count layers before deciding how many holes appear.",
                "A mark on a fold line may duplicate differently from a mark away from the fold line.",
            ],
            "quick_check_prompts": [
                "Why is reverse order safer than imagining the final unfolded page immediately?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-daily-cycle",
            "title": "Entrance Exam daily cycle: lesson, drill, error memory, retest",
            "summary": (
                "Near-term preparation should alternate mini-lessons, short drills, "
                "named error memory, and retesting rather than long passive reading."
            ),
            "body": (
                "Use a daily cycle: one mini-lesson, one worked example, three to six "
                "quick items, error label, then a retest later. The learner should know "
                "whether each miss was arithmetic, translation, evidence, mechanism tracing, "
                "spatial reversal, or pacing."
            ),
            "teaching_points": [
                "Short frequent practice beats one long theory block for aptitude readiness.",
                "Every miss needs a label so remediation can target the cause.",
                "Retest the same skill after a delay to confirm the fix held.",
                "Final-week study should protect test-day execution instead of adding too many new topics.",
            ],
            "quick_check_prompts": [
                "Name one error label that sends you back to math setup and one that sends you to pacing practice."
            ],
            "source_ref_ids": SOURCE_REFS,
        },
    ]


def practice_blueprints() -> list[dict]:
    return [
        {
            "id": "cec-practice-entrance-section-rotation",
            "title": "Entrance Exam rotating section drill",
            "summary": (
                "Rotate one focused section per day across math, numerical reasoning, "
                "reading, mechanical, and spatial skills."
            ),
            "practice_modes": ["focused lesson-first drill", "mixed-format quick quiz", "error-label retest"],
            "item_format_mix": [
                "multiple_choice",
                "numeric_fill",
                "true_false",
                "short_evidence_answer",
                "visual_reasoning_prompt",
            ],
            "generation_rules": [
                "Use only original practice items, never recalled or copyrighted exam questions.",
                "Start each drill with the method card for that section.",
                "Require explanation only after repeated misses or at checkpoint moments.",
                "Attach an error label to every wrong answer.",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-practice-entrance-math-no-choice",
            "title": "Entrance math without answer choices",
            "summary": (
                "Generate numeric-fill arithmetic and algebra items so the learner "
                "cannot rely only on elimination."
            ),
            "practice_modes": ["mental estimate", "numeric fill", "choice comparison after solving"],
            "generation_rules": [
                "Ask for the numeric answer first, then optionally show choices.",
                "Keep arithmetic realistic for aptitude speed practice.",
                "Include one ratio, one percent, one algebra setup, and one rate item per set.",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-practice-entrance-reading-evidence-set",
            "title": "Entrance reading evidence set",
            "summary": (
                "Generate short technical passages that require locating evidence, "
                "handling qualifiers, and rejecting unsupported choices."
            ),
            "practice_modes": ["passage-only answer", "EXCEPT qualifier drill", "unsupported-choice elimination"],
            "generation_rules": [
                "Use short original passages about workplace instructions, scheduling, safety notices, or tool handling.",
                "Do not require outside electrical knowledge.",
                "After grading, identify the controlling phrase in the passage.",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-practice-entrance-mechanical-spatial-lab",
            "title": "Mechanical and spatial reasoning lab",
            "summary": (
                "Generate visual-thinking drills for levers, gears, pulleys, rotation, "
                "reflection, and paper folding."
            ),
            "practice_modes": ["trace one connection", "predict direction", "reverse unfold", "rotation versus mirror"],
            "generation_rules": [
                "Keep diagrams textual or simple ASCII when no image renderer is available.",
                "Grade the reasoning step, not only the final letter.",
                "Separate mechanical misses from spatial misses in the error log.",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
    ]


def scenario_cards() -> list[dict]:
    return [
        {
            "id": "cec-scenario-entrance-fraction-decimal-bridge",
            "title": "Math bridge: fraction to percent",
            "summary": "Original numeric-fill item for fraction, decimal, and percent fluency.",
            "response_format": "numeric_fill",
            "scenario": ["A conduit run is 3/8 complete. What percent of the run is complete?"],
            "expected_answer": "37.5%",
            "correct_rationale": ["3 divided by 8 is 0.375, which is 37.5%."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-percent-base",
            "title": "Math trap: percent base",
            "summary": "Original multiple-choice item about percent increase base quantity.",
            "response_format": "multiple_choice",
            "scenario": ["A practice score rises from 24 correct to 30 correct. What is the percent increase?"],
            "choices": ["A) 6%", "B) 20%", "C) 25%", "D) 30%"],
            "answer": "C",
            "correct_rationale": ["The increase is 6. The base is the original 24. 6/24 = 25%."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-equation-fittings",
            "title": "Algebra setup: fittings count",
            "summary": "Original equation-setup item for word-problem translation.",
            "response_format": "short_answer",
            "scenario": [
                "Box A has 12 more fittings than Box B. Together they have 64 fittings. Define x as the number in Box B and write the equation."
            ],
            "expected_answer": "x + (x + 12) = 64",
            "correct_rationale": ["Box B is x. Box A is x + 12. Together means add them to get 64."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-rate-output",
            "title": "Rate reasoning: parts per hour",
            "summary": "Original rate item for numerical computation.",
            "response_format": "numeric_fill",
            "scenario": ["A trainee labels 45 parts in 15 minutes. At the same rate, how many parts can the trainee label in 1 hour?"],
            "expected_answer": "180",
            "correct_rationale": ["One hour is four 15-minute blocks. 45 times 4 is 180."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-sequence-second-difference",
            "title": "Numerical pattern: changing difference",
            "summary": "Original sequence item using second differences.",
            "response_format": "multiple_choice",
            "scenario": ["Find the next number: 2, 5, 10, 17, 26, ?"],
            "choices": ["A) 35", "B) 36", "C) 37", "D) 38"],
            "answer": "C",
            "correct_rationale": ["The differences are 3, 5, 7, 9, so the next difference is 11. 26 + 11 = 37."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-reading-only-after",
            "title": "Reading qualifier: only after",
            "summary": "Original passage-evidence item about sequence and condition words.",
            "response_format": "multiple_choice",
            "scenario": [
                "Passage: Submit the completed form only after the supervisor signs the verification line. Unsigned forms will be returned. Question: What must happen before submission?"
            ],
            "choices": ["A) The applicant pays a fee", "B) The supervisor signs the verification line", "C) The form is copied twice", "D) The applicant calls the office"],
            "answer": "B",
            "correct_rationale": ["The controlling words are only after the supervisor signs the verification line."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-reading-except-tool",
            "title": "Reading EXCEPT: tool notice",
            "summary": "Original EXCEPT item for careful answer-task handling.",
            "response_format": "multiple_choice",
            "scenario": [
                "Passage: Bring a photo ID, two pencils, and your appointment notice. Calculators and phones are not permitted in the testing room. Question: All are required EXCEPT:"
            ],
            "choices": ["A) Photo ID", "B) Two pencils", "C) Appointment notice", "D) Calculator"],
            "answer": "D",
            "correct_rationale": ["The question asks EXCEPT. A calculator is not permitted, not required."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-mechanical-door-hinge",
            "title": "Mechanical: door hinge leverage",
            "summary": "Original true-false item about pivot distance.",
            "response_format": "true_false",
            "scenario": ["True or false: Pushing a door near the outer edge usually takes less force than pushing near the hinge."],
            "answer": "True",
            "correct_rationale": ["The outer edge is farther from the pivot, so the same push creates more turning effect."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-mechanical-ramp",
            "title": "Mechanical: ramp tradeoff",
            "summary": "Original mechanical reasoning item about force and distance tradeoff.",
            "response_format": "multiple_choice",
            "scenario": [
                "Two ramps reach the same platform. Ramp A is short and steep. Ramp B is longer and less steep. Which usually requires less pushing force for the same load?"
            ],
            "choices": ["A) Ramp A", "B) Ramp B", "C) Both always require exactly the same force", "D) Neither because ramps do not affect force"],
            "answer": "B",
            "correct_rationale": ["The longer, less steep ramp usually reduces force but increases travel distance."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-gear-five",
            "title": "Mechanical: five-gear chain",
            "summary": "Original gear-direction item using reversal count.",
            "response_format": "multiple_choice",
            "scenario": ["Gear A meshes with B, B with C, C with D, and D with E. If A turns clockwise, which direction does E turn?"],
            "choices": ["A) Clockwise", "B) Counterclockwise", "C) It does not turn", "D) Cannot tell from the connections"],
            "answer": "A",
            "correct_rationale": ["There are four gear contacts. Four reversals returns to the same direction as A."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-spatial-rotation-l",
            "title": "Spatial: rotated L shape",
            "summary": "Original short-answer item distinguishing rotation from reflection.",
            "response_format": "short_answer",
            "scenario": ["An L shape has its short foot pointing right. After a 90-degree clockwise rotation, does that foot point down, left, up, or right?"],
            "expected_answer": "down",
            "correct_rationale": ["A right-pointing feature rotated 90 degrees clockwise points down."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-fold-vertical-horizontal",
            "title": "Paper folding: vertical then horizontal",
            "summary": "Original paper-folding item using reverse unfold order.",
            "response_format": "short_answer",
            "scenario": [
                "A square paper is folded left-to-right, then bottom-to-top. One hole is punched near the final folded packet corner away from both fold lines. When unfolded, how many matching holes appear?"
            ],
            "expected_answer": "4",
            "correct_rationale": ["Two folds create four layers at that position, so the hole mirrors into four positions when unfolded."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-timed-triage",
            "title": "Timed strategy: triage decision",
            "summary": "Original pacing item for skip/mark/return behavior.",
            "response_format": "multiple_choice",
            "scenario": [
                "During a timed mixed set, you spend 90 seconds on a spatial item and still cannot choose between two answers. What is the best next action?"
            ],
            "choices": ["A) Spend as long as needed", "B) Mark it, make the best provisional choice if required, and move on", "C) Stop the test and review notes", "D) Guess without reading the remaining questions"],
            "answer": "B",
            "correct_rationale": ["Pacing protects the total score. Mark, move, and return if time remains."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-pef-specific-evidence",
            "title": "PEF: specific evidence beats vague claims",
            "summary": "Original PEF item about evidence quality.",
            "response_format": "multiple_choice",
            "scenario": ["Which PEF note is strongest?"],
            "choices": ["A) I am hardworking", "B) I helped sometimes", "C) I completed a 40-hour safety course and can attach the certificate", "D) I like electrical work"],
            "answer": "C",
            "correct_rationale": ["Specific, verifiable evidence is stronger than vague self-description."],
            "source_ref_ids": ["laett.inside_wireman.2026-01-26", "gan.validation.2026-09-03"],
        },
    ]


def flashcard_decks() -> list[dict]:
    return [
        {
            "id": "cec-flashcards-entrance-format-mix",
            "title": "Entrance Exam format mix",
            "summary": "Cards reminding Tutor and learner to practice more than multiple choice.",
            "cards": [
                "Multiple choice: fast grading and elimination practice.",
                "Numeric fill: prevents overreliance on answer choices.",
                "Short evidence answer: proves reading support.",
                "True/false: quick concept check, but explain false statements after misses.",
                "Visual reasoning prompt: trace one feature, fold, gear, or force path.",
                "Never call original Tutor items official or recalled exam questions.",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-flashcards-entrance-reading-qualifiers",
            "title": "Entrance reading qualifier traps",
            "summary": "Recognition cards for passage-based reading questions.",
            "cards": ["only", "except", "unless", "before", "after", "must", "may", "not permitted", "first", "most likely"],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-flashcards-entrance-mechanical-motion",
            "title": "Entrance mechanical motion cues",
            "summary": "Fast cues for tracing basic mechanical systems.",
            "cards": [
                "Pivot: farther usually means less force.",
                "Ramp: less force usually means more distance.",
                "Meshed gear: reverse direction.",
                "Even gear reversals: same final direction.",
                "Odd gear reversals: opposite final direction.",
                "Pulley advantage: less force, more rope travel.",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-flashcards-entrance-spatial-paper",
            "title": "Entrance spatial and paper-folding cues",
            "summary": "Fast cues for rotation, reflection, and unfolding.",
            "cards": [
                "Rotation preserves feature order.",
                "Reflection reverses handedness.",
                "Track one asymmetric feature.",
                "Unfold in reverse order.",
                "Mirror holes across each fold line.",
                "Count layers before counting holes.",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
    ]


def readiness_checkpoints() -> list[dict]:
    return [
        {
            "id": "cec-checkpoint-entrance-exam-section-readiness",
            "title": "Entrance Exam section readiness checkpoint",
            "summary": (
                "Use after several Entrance Exam lessons to decide whether the learner "
                "needs focused repair or mixed timed practice."
            ),
            "checkpoint_prompts": [
                "Can the learner solve no-choice numeric-fill math items before seeing choices?",
                "Can the learner name the pattern type in sequence and table questions?",
                "Can the learner identify the exact passage phrase that controls a reading answer?",
                "Can the learner trace lever, ramp, gear, pulley, rotation, and fold items one step at a time?",
                "Can the learner explain the reason for a wrong answer using an error label?",
                "Can the learner switch from focused drills to timed mixed sets without freezing?",
            ],
            "mastery_evidence": [
                "80% on math computation and setup drills across two sessions",
                "75% on numerical pattern/table drills across two sessions",
                "75% on reading evidence drills with qualifier traps",
                "70% on mechanical/spatial visual reasoning drills",
                "documented error log with fewer repeated misses",
                "one completed timed mixed set with a written skip rule",
            ],
            "remediation": [
                "If numeric fill is weak, return to fraction/decimal/percent bridges and equation setup.",
                "If reading is weak, use evidence-ladder drills before more mixed practice.",
                "If mechanical is weak, use force-distance and one-connection tracing drills.",
                "If spatial is weak, separate rotation/reflection before paper-folding drills.",
                "If timing is weak, shorten sets and enforce mark/move/return behavior.",
            ],
            "source_ref_ids": SOURCE_REFS,
        }
    ]


def learning_activity_templates() -> list[dict]:
    return [
        {
            "id": "cec-activity-entrance-warmup-ladder",
            "title": "Entrance Exam warmup ladder",
            "summary": (
                "A short daily warmup that moves from recall to calculation to one "
                "timed item before the main lesson."
            ),
            "activity_modes": [
                "one-minute recall",
                "numeric-fill calculation",
                "one timed choice",
                "error tag",
            ],
            "steps": [
                "Ask one flashcard-style trigger question from the current section.",
                "Ask one no-choice numeric or short-answer item.",
                "Ask one timed multiple-choice item.",
                "Tag the miss if any, then continue to the planned mini-lesson.",
            ],
            "learner_action": [
                "Answer quickly without overexplaining.",
                "Write the setup before arithmetic when math is involved.",
                "Name the error pattern after feedback.",
            ],
            "feedback_rule": [
                "Keep warmups under five minutes.",
                "Do not block the lesson unless the same error repeats twice.",
            ],
            "exam_alignment": [
                "Builds daily retrieval and pacing for aptitude-section readiness."
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-activity-reading-annotation-drill",
            "title": "Reading annotation drill",
            "summary": (
                "A passage-first drill where the learner marks controlling words "
                "before seeing or choosing the answer."
            ),
            "activity_modes": [
                "short passage",
                "qualifier marking",
                "evidence choice",
                "unsupported-choice review",
            ],
            "steps": [
                "Show a short original technical or admissions passage.",
                "Ask the learner to identify the controlling phrase.",
                "Ask a multiple-choice or short evidence question.",
                "After grading, explain whether the miss was add, reverse, overstate, or ignore-condition.",
            ],
            "learner_action": [
                "Underline mentally: only, except, before, after, must, may, not permitted.",
                "Answer from the passage rather than outside knowledge.",
            ],
            "feedback_rule": [
                "If the learner chooses an unsupported answer, require the controlling phrase on the replacement item."
            ],
            "exam_alignment": [
                "Supports reading-comprehension sections without using official passages."
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-activity-mechanical-visual-trace",
            "title": "Mechanical visual trace board",
            "summary": (
                "A visual-thinking activity for levers, gears, pulleys, ramps, "
                "rotation, and paper folding."
            ),
            "activity_modes": [
                "identify parts",
                "trace one connection",
                "predict result",
                "compare to answer choices",
            ],
            "steps": [
                "Name the system: lever, ramp, gear train, pulley, rotation, reflection, or fold.",
                "Pick one feature, pivot, fold line, or gear contact to track.",
                "Predict direction, force tradeoff, or final position before choices.",
                "Grade the tracing step and the final answer separately.",
            ],
            "learner_action": [
                "Say what is being tracked.",
                "Move one connection or fold at a time.",
                "Avoid jumping to the final image before tracing.",
            ],
            "feedback_rule": [
                "If the final answer is right but tracing is wrong, mark as fragile and give one more visual trace."
            ],
            "exam_alignment": [
                "Supports mechanical comprehension and paper-folding/spatial readiness."
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-activity-adaptive-retest-loop",
            "title": "Adaptive retest loop",
            "summary": (
                "A remediation loop that retests the exact skill behind a miss after "
                "one short repair explanation."
            ),
            "activity_modes": [
                "grade",
                "error label",
                "micro repair",
                "parallel retest",
            ],
            "steps": [
                "Grade the learner's response as correct, incorrect, or fragile.",
                "Assign one error label.",
                "Teach a one-paragraph repair tied to that label.",
                "Ask a new original item with the same underlying skill but different surface story.",
            ],
            "learner_action": [
                "Read the error label.",
                "Apply the repair method on a new item.",
                "Continue only after the repeated miss is resolved or scheduled for review.",
            ],
            "feedback_rule": [
                "Never advance after a wrong answer without correction and a retest decision.",
                "Avoid long free-response gates unless the learner repeatedly guesses.",
            ],
            "exam_alignment": [
                "Turns quick quizzes into mastery evidence instead of simple exposure."
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-activity-final-week-mock-block",
            "title": "Final-week mock block",
            "summary": (
                "A compressed mixed block for learners close to an Entrance Exam date, "
                "balancing speed, coverage, and document readiness."
            ),
            "activity_modes": [
                "timed mixed set",
                "confidence mark",
                "section score",
                "document check",
            ],
            "steps": [
                "Run a short mixed set across math, numerical, reading, mechanical, and spatial items.",
                "Have the learner mark confidence on each answer.",
                "Grade by section and error label.",
                "Close with one application or PEF/document readiness reminder.",
            ],
            "learner_action": [
                "Use the skip/mark/return rule.",
                "Do not spend too long on one visual item.",
                "Review only the top two error types after the block.",
            ],
            "feedback_rule": [
                "In final-week mode, prioritize repeated high-yield errors and test execution over broad new content."
            ],
            "exam_alignment": [
                "Builds near-term readiness for timed aptitude selection."
            ],
            "source_ref_ids": SOURCE_REFS,
        },
    ]


def study_sequences() -> list[dict]:
    return [
        {
            "id": "cec-sequence-entrance-10-day-bootcamp",
            "title": "Entrance Exam 10-day bootcamp",
            "summary": (
                "A compressed sequence for a learner who needs immediate Entrance "
                "Exam preparation across every aptitude section."
            ),
            "objective_ids": [
                "cec-apprentice-baseline-diagnostic",
                "cec-apprentice-math-reasoning",
                "cec-apprentice-numerical-reasoning",
                "cec-apprentice-reading",
                "cec-apprentice-mechanical",
                "cec-apprentice-spatial",
                "cec-apprentice-timed-practice",
                "cec-apprentice-pef",
            ],
            "lesson_card_ids": [
                "cec-lesson-entrance-exam-format-boundary",
                "cec-lesson-entrance-math-fractions-decimals",
                "cec-lesson-entrance-math-equation-from-words",
                "cec-lesson-entrance-numerical-pattern-map",
                "cec-lesson-entrance-reading-evidence-ladder",
                "cec-lesson-entrance-mechanical-force-distance",
                "cec-lesson-entrance-mechanical-motion-tracing",
                "cec-lesson-entrance-spatial-rotation-reflection",
                "cec-lesson-entrance-paper-folding-unfold-order",
                "cec-lesson-entrance-daily-cycle",
            ],
            "activity_template_ids": [
                "cec-activity-entrance-warmup-ladder",
                "cec-activity-mini-lesson-quick-check",
                "cec-activity-adaptive-retest-loop",
                "cec-activity-final-week-mock-block",
            ],
            "day_plan": [
                "Day 1: baseline diagnostic and format boundary",
                "Day 2: fraction/decimal/percent bridge",
                "Day 3: algebra setup from words",
                "Day 4: sequence and table reasoning",
                "Day 5: reading evidence ladder",
                "Day 6: levers, ramps, and force-distance tradeoffs",
                "Day 7: gears, pulleys, and motion tracing",
                "Day 8: rotation, reflection, and paper folding",
                "Day 9: timed mixed set and error repair",
                "Day 10: final mock block and PEF/document check",
            ],
            "checkpoint_prompts": [
                "Which two sections are now strongest?",
                "Which two error labels repeat most often?",
                "Can the learner use skip/mark/return without prompting?",
            ],
            "mastery_evidence": [
                "completed one focused drill in each Entrance Exam section",
                "completed one mixed timed block",
                "error log shows fewer repeated misses",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-sequence-entrance-daily-maintenance",
            "title": "Entrance Exam daily maintenance",
            "summary": (
                "A lighter ongoing sequence for learners who have finished core "
                "lessons and need retention until the exam date."
            ),
            "objective_ids": [
                "cec-apprentice-math-reasoning",
                "cec-apprentice-numerical-reasoning",
                "cec-apprentice-reading",
                "cec-apprentice-mechanical",
                "cec-apprentice-spatial",
                "cec-apprentice-timed-practice",
            ],
            "activity_template_ids": [
                "cec-activity-entrance-warmup-ladder",
                "cec-activity-reading-annotation-drill",
                "cec-activity-mechanical-visual-trace",
                "cec-activity-adaptive-retest-loop",
            ],
            "rotation_rule": [
                "Every day includes one math/numerical item, one reading item, and one mechanical or spatial item.",
                "Every third day includes a timed mini-block.",
                "Any repeated miss becomes the next day's first warmup.",
            ],
            "mastery_evidence": [
                "stable accuracy over three separate days",
                "no repeated qualifier-trap or setup-error miss",
                "learner can explain the chosen pacing rule",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
    ]


def error_taxonomy() -> list[dict]:
    return [
        {
            "id": "cec-error-entrance-qualifier-trap",
            "title": "Entrance reading qualifier trap",
            "summary": (
                "The learner misses because they overlook words like except, only, "
                "unless, before, after, required, or not permitted."
            ),
            "remediation": [
                "Require the learner to identify the controlling phrase before answer choices.",
                "Use a short evidence-answer replacement item before another multiple-choice item.",
            ],
        },
        {
            "id": "cec-error-entrance-answer-choice-dependence",
            "title": "Answer-choice dependence",
            "summary": (
                "The learner can sometimes pick from choices but cannot produce the "
                "quantity, setup, or reasoning without options."
            ),
            "remediation": [
                "Switch the next math or spatial item to numeric-fill or short-answer format.",
                "Ask for an estimate before showing choices.",
            ],
        },
        {
            "id": "cec-error-entrance-visual-jump",
            "title": "Visual reasoning jump",
            "summary": (
                "The learner jumps to the final gear direction, fold result, or rotated "
                "shape without tracing one connection or fold at a time."
            ),
            "remediation": [
                "Ask the learner to name the tracked feature, pivot, gear contact, or fold line.",
                "Grade the trace step before grading the final answer.",
            ],
        },
    ]


def exam_deepening_lesson_cards() -> list[dict]:
    return [
        {
            "id": "cec-lesson-entrance-test-section-triage",
            "title": "Entrance Exam section triage",
            "summary": (
                "A learner should know which section a question belongs to before "
                "choosing a solving method."
            ),
            "body": (
                "Teach a section-first habit. Before solving, classify the item as "
                "computation, math reasoning, numerical pattern/data, reading, "
                "mechanical, spatial, or document/PEF readiness. The method comes "
                "after classification: calculate, set up, scan evidence, trace motion, "
                "or reverse unfold."
            ),
            "teaching_points": [
                "Wrong method selection wastes time even when the learner knows the topic.",
                "A numbers-only item may be computation; a relationship item may be reasoning.",
                "A passage item should start with evidence, not memory.",
                "A visual item should start with tracking, not guessing.",
            ],
            "quick_check_prompts": [
                "Classify this item before solving: A passage says forms are accepted only after review. Which word controls the answer?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-numerical-computation-speed",
            "title": "Numerical computation speed without rushing",
            "summary": (
                "Computation speed comes from stable shortcuts, estimates, and unit "
                "sense, not from skipping setup."
            ),
            "body": (
                "Teach a three-pass computation habit: estimate the size, calculate "
                "with a clean shortcut, then check whether the answer is plausible. "
                "Use friendly numbers, cancellation, doubling/halving, and percent "
                "multipliers. Speed should reduce careless errors, not create them."
            ),
            "teaching_points": [
                "Estimate first so decimal-place errors are easier to catch.",
                "Use doubling and halving for multiplication with 5, 25, and 50 percent.",
                "Cancel common factors in ratios before multiplying.",
                "Write units when the question mixes time, length, or rate.",
            ],
            "quick_check_prompts": [
                "Estimate first: 19.8 multiplied by 5 is closest to 10, 50, 100, or 200?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-problem-solving-constraints",
            "title": "Problem solving: satisfy every constraint",
            "summary": (
                "Constraint questions require checking every condition, not finding "
                "the first answer that looks reasonable."
            ),
            "body": (
                "Teach the checklist method: list constraints, test each answer or "
                "candidate against them, reject a candidate as soon as it violates one "
                "constraint, and keep the first candidate that satisfies all conditions. "
                "This method works for schedules, ordering, tool requirements, and "
                "logic-style aptitude items."
            ),
            "teaching_points": [
                "A candidate must satisfy all constraints, not most of them.",
                "Testing answer choices can be faster than building a full solution.",
                "Order words such as before, after, between, and not with matter.",
                "Write short symbols for constraints to reduce working-memory load.",
            ],
            "quick_check_prompts": [
                "If A must happen before B, and C cannot be first, which constraint should you test first?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-reading-main-idea-detail",
            "title": "Reading: main idea versus detail",
            "summary": (
                "Reading questions can ask for the whole passage point or for one "
                "specific controlling detail."
            ),
            "body": (
                "Teach learners to identify the question type before choosing. Main-idea "
                "questions need the passage's overall purpose. Detail questions need the "
                "specific sentence or phrase. Inference questions need a conclusion that "
                "must follow from the text, not a likely real-world assumption."
            ),
            "teaching_points": [
                "Main idea summarizes the whole passage.",
                "Detail answers live in one controlling phrase or sentence.",
                "Inference must be supported by the passage.",
                "Extreme choices often overstate a detail.",
            ],
            "quick_check_prompts": [
                "What is the difference between a detail answer and an inference answer?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-lesson-entrance-final-review-priority",
            "title": "Final review: prioritize repeated errors",
            "summary": (
                "The last stretch before an Entrance Exam should prioritize repeated "
                "error types and test execution."
            ),
            "body": (
                "Teach a final-review priority order: repeated misses first, slow but "
                "correct sections second, already-stable sections third, and new broad "
                "content last. The learner should leave each session with one repair "
                "rule and one short retest, not a long list of vague study tasks."
            ),
            "teaching_points": [
                "Repeated error labels matter more than one-off misses.",
                "Speed work should begin after the method is accurate.",
                "The final week is for execution, confidence, and documents.",
                "Stop broad review when it hides the real weak section.",
            ],
            "quick_check_prompts": [
                "If your last three misses are all EXCEPT-question mistakes, what should tomorrow's first drill be?"
            ],
            "source_ref_ids": SOURCE_REFS,
        },
    ]


def exam_deepening_practice_blueprints() -> list[dict]:
    return [
        {
            "id": "cec-practice-entrance-section-diagnostic-matrix",
            "title": "Entrance Exam section diagnostic matrix",
            "summary": (
                "Generate a diagnostic that separately scores computation, math setup, "
                "numerical reasoning, reading evidence, mechanical tracing, spatial "
                "reasoning, pacing, and PEF/document readiness."
            ),
            "practice_modes": [
                "section classification",
                "mixed short diagnostic",
                "error taxonomy assignment",
                "next-section routing",
            ],
            "score_dimensions": [
                "accuracy",
                "method choice",
                "time pressure",
                "confidence",
                "error repeat rate",
            ],
            "generation_rules": [
                "Use at least one non-multiple-choice item in math or spatial sections.",
                "Do not collapse reading and numerical misses into a single score.",
                "Recommend the next start point from the weakest repeated dimension.",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-practice-entrance-half-mock",
            "title": "Entrance Exam half mock",
            "summary": (
                "Generate a medium-length mixed practice block for learners who are "
                "past basic method lessons but not ready for full mock pacing."
            ),
            "practice_modes": [
                "timed half mock",
                "section score breakdown",
                "top-two error repair",
                "targeted retest",
            ],
            "item_format_mix": [
                "multiple_choice",
                "numeric_fill",
                "reading_evidence",
                "mechanical_trace",
                "spatial_unfold",
            ],
            "generation_rules": [
                "Keep the block short enough for immediate feedback in one Tutor session.",
                "After grading, repair only the top two repeated error types.",
                "End with one concrete next study action.",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-practice-entrance-visual-reasoning-bank",
            "title": "Entrance visual reasoning bank",
            "summary": (
                "Generate original mechanical and spatial visual reasoning items with "
                "text or simple diagram descriptions."
            ),
            "practice_modes": [
                "lever and pivot",
                "gear direction",
                "pulley tradeoff",
                "rotation versus reflection",
                "paper fold reverse unfolding",
            ],
            "generation_rules": [
                "Ask for the tracked feature or connection before the final answer.",
                "Vary surface stories so the learner does not memorize one pattern.",
                "Prefer simple diagrams or textual layouts that render well in chat.",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
    ]


def exam_deepening_scenario_cards() -> list[dict]:
    return [
        {
            "id": "cec-scenario-entrance-computation-decimal-place",
            "title": "Computation: decimal place check",
            "summary": "Original numerical-computation item focused on estimation.",
            "response_format": "multiple_choice",
            "scenario": ["Which is closest to 19.8 x 5?"],
            "choices": ["A) 10", "B) 50", "C) 100", "D) 500"],
            "answer": "C",
            "correct_rationale": ["19.8 is close to 20, and 20 x 5 is 100."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-computation-unit-rate",
            "title": "Computation: unit rate",
            "summary": "Original numeric-fill item for rate and units.",
            "response_format": "numeric_fill",
            "scenario": ["A learner completes 18 questions in 12 minutes. At that rate, how many questions per minute?"],
            "expected_answer": "1.5",
            "correct_rationale": ["18 divided by 12 is 1.5 questions per minute."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-ratio-simplify",
            "title": "Ratio: simplify before scaling",
            "summary": "Original ratio item that rewards cancellation.",
            "response_format": "multiple_choice",
            "scenario": ["The ratio of correct to incorrect answers is 5:2. If there are 21 answers total, how many are correct?"],
            "choices": ["A) 10", "B) 12", "C) 15", "D) 18"],
            "answer": "C",
            "correct_rationale": ["The ratio has 7 total parts. 21/7 = 3 per part. Correct answers are 5 x 3 = 15."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-algebra-two-workers",
            "title": "Algebra: two worker totals",
            "summary": "Original algebra word problem with a defined unknown.",
            "response_format": "numeric_fill",
            "scenario": ["Worker A prepared twice as many labels as Worker B. Together they prepared 72 labels. How many did Worker B prepare?"],
            "expected_answer": "24",
            "correct_rationale": ["Let B = x, so A = 2x. Then 3x = 72, so x = 24."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-work-rate-combined",
            "title": "Problem solving: combined work rate",
            "summary": "Original rate item for combined production.",
            "response_format": "multiple_choice",
            "scenario": ["One trainee can sort a bin in 30 minutes. Another can sort the same kind of bin in 60 minutes. Working together at those rates, about how long for one bin?"],
            "choices": ["A) 20 minutes", "B) 30 minutes", "C) 45 minutes", "D) 90 minutes"],
            "answer": "A",
            "correct_rationale": ["Rates are 1/30 and 1/60 bin per minute. Together they sort 3/60 = 1/20 bin per minute."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-sequence-multiply-add",
            "title": "Sequence: multiply then add",
            "summary": "Original numerical-reasoning sequence item.",
            "response_format": "multiple_choice",
            "scenario": ["Find the next number: 2, 5, 11, 23, 47, ?"],
            "choices": ["A) 71", "B) 89", "C) 95", "D) 96"],
            "answer": "C",
            "correct_rationale": ["Each term is previous x 2 + 1. 47 x 2 + 1 = 95."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-sequence-position-rule",
            "title": "Sequence: position rule",
            "summary": "Original pattern item using position increments.",
            "response_format": "numeric_fill",
            "scenario": ["Find the next number: 4, 6, 9, 13, 18, ?"],
            "expected_answer": "24",
            "correct_rationale": ["The differences are +2, +3, +4, +5, so next is +6. 18 + 6 = 24."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-table-efficiency",
            "title": "Table reasoning: efficiency",
            "summary": "Original table-comparison item.",
            "response_format": "multiple_choice",
            "scenario": ["Team A completes 40 tasks using 5 hours. Team B completes 54 tasks using 9 hours. Which team has better tasks-per-hour efficiency?"],
            "choices": ["A) Team A", "B) Team B", "C) Same", "D) Cannot tell"],
            "answer": "A",
            "correct_rationale": ["Team A: 8 tasks/hour. Team B: 6 tasks/hour."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-reading-main-purpose",
            "title": "Reading: main purpose",
            "summary": "Original main-idea reading item.",
            "response_format": "multiple_choice",
            "scenario": [
                "Passage: The testing notice explains what to bring, what is not allowed in the room, and when to arrive. Applicants who arrive late may need to reschedule. Question: What is the main purpose of the notice?"
            ],
            "choices": ["A) To teach electrical theory", "B) To explain test-day requirements", "C) To advertise a job", "D) To compare training programs"],
            "answer": "B",
            "correct_rationale": ["The passage focuses on what to bring, restrictions, arrival time, and rescheduling."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-reading-inference",
            "title": "Reading: supported inference",
            "summary": "Original inference item requiring passage support.",
            "response_format": "multiple_choice",
            "scenario": [
                "Passage: Applicants may update contact information online until the application deadline. After the deadline, updates must be made by contacting the office. Which inference is best supported?"
            ],
            "choices": ["A) Online updates are always available", "B) No updates are allowed after the deadline", "C) The update method changes after the deadline", "D) Applicants never need contact information"],
            "answer": "C",
            "correct_rationale": ["Before the deadline updates are online; after the deadline they require contacting the office."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-reading-not-permitted",
            "title": "Reading: not permitted",
            "summary": "Original detail item about a negative condition.",
            "response_format": "multiple_choice",
            "scenario": ["Passage: Bags must remain outside the testing room. Photo ID and pencils may be brought to the desk. Which item is not permitted at the desk?"],
            "choices": ["A) Bag", "B) Photo ID", "C) Pencil", "D) Appointment notice"],
            "answer": "A",
            "correct_rationale": ["The passage says bags must remain outside the testing room."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-mechanical-wheel-radius",
            "title": "Mechanical: wheel radius and turning",
            "summary": "Original mechanical item about radius and distance per turn.",
            "response_format": "true_false",
            "scenario": ["True or false: If two wheels turn once, the wheel with the larger radius moves a point on its rim through a longer distance."],
            "answer": "True",
            "correct_rationale": ["Circumference grows with radius, so the larger wheel rim travels farther per revolution."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-mechanical-open-belt",
            "title": "Mechanical: open belt direction",
            "summary": "Original motion-tracing item for belt direction.",
            "response_format": "multiple_choice",
            "scenario": ["Pulley A is connected to Pulley B by an open belt. If A turns clockwise and the belt does not cross, which way does B turn?"],
            "choices": ["A) Clockwise", "B) Counterclockwise", "C) It cannot move", "D) It alternates direction every turn"],
            "answer": "A",
            "correct_rationale": ["An open belt usually turns the connected pulley in the same direction."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-mechanical-crossed-belt",
            "title": "Mechanical: crossed belt direction",
            "summary": "Original motion-tracing item for crossed belts.",
            "response_format": "multiple_choice",
            "scenario": ["Pulley A is connected to Pulley B by a crossed belt. If A turns clockwise, which way does B turn?"],
            "choices": ["A) Clockwise", "B) Counterclockwise", "C) It cannot move", "D) Same direction only if B is larger"],
            "answer": "B",
            "correct_rationale": ["A crossed belt reverses the direction between the pulleys."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-spatial-clockwise-feature",
            "title": "Spatial: clockwise feature tracking",
            "summary": "Original rotation item using feature tracking.",
            "response_format": "multiple_choice",
            "scenario": ["A triangle has a dot near its top corner. After a 180-degree rotation, where is the dot?"],
            "choices": ["A) Top", "B) Bottom", "C) Left", "D) It disappears"],
            "answer": "B",
            "correct_rationale": ["A 180-degree rotation moves the top feature to the bottom."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-spatial-reflection-letter",
            "title": "Spatial: reflection trap",
            "summary": "Original item checking mirror versus rotation.",
            "response_format": "true_false",
            "scenario": ["True or false: A reflected letter F can always be made identical to the original by rotating it on the page."],
            "answer": "False",
            "correct_rationale": ["Reflection reverses handedness; rotating does not undo that mirror reversal."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-fold-edge-hole",
            "title": "Paper folding: hole on fold line",
            "summary": "Original paper-folding item about fold-line placement.",
            "response_format": "multiple_choice",
            "scenario": ["A paper is folded once vertically. A hole is punched exactly on the fold line. After unfolding, how many holes appear?"],
            "choices": ["A) 1", "B) 2", "C) 3", "D) 4"],
            "answer": "A",
            "correct_rationale": ["A punch on the fold line lies on the mirror axis, so it does not duplicate to a separate position."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-constraint-order",
            "title": "Problem solving: order constraints",
            "summary": "Original constraint-satisfaction item.",
            "response_format": "multiple_choice",
            "scenario": ["Tasks must be done with Measure before Cut, Label after Cut, and Review last. Which order works?"],
            "choices": ["A) Cut, Measure, Label, Review", "B) Measure, Cut, Label, Review", "C) Measure, Review, Cut, Label", "D) Label, Measure, Cut, Review"],
            "answer": "B",
            "correct_rationale": ["Measure is before Cut, Label is after Cut, and Review is last."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-confidence-calibration",
            "title": "Timed block: confidence calibration",
            "summary": "Original metacognitive item for mock review.",
            "response_format": "multiple_choice",
            "scenario": ["After a timed block, which result most needs review first?"],
            "choices": ["A) Correct with high confidence", "B) Correct with low confidence", "C) Incorrect with high confidence", "D) Skipped intentionally and returned later"],
            "answer": "C",
            "correct_rationale": ["Incorrect with high confidence signals a misconception, not just uncertainty."],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-scenario-entrance-pef-deadline",
            "title": "PEF: deadline control",
            "summary": "Original document-readiness item.",
            "response_format": "multiple_choice",
            "scenario": ["Which action best protects a PEF submission close to a deadline?"],
            "choices": ["A) Wait until test day to gather evidence", "B) Keep a dated checklist of required documents and unresolved items", "C) Submit vague claims without support", "D) Ignore official messages after applying"],
            "answer": "B",
            "correct_rationale": ["A dated checklist makes missing evidence and deadlines visible."],
            "source_ref_ids": ["laett.inside_wireman.2026-01-26", "gan.validation.2026-09-03"],
        },
    ]


def exam_deepening_flashcard_decks() -> list[dict]:
    return [
        {
            "id": "cec-flashcards-entrance-section-triage",
            "title": "Entrance section triage cues",
            "summary": "Cards for selecting the right solving method before answering.",
            "cards": [
                "Numbers only: estimate, compute, check units.",
                "Relationship words: define x and write the equation.",
                "Sequence: test differences, multiplication, alternating tracks.",
                "Passage: locate controlling phrase before choosing.",
                "Mechanism: identify pivot, contact, belt, or rope path.",
                "Fold/shape: track one feature and reverse unfold.",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
        {
            "id": "cec-flashcards-entrance-final-week",
            "title": "Entrance final-week rules",
            "summary": "Cards for protecting score and confidence near the test date.",
            "cards": [
                "Repair repeated errors before adding new content.",
                "Use skip/mark/return when stuck.",
                "Review incorrect-high-confidence answers first.",
                "Sleep and documents are part of readiness.",
                "Short mixed blocks beat panic cramming.",
                "Do not treat Tutor practice as official exam questions.",
            ],
            "source_ref_ids": SOURCE_REFS,
        },
    ]


def exam_deepening_readiness_checkpoints() -> list[dict]:
    return [
        {
            "id": "cec-checkpoint-entrance-half-mock-readiness",
            "title": "Entrance Exam half-mock readiness checkpoint",
            "summary": (
                "Use before moving from focused drills into longer mixed timed practice."
            ),
            "checkpoint_prompts": [
                "Can the learner classify each item section before solving?",
                "Can the learner complete numeric-fill math without answer choices?",
                "Can the learner identify reading evidence in one sentence?",
                "Can the learner trace visual items without jumping to choices?",
                "Can the learner review incorrect-high-confidence answers first?",
            ],
            "mastery_evidence": [
                "at least 75% across a mixed short diagnostic",
                "no unresolved repeated miss in the same section",
                "written top-two error labels and repair plan",
                "one successful adaptive retest after a miss",
            ],
            "remediation": [
                "If section triage is weak, run section-classification warmups.",
                "If incorrect-high-confidence errors appear, slow down and require method explanation.",
                "If time pressure causes broad collapse, use smaller timed blocks before half mock.",
            ],
            "source_ref_ids": SOURCE_REFS,
        }
    ]


def provenance_refs() -> list[dict]:
    return [
        {
            "source_id": "cec.entrance_exam_practice_boundary.2026-09-04",
            "managed_by": "Cognisphere",
            "materialized_at": "2026-09-04",
            "claim_summaries": [
                "Tutor Entrance Exam practice uses original items derived from published section descriptions and validated-selection principles, not recalled or official exam questions.",
                "Tutor should use multiple item formats: multiple choice for fast checks, numeric fill for computation, short evidence answers for reading, and visual reasoning prompts for mechanical/spatial skills.",
                "When exact local item presentation is not published, Tutor must avoid claiming that all official Entrance Exam questions are multiple choice.",
            ],
        }
    ]


def main() -> None:
    data = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    knowledge = data["knowledge"]
    added = {
        "lesson_cards": append_unique(knowledge, "lesson_cards", lesson_cards()),
        "exam_deepening_lesson_cards": append_unique(
            knowledge, "lesson_cards", exam_deepening_lesson_cards()
        ),
        "practice_blueprints": append_unique(knowledge, "practice_blueprints", practice_blueprints()),
        "exam_deepening_practice_blueprints": append_unique(
            knowledge, "practice_blueprints", exam_deepening_practice_blueprints()
        ),
        "scenario_cards": append_unique(knowledge, "scenario_cards", scenario_cards()),
        "exam_deepening_scenario_cards": append_unique(
            knowledge, "scenario_cards", exam_deepening_scenario_cards()
        ),
        "flashcard_decks": append_unique(knowledge, "flashcard_decks", flashcard_decks()),
        "exam_deepening_flashcard_decks": append_unique(
            knowledge, "flashcard_decks", exam_deepening_flashcard_decks()
        ),
        "readiness_checkpoints": append_unique(knowledge, "readiness_checkpoints", readiness_checkpoints()),
        "exam_deepening_readiness_checkpoints": append_unique(
            knowledge, "readiness_checkpoints", exam_deepening_readiness_checkpoints()
        ),
        "learning_activity_templates": append_unique(
            knowledge, "learning_activity_templates", learning_activity_templates()
        ),
        "study_sequences": append_unique(knowledge, "study_sequences", study_sequences()),
        "error_taxonomy": append_unique(knowledge, "error_taxonomy", error_taxonomy()),
        "cognisphere_provenance_refs": append_unique(
            knowledge, "cognisphere_provenance_refs", provenance_refs()
        ),
    }
    PACK_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(added, indent=2))


if __name__ == "__main__":
    main()
