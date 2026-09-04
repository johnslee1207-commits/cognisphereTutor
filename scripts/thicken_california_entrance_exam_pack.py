"""Add dense apprenticeship entrance exam learning material to the California pack."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BUNDLE_PATH = Path(
    "cognispheretutor/integrations/cognisphere/bundled_packs/"
    "california_electrical_career_bundle.json"
)
IMPORT_CACHE_PATH = Path(
    "data/user/workspace/cognisphere_imports/california_electrical_career/bundle.json"
)

SOURCE_IDS = [
    "laett.inside_wireman.2026-01-26",
    "eta.sample_test.2026-09-03",
    "gan.aptitude_test.2026-09-03",
    "cceti.gan_how_to_apply.2026-09-03",
    "inland_electrical.eta_aptitude.2026-09-03",
    "cec.entrance_exam_practice_boundary.2026-09-04",
]


def _append_unique(items: list[dict[str, Any]], new_items: list[dict[str, Any]]) -> int:
    seen = {str(item.get("id")) for item in items}
    added = 0
    for item in new_items:
        item_id = str(item.get("id"))
        if item_id and item_id not in seen:
            items.append(item)
            seen.add(item_id)
            added += 1
    return added


def _lesson(
    lesson_id: str,
    title: str,
    summary: str,
    body: str,
    points: list[str],
    check: str,
) -> dict[str, Any]:
    return {
        "id": lesson_id,
        "title": title,
        "summary": summary,
        "body": body,
        "teaching_points": points,
        "quick_check_prompts": [check],
        "source_ref_ids": SOURCE_IDS,
    }


def _blueprint(
    blueprint_id: str,
    title: str,
    summary: str,
    modes: list[str],
) -> dict[str, Any]:
    return {
        "id": blueprint_id,
        "title": title,
        "summary": summary,
        "practice_modes": modes,
        "source_ref_ids": SOURCE_IDS,
    }


def _scenario(
    scenario_id: str,
    title: str,
    scenario: str,
    choices: list[str],
    correct: str,
    distractors: list[str],
) -> dict[str, Any]:
    return {
        "id": scenario_id,
        "title": title,
        "summary": "Original apprenticeship entrance practice item.",
        "scenario": [scenario],
        "choices": choices,
        "correct_rationale": [correct],
        "distractor_rationales": distractors,
        "source_ref_ids": SOURCE_IDS,
    }


def new_lessons() -> list[dict[str, Any]]:
    return [
        _lesson(
            "cec-lesson-entrance-2-week-diagnostic-map",
            "Two-week entrance diagnostic map",
            "A near-term learner needs a fast baseline, not a broad trade survey.",
            "Teach the learner to split preparation into five lanes: math setup, numerical pattern, reading evidence, mechanical trace, and spatial tracking. The first session should sample all five, then spend most daily time on the weakest two lanes while keeping a short mixed set every day.",
            [
                "Start with a timed mixed baseline before choosing drills.",
                "Mark each miss with one primary tag: setup, arithmetic, misread, evidence, mechanical trace, spatial track, or pacing.",
                "Do not postpone weak sections; rotate them daily in short blocks.",
            ],
            "For a test soon, what should the first study session produce: a weakness map, a contractor-law outline, a NEC article list, or a memorized answer sheet?",
        ),
        _lesson(
            "cec-lesson-entrance-no-calculator-decimals",
            "No-calculator decimal arithmetic",
            "Decimal placement and estimation protect many easy points.",
            "Teach decimal arithmetic with a three-step check: ignore decimals briefly, compute the whole-number shape, then place the decimal by magnitude. Before selecting an answer, estimate whether the result should be less than 1, between 1 and 10, or larger than 10.",
            [
                "Use estimation before exact arithmetic.",
                "Align decimal places for addition and subtraction.",
                "For multiplication, count decimal places after multiplying whole numbers.",
            ],
            "When multiplying 0.6 by 0.08, why should the answer be less than 0.1?",
        ),
        _lesson(
            "cec-lesson-entrance-fractions-ratios",
            "Fractions, ratios, and proportions under time pressure",
            "Most ratio errors come from comparing the wrong part to the wrong whole.",
            "Teach every ratio problem as parts first. Add the ratio parts to get the total parts, divide the real total by total parts, then multiply by the requested part. For percent problems, name the base before calculating.",
            [
                "In a ratio A:B, the whole is A+B parts unless the question says otherwise.",
                "Percent change uses the original value as the base.",
                "Cross-multiply only after writing matching units on both sides.",
            ],
            "In a 2:3 mix with 40 total items, why is one part worth 8?",
        ),
        _lesson(
            "cec-lesson-entrance-algebra-functions",
            "Algebra and function-table recognition",
            "ETA-style samples make algebra/function practice a high-value preparation lane.",
            "Teach the learner to identify whether a question asks for substitution, solving for x, slope, pattern continuation, or function output. The safe routine is: copy the rule, substitute carefully, simplify one operation at a time, and check with estimation.",
            [
                "Function notation means input-output, not multiplication by a letter.",
                "When solving equations, keep both sides balanced.",
                "For tables, test differences, multiplication, and simple linear rules before guessing.",
            ],
            "If f(x)=3x+2, what does f(4) ask you to do?",
        ),
        _lesson(
            "cec-lesson-entrance-reading-evidence-ladder",
            "Reading evidence ladder",
            "Technical reading should be passage-first and qualifier-aware.",
            "Teach a ladder: read the question, locate the controlling sentence, underline qualifiers, predict the answer in plain words, then match the choice. Outside knowledge is useful after the exam, but it can hurt reading questions when it overrides the passage.",
            [
                "Answer from passage evidence, not from what sounds professional.",
                "Watch qualifiers: only, always, except, before, after, unless.",
                "A correct answer may be less dramatic than a distractor.",
            ],
            "If a choice is true in real life but not supported by the passage, should you select it?",
        ),
        _lesson(
            "cec-lesson-entrance-mechanical-force-distance",
            "Mechanical advantage: force versus distance",
            "Levers and pulleys often trade force for distance.",
            "Teach the simple idea: a machine can make a force feel smaller, but the work is paid back through more distance or more movement. For test reasoning, trace the input point, output point, pivot or support, and direction of motion before choosing.",
            [
                "Longer lever arm usually means less force for the same turning effect.",
                "A fixed pulley changes direction; a movable pulley can reduce effort force.",
                "Mechanical advantage is a relationship, not a magic energy gain.",
            ],
            "If a longer handle makes a wrench easier to turn, what changed: force needed, bolt material, wire color, or reading speed?",
        ),
        _lesson(
            "cec-lesson-entrance-gear-pulley-direction",
            "Gear and pulley direction tracing",
            "Direction errors are preventable if the learner traces one contact at a time.",
            "Teach a one-connection rule: each pair of touching gears reverses direction; gears on the same shaft rotate together; crossed belts reverse direction while open belts usually keep direction. Draw arrows before thinking about speed.",
            [
                "Touching gears alternate direction.",
                "Same-shaft parts share rotation direction.",
                "Speed changes depend on relative size.",
            ],
            "If gear A touches gear B and B touches gear C, does C turn the same direction as A or opposite?",
        ),
        _lesson(
            "cec-lesson-entrance-spatial-fold-hole-punch",
            "Paper folding and hole-punch tracking",
            "Spatial items reward slow, ordered unfolding.",
            "Teach the learner to reverse the folds one at a time. Each unfold mirrors the mark across the fold line. Do not rotate the mental picture unless the problem explicitly rotates the paper.",
            [
                "Reverse the last fold first.",
                "Mirror across the fold line at each unfold.",
                "Separate reflection from rotation.",
            ],
            "When unfolding a folded paper, should you reverse the first fold first or the last fold first?",
        ),
        _lesson(
            "cec-lesson-entrance-pef-evidence-stories",
            "Personal Experience Form evidence stories",
            "PEF preparation should collect honest evidence, not polished fiction.",
            "Teach the learner to organize experiences into situation, task, action, result, and evidence. Good entries show reliability, follow-through, math/technical exposure, teamwork, safety mindset, and learning attitude. The learner should not invent experience or copy generic wording.",
            [
                "Use real examples from work, school, volunteering, projects, or family responsibilities.",
                "Attach evidence to claims: dates, role, supervisor, project, outcome.",
                "Avoid exaggeration; consistency matters across application, PEF, and interview.",
            ],
            "What is stronger for PEF: a specific honest example or a vague claim that sounds impressive?",
        ),
        _lesson(
            "cec-lesson-entrance-final-72-hours",
            "Final 72-hour readiness routine",
            "The final days should protect accuracy, sleep, documents, and confidence.",
            "Teach the learner to stop cramming broad new material. Use short mixed sets, review recurring error tags, prepare documents and route logistics, and sleep. The aim is stable performance, not exhausting practice volume.",
            [
                "Run short mixed practice, not marathon study.",
                "Review the top three error tags and one fix for each.",
                "Confirm ID, arrival time, address, parking, and permitted materials.",
            ],
            "In the final 72 hours, what matters more: stable accuracy and logistics, or learning every possible trade topic?",
        ),
    ]


def new_blueprints() -> list[dict[str, Any]]:
    return [
        _blueprint("cec-practice-entrance-10-minute-arithmetic-sprint", "10-minute arithmetic sprint", "Generate 12 original no-calculator items covering decimals, fractions, percentages, ratios, and unit conversion.", ["timed sprint", "answer-only first pass", "worked review by arithmetic tag"]),
        _blueprint("cec-practice-entrance-algebra-function-table", "Algebra and function-table set", "Generate original substitution, solve-for-x, slope, and table-rule questions.", ["untimed method drill", "timed 8-item set", "wrong-rule remediation"]),
        _blueprint("cec-practice-entrance-reading-evidence-set", "Reading evidence set", "Generate short technical passages with main idea, detail, inference, and qualifier traps.", ["passage annotation", "multiple-choice check", "one-sentence evidence answer"]),
        _blueprint("cec-practice-entrance-mechanical-trace-set", "Mechanical trace set", "Generate lever, pulley, gear, wheel, inclined-plane, and motion-direction items.", ["visual trace", "direction-only drill", "force-distance explanation"]),
        _blueprint("cec-practice-entrance-spatial-folding-set", "Spatial folding set", "Generate original folding, rotation, reflection, and unfolded-pattern prompts.", ["slow unfold", "timed spatial set", "reflection-vs-rotation remediation"]),
        _blueprint("cec-practice-entrance-half-mock", "Entrance half-mock", "Generate a balanced half-length practice block across math, numerical, reading, mechanical, and spatial lanes.", ["timed mixed block", "skip-and-return pacing", "error heatmap review"]),
        _blueprint("cec-practice-entrance-full-mock-rehearsal", "Entrance full-mock rehearsal", "Generate a longer original rehearsal with section pacing, confidence marking, and post-test triage.", ["timed rehearsal", "confidence marking", "readiness gate"]),
        _blueprint("cec-practice-entrance-pef-interview-bridge", "PEF-to-interview bridge", "Generate prompts that convert honest experience evidence into concise interview-ready stories.", ["STAR evidence drafting", "claim-evidence check", "two-minute spoken rehearsal"]),
    ]


def new_activities() -> list[dict[str, Any]]:
    return [
        {
            "id": "cec-activity-entrance-daily-rotation",
            "title": "Entrance daily rotation",
            "summary": "A short daily block for learners with an exam soon.",
            "activity_modes": ["warmup", "weak-lane drill", "mixed quick check", "error tag"],
            "steps": [
                "Run three easy arithmetic warmups.",
                "Drill the weakest lane for 12-15 minutes.",
                "Run a five-question mixed set.",
                "Record one error tag and one fix.",
            ],
            "learner_action": ["Answer quickly.", "Review only missed or guessed items.", "Name the next drill lane."],
            "feedback_rule": ["Prefer immediate feedback.", "Move on after one correct quick check unless confidence is low."],
            "exam_alignment": ["Builds section switching and pacing for aptitude testing."],
        },
        {
            "id": "cec-activity-entrance-evidence-reading",
            "title": "Evidence-first reading drill",
            "summary": "A technical reading routine that prevents unsupported-answer mistakes.",
            "activity_modes": ["question-first scan", "evidence underline", "choice elimination"],
            "steps": [
                "Read the question before the passage.",
                "Find the controlling sentence.",
                "Predict the answer in plain language.",
                "Select the matching option and cite the phrase.",
            ],
            "learner_action": ["Provide an answer and the evidence phrase."],
            "feedback_rule": ["Grade unsupported claims as reading-evidence errors even if they sound plausible."],
            "exam_alignment": ["Matches reading-comprehension selection logic."],
        },
        {
            "id": "cec-activity-entrance-mechanical-sketch",
            "title": "Mechanical one-sketch trace",
            "summary": "A visual trace routine for levers, gears, pulleys, and motion.",
            "activity_modes": ["sketch", "arrow trace", "answer"],
            "steps": [
                "Identify input, output, support, and contact points.",
                "Draw one arrow at the input.",
                "Propagate one connection at a time.",
                "Answer only after the trace is complete.",
            ],
            "learner_action": ["Explain the trace in one or two sentences."],
            "feedback_rule": ["Correct direction errors by replaying the first wrong connection."],
            "exam_alignment": ["Supports mechanical reasoning without requiring trade knowledge."],
        },
        {
            "id": "cec-activity-entrance-pacing-lab",
            "title": "Pacing and confidence lab",
            "summary": "A timed block that trains skip, return, and confidence marking.",
            "activity_modes": ["timed set", "confidence mark", "review"],
            "steps": [
                "Mark each answer as sure, maybe, or guessed.",
                "Skip any item that exceeds the time budget.",
                "Return after easier items are complete.",
                "Review misses by accuracy and confidence.",
            ],
            "learner_action": ["Submit answers plus confidence marks."],
            "feedback_rule": ["Prioritize high-confidence misses and slow correct answers in remediation."],
            "exam_alignment": ["Builds reliable scoring behavior under time pressure."],
        },
    ]


def new_sequences() -> list[dict[str, Any]]:
    return [
        {
            "id": "cec-sequence-entrance-two-week-urgent-sprint",
            "title": "Entrance Exam two-week urgent sprint",
            "summary": "A compressed route for a learner taking an apprenticeship entrance selection soon.",
            "objective_ids": [
                "cec-apprentice-diagnostic",
                "cec-apprentice-math-reasoning",
                "cec-apprentice-numerical-reasoning",
                "cec-apprentice-reading",
                "cec-apprentice-mechanical",
                "cec-apprentice-spatial",
                "cec-apprentice-timed-practice",
                "cec-apprentice-pef",
            ],
            "lesson_card_ids": [
                "cec-lesson-entrance-2-week-diagnostic-map",
                "cec-lesson-entrance-no-calculator-decimals",
                "cec-lesson-entrance-fractions-ratios",
                "cec-lesson-entrance-algebra-functions",
                "cec-lesson-entrance-reading-evidence-ladder",
                "cec-lesson-entrance-mechanical-force-distance",
                "cec-lesson-entrance-spatial-fold-hole-punch",
                "cec-lesson-entrance-final-72-hours",
            ],
            "activity_template_ids": [
                "cec-activity-entrance-daily-rotation",
                "cec-activity-entrance-evidence-reading",
                "cec-activity-entrance-mechanical-sketch",
                "cec-activity-entrance-pacing-lab",
            ],
            "checkpoint_prompts": [
                "Can the learner keep arithmetic accuracy while moving fast?",
                "Can the learner cite reading evidence rather than guess?",
                "Can the learner trace mechanical and spatial items one step at a time?",
            ],
            "mastery_evidence": [
                "two mixed sets with error tags",
                "one half-mock review",
                "ready/not-ready decision before final-week practice",
            ],
        },
        {
            "id": "cec-sequence-entrance-math-repair",
            "title": "Entrance math repair lane",
            "summary": "A focused lane for learners missing arithmetic, ratio, algebra, or table-rule items.",
            "objective_ids": [
                "cec-foundation-arithmetic",
                "cec-foundation-algebra",
                "cec-apprentice-math-reasoning",
                "cec-apprentice-numerical-reasoning",
            ],
            "lesson_card_ids": [
                "cec-lesson-entrance-no-calculator-decimals",
                "cec-lesson-entrance-fractions-ratios",
                "cec-lesson-entrance-algebra-functions",
                "cec-lesson-apprentice-table-graph-reading",
            ],
            "activity_template_ids": [
                "cec-activity-entrance-daily-rotation",
                "cec-activity-error-memory-loop",
            ],
            "checkpoint_prompts": [
                "Can the learner solve before looking at answer choices?",
                "Can the learner explain the setup in one sentence?",
            ],
            "mastery_evidence": [
                "80% or better across two short math sets",
                "no recurring decimal-placement or wrong-base percent errors",
            ],
        },
        {
            "id": "cec-sequence-entrance-visual-reasoning-repair",
            "title": "Entrance visual reasoning repair lane",
            "summary": "A focused lane for mechanical and spatial misses.",
            "objective_ids": [
                "cec-apprentice-mechanical",
                "cec-apprentice-spatial",
                "cec-apprentice-timed-practice",
            ],
            "lesson_card_ids": [
                "cec-lesson-entrance-mechanical-force-distance",
                "cec-lesson-entrance-gear-pulley-direction",
                "cec-lesson-entrance-spatial-fold-hole-punch",
                "cec-lesson-apprentice-spatial-rotation",
            ],
            "activity_template_ids": [
                "cec-activity-entrance-mechanical-sketch",
                "cec-activity-entrance-pacing-lab",
            ],
            "checkpoint_prompts": [
                "Can the learner trace one connection at a time?",
                "Can the learner distinguish rotation from reflection?",
            ],
            "mastery_evidence": [
                "70% or better on mechanical/spatial mixed cards",
                "learner can verbalize the first trace step before answering",
            ],
        },
    ]


def new_scenarios() -> list[dict[str, Any]]:
    return [
        _scenario("cec-scenario-entrance-decimal-wire-cost", "Decimal multiplication: wire cost", "Wire costs $0.18 per foot. What is the cost of 25 feet?", ["A) $0.45", "B) $4.50", "C) $45.00", "D) $450.00"], "18 cents times 25 is 450 cents, or $4.50.", ["A misses a decimal place.", "C is ten times too large.", "D is one hundred times too large."]),
        _scenario("cec-scenario-entrance-percent-increase-hours", "Percent increase: practice hours", "A learner increases daily practice from 40 minutes to 50 minutes. What is the percent increase?", ["A) 10%", "B) 20%", "C) 25%", "D) 50%"], "The increase is 10 minutes. 10 divided by the original 40 is 25%.", ["A uses the increase as raw points.", "B divides by 50.", "D confuses 10 with half of 20."]),
        _scenario("cec-scenario-entrance-ratio-crews", "Ratio: crew assignment", "For every 4 apprentices there are 3 journey workers. If 28 workers are present, how many are apprentices?", ["A) 12", "B) 14", "C) 16", "D) 21"], "The ratio has 7 parts. 28/7=4 per part. Apprentices are 4 parts, so 16.", ["12 gives journey workers.", "14 assumes half.", "21 uses 3/4 of the total."]),
        _scenario("cec-scenario-entrance-unit-conversion-conduit", "Unit conversion: conduit length", "A piece is 7 feet 6 inches long. How many inches is that?", ["A) 42", "B) 78", "C) 84", "D) 90"], "7 feet is 84 inches; plus 6 inches is 90.", ["42 halves the feet.", "78 subtracts 6.", "84 forgets the extra 6 inches."]),
        _scenario("cec-scenario-entrance-average-scores", "Average: practice scores", "Three scores are 72, 84, and 90. What fourth score makes the average 82?", ["A) 76", "B) 78", "C) 80", "D) 82"], "Four scores averaging 82 total 328. Current total is 246. The fourth score is 82.", ["76 uses a wrong target total.", "78 is close but low.", "80 estimates without exact total."]),
        _scenario("cec-scenario-entrance-sequence-add", "Sequence: increasing differences", "What comes next: 3, 6, 10, 15, 21, ?", ["A) 25", "B) 27", "C) 28", "D) 30"], "The differences are +3,+4,+5,+6, so next is +7 and the answer is 28.", ["25 repeats +4.", "27 adds +6 again.", "30 jumps by +9."]),
        _scenario("cec-scenario-entrance-function-output", "Function output", "If f(x)=2x^2-1, what is f(3)?", ["A) 11", "B) 17", "C) 18", "D) 35"], "2 times 3 squared is 18; 18 minus 1 is 17.", ["11 squares after multiplying.", "18 forgets minus 1.", "35 uses 2 times 9 plus 17."]),
        _scenario("cec-scenario-entrance-solve-x", "Solve for x", "Solve: 3x + 5 = 20.", ["A) 3", "B) 5", "C) 8", "D) 15"], "Subtract 5 to get 15, then divide by 3 to get 5.", ["3 divides too early.", "8 adds values.", "15 stops before dividing."]),
        _scenario("cec-scenario-entrance-table-rate", "Table rate comparison", "Crew A installs 18 devices in 3 hours. Crew B installs 20 devices in 5 hours. Which crew has the higher hourly rate?", ["A) Crew A", "B) Crew B", "C) Same rate", "D) Cannot tell"], "Crew A is 6 per hour; Crew B is 4 per hour.", ["B compares raw devices only.", "C assumes similar totals.", "D ignores hours given."]),
        _scenario("cec-scenario-entrance-reading-qualifier", "Reading qualifier: before", "Passage: Before using a tool, the trainee must inspect the cord and report visible damage. Question: What must happen before use?", ["A) Replace every cord", "B) Inspect the cord and report visible damage", "C) Use the tool first", "D) Ask for a new task"], "The passage says inspect the cord and report visible damage before use.", ["A adds every cord replacement.", "C reverses before/after.", "D is not supported."]),
        _scenario("cec-scenario-entrance-reading-except", "Reading qualifier: except", "Passage: The class meets Monday through Thursday. Attendance is recorded at the start of each class. Which statement is NOT supported?", ["A) Class meets on Monday", "B) Attendance is recorded", "C) Class meets on Friday", "D) Class meets on Thursday"], "Friday is not included in Monday through Thursday.", ["A is supported.", "B is supported.", "D is supported."]),
        _scenario("cec-scenario-entrance-main-idea", "Reading main idea", "Passage: The applicant should arrive early, bring required identification, and follow staff instructions. These steps reduce delays during check-in. What is the main idea?", ["A) Check-in readiness prevents delays", "B) Identification is optional", "C) Staff instructions are unnecessary", "D) Arriving late saves time"], "The passage groups actions that reduce check-in delays.", ["B contradicts required ID.", "C contradicts instructions.", "D contradicts arriving early."]),
        _scenario("cec-scenario-entrance-inference", "Reading inference", "Passage: If a form is incomplete, staff may ask the applicant to correct it before the next step. What can be inferred?", ["A) Complete forms help the process move forward", "B) Staff never review forms", "C) Incomplete forms are ignored", "D) The applicant skips all steps"], "If incomplete forms must be corrected before the next step, complete forms support progress.", ["B contradicts review.", "C contradicts correction.", "D invents a skip."]),
        _scenario("cec-scenario-entrance-lever-handle", "Lever handle", "Two identical wrenches are used on the same bolt. Wrench A has a longer handle. Which usually requires less force at the hand?", ["A) Wrench A", "B) Wrench B", "C) Both require no force", "D) Handle length never matters"], "A longer handle gives more turning effect for the same force.", ["B reverses lever advantage.", "C ignores force.", "D ignores lever arm."]),
        _scenario("cec-scenario-entrance-fixed-pulley", "Fixed pulley direction", "A rope passes over a fixed pulley. Pulling down on one side lifts the load on the other. What does the fixed pulley mainly change?", ["A) Direction of force", "B) Weight of the load to zero", "C) Material of the rope", "D) The need for support"], "A fixed pulley mainly changes pulling direction.", ["B invents zero weight.", "C is unrelated.", "D ignores the pulley support."]),
        _scenario("cec-scenario-entrance-gear-three", "Three touching gears", "Gear A touches B, and B touches C. If A turns clockwise, which way does C turn?", ["A) Clockwise", "B) Counterclockwise", "C) It stops", "D) Direction cannot be traced"], "A reverses B; B reverses C, so C matches A.", ["B misses the second reversal.", "C invents stopping.", "D ignores traceable contacts."]),
        _scenario("cec-scenario-entrance-belt-open", "Open belt direction", "Two pulleys are connected by an open belt that is not crossed. If the first turns clockwise, the second usually turns which way?", ["A) Clockwise", "B) Counterclockwise", "C) It always doubles speed", "D) It cannot move"], "An open belt usually keeps rotation direction.", ["B describes a crossed-belt style.", "C confuses direction and speed.", "D ignores belt transfer."]),
        _scenario("cec-scenario-entrance-inclined-plane", "Inclined plane", "A heavy box is moved up a long ramp instead of lifted straight up. What is the main tradeoff?", ["A) Less force over more distance", "B) More force over less distance", "C) No work is needed", "D) Gravity disappears"], "A ramp can reduce required force by spreading work over longer distance.", ["B reverses the tradeoff.", "C violates work idea.", "D is impossible."]),
        _scenario("cec-scenario-entrance-paper-one-fold", "Paper fold one time", "A square paper is folded left over right, then one hole is punched near the folded edge. After unfolding, what happens?", ["A) One hole only", "B) Two mirrored holes", "C) Four holes in a circle", "D) No holes"], "One fold creates a mirrored pair when unfolded.", ["A forgets the folded layers.", "C assumes two folds.", "D ignores the punch."]),
        _scenario("cec-scenario-entrance-rotation-reflection", "Rotation versus reflection", "A shape is flipped over a vertical line. Which description is best?", ["A) Reflection", "B) Rotation", "C) Translation only", "D) Enlargement"], "Flipping across a line is reflection.", ["B turns around a point.", "C slides without flipping.", "D changes size."]),
        _scenario("cec-scenario-entrance-fold-order", "Fold order", "A paper is folded twice, first horizontally then vertically. When reasoning backward, which fold should be undone first?", ["A) Vertical fold", "B) Horizontal fold", "C) Both at once", "D) Neither fold"], "Reverse operations undo the last fold first, so vertical is first to undo.", ["B undoes the first fold first.", "C loses tracking.", "D gives up."]),
        _scenario("cec-scenario-entrance-cube-net", "Cube net adjacency", "On a cube net, two squares share an edge before folding. What is usually true after folding?", ["A) They become adjacent faces", "B) They vanish", "C) They must be opposite faces", "D) They become the same face"], "Shared-edge squares in a valid cube net usually fold into adjacent faces.", ["B is impossible.", "C confuses opposite with adjacent.", "D merges faces."]),
        _scenario("cec-scenario-entrance-pacing-skip", "Pacing decision", "A spatial item has taken too long and easier questions remain. What is the best scoring move?", ["A) Mark it and return", "B) Spend all remaining time", "C) Quit the section", "D) Randomly change previous answers"], "Mark-and-return protects easier points and keeps momentum.", ["B risks many easy points.", "C forfeits work.", "D introduces new errors."]),
        _scenario("cec-scenario-entrance-confidence-review", "Confidence review", "After a timed set, which miss should be reviewed first?", ["A) A high-confidence wrong answer", "B) A skipped hard item", "C) A correct sure answer", "D) The neatest solution"], "High-confidence misses reveal dangerous misconceptions.", ["B matters later but may be expected difficulty.", "C is low priority.", "D is not an error criterion."]),
        _scenario("cec-scenario-entrance-pef-specificity", "PEF specificity", "Which PEF statement is strongest?", ["A) I am good with tools", "B) I helped repair a fence every Saturday for six weeks and tracked materials", "C) I always work harder than everyone", "D) I deserve a chance"], "Specific, honest evidence beats vague claims.", ["A is vague.", "C is broad and hard to verify.", "D is motivation without evidence."]),
    ]


def new_flashcards() -> list[dict[str, Any]]:
    return [
        {"id": "cec-flashcards-entrance-no-calculator", "title": "Entrance no-calculator arithmetic", "summary": "Fast cues for arithmetic under time pressure.", "cards": ["Estimate magnitude before calculating.", "Percent change uses original value as the base.", "Ratio total parts usually means add the parts.", "For decimal multiplication, multiply first and place decimals last.", "Convert feet to inches by multiplying by 12."], "source_ref_ids": SOURCE_IDS},
        {"id": "cec-flashcards-entrance-algebra-functions", "title": "Entrance algebra and functions", "summary": "Recognition cards for algebra/function items.", "cards": ["f(4) means substitute 4 for x.", "Solve equations by keeping both sides balanced.", "Table rules often start with differences or multiplication.", "Slope is change in y divided by change in x.", "Check final answers by substitution when possible."], "source_ref_ids": SOURCE_IDS},
        {"id": "cec-flashcards-entrance-reading-evidence", "title": "Entrance reading evidence", "summary": "Passage-first reading cards.", "cards": ["Question first, passage second.", "Locate the controlling sentence.", "Qualifiers decide many answers: only, always, except, before, after.", "Outside knowledge cannot replace passage evidence.", "Unsupported but plausible choices are traps."], "source_ref_ids": SOURCE_IDS},
        {"id": "cec-flashcards-entrance-mechanical-advantage", "title": "Entrance mechanical advantage", "summary": "Levers, pulleys, and direction trace cards.", "cards": ["Longer lever arm usually reduces effort force.", "Fixed pulley changes force direction.", "Movable pulley can reduce effort by increasing rope movement.", "Touching gears reverse direction.", "Open belts usually keep direction; crossed belts reverse direction."], "source_ref_ids": SOURCE_IDS},
        {"id": "cec-flashcards-entrance-visual-spatial", "title": "Entrance visual-spatial tracking", "summary": "Spatial reasoning cards.", "cards": ["Undo the last fold first.", "Each unfold mirrors across the fold line.", "Reflection flips; rotation turns.", "Do not rotate the page mentally unless the item rotates it.", "Shared edges on cube nets usually become adjacent faces."], "source_ref_ids": SOURCE_IDS},
    ]


def new_checkpoints() -> list[dict[str, Any]]:
    return [
        {
            "id": "cec-checkpoint-entrance-two-week-routing",
            "title": "Entrance two-week routing checkpoint",
            "summary": "Use after the first diagnostic to route the learner into math, reading, mechanical, spatial, or mixed practice.",
            "checkpoint_prompts": [
                "Which two lanes produced the most misses?",
                "Were misses mostly method errors, careless arithmetic, reading evidence errors, visual trace errors, or pacing errors?",
                "Can the learner complete a five-question mixed set without asking what to study next?",
            ],
            "mastery_evidence": [
                "a ranked weakness list",
                "at least one corrective drill selected",
                "a daily rotation plan for the next three sessions",
            ],
            "remediation": [
                "If no weakness pattern is known, run a mixed diagnostic.",
                "If math is weak, use the math repair lane.",
                "If visual reasoning is weak, use the visual reasoning repair lane.",
            ],
            "source_ref_ids": SOURCE_IDS,
        },
        {
            "id": "cec-checkpoint-entrance-section-switching",
            "title": "Entrance section-switching checkpoint",
            "summary": "Use before longer timed practice to confirm the learner can switch question types without losing method.",
            "checkpoint_prompts": [
                "Can the learner name the lane before solving?",
                "Can the learner skip a time trap without emotional derailment?",
                "Can the learner preserve accuracy after switching from reading to math or spatial to mechanical?",
            ],
            "mastery_evidence": [
                "70% or better on a mixed switching drill",
                "all skipped questions marked for return",
                "one post-set error tag per miss",
            ],
            "remediation": [
                "If switching causes accuracy collapse, shorten blocks and alternate only two lanes.",
                "If pacing fails, use the pacing lab template.",
            ],
            "source_ref_ids": SOURCE_IDS,
        },
        {
            "id": "cec-checkpoint-entrance-pef-readiness",
            "title": "PEF evidence readiness checkpoint",
            "summary": "Use after PEF preparation to confirm the learner has honest, specific examples ready.",
            "checkpoint_prompts": [
                "Can each claim be tied to a concrete example?",
                "Does the learner avoid exaggerating trade experience?",
                "Can the learner explain reliability, learning attitude, teamwork, and safety mindset with evidence?",
            ],
            "mastery_evidence": [
                "three specific experience stories",
                "each story has situation, action, result, and evidence",
                "no unsupported or inflated claim remains",
            ],
            "remediation": [
                "If examples are vague, ask for dates, setting, task, action, and outcome.",
                "If experience is limited, use school, volunteer, family, project, or work responsibility evidence.",
            ],
            "source_ref_ids": SOURCE_IDS,
        },
    ]


def new_errors() -> list[dict[str, Any]]:
    return [
        {"id": "cec-error-entrance-decimal-placement", "title": "Decimal placement error", "summary": "The learner performs the operation but places the decimal by pattern matching instead of magnitude.", "remediation": ["Estimate the answer range first.", "Redo the item with whole-number multiplication and decimal-place count.", "Ask one similar item with different numbers."]},
        {"id": "cec-error-entrance-reading-unsupported-choice", "title": "Unsupported reading choice", "summary": "The learner chooses a plausible answer that is not actually supported by the passage.", "remediation": ["Ask for the controlling sentence.", "Have the learner eliminate any choice that adds an unsupported claim.", "Repeat with an except/before/after qualifier item."]},
        {"id": "cec-error-entrance-visual-trace-skip", "title": "Visual trace skip", "summary": "The learner jumps to the answer without tracing fold, gear, pulley, or lever relationships one connection at a time.", "remediation": ["Force an arrow or unfold step before answering.", "Replay only the first wrong connection.", "Use a slower no-timer item before returning to timed practice."]},
        {"id": "cec-error-entrance-confidence-miscalibration", "title": "Confidence miscalibration", "summary": "The learner is highly confident on wrong answers or repeatedly guesses without marking uncertainty.", "remediation": ["Record sure/maybe/guess on each timed answer.", "Review high-confidence misses first.", "Ask the learner to state the method before seeing choices."]},
    ]


def new_provenance_refs() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "eta.application_process.2026-09-04",
            "managed_by": "Cognisphere",
            "materialized_at": "2026-09-04",
            "claim_summaries": [
                "Electrical Training Alliance describes apprenticeship application flow at a high level, including application, aptitude testing, and interview-related progression.",
                "Tutor should use this as broad process context only; local program notices control exact applicant requirements.",
            ],
        },
        {
            "source_id": "eta.online_tech_math.2026-09-04",
            "managed_by": "Cognisphere",
            "materialized_at": "2026-09-04",
            "claim_summaries": [
                "Electrical Training Alliance offers an online tech math course as a preparation/resource path for algebra and technical math readiness.",
                "Tutor may use the existence of this preparation route to reinforce algebra and function practice, without reproducing proprietary course material.",
            ],
        },
    ]


def _sync_metadata(knowledge: dict[str, Any]) -> None:
    metadata = knowledge.setdefault("pack_metadata", {})
    count_keys = {
        "lesson_card_count": "lesson_cards",
        "practice_blueprint_count": "practice_blueprints",
        "learning_activity_template_count": "learning_activity_templates",
        "study_sequence_count": "study_sequences",
        "scenario_card_count": "scenario_cards",
        "flashcard_deck_count": "flashcard_decks",
        "readiness_checkpoint_count": "readiness_checkpoints",
        "error_taxonomy_count": "error_taxonomy",
    }
    for meta_key, list_key in count_keys.items():
        metadata[meta_key] = len(knowledge.get(list_key) or [])
    metadata["stage"] = "M0/M2 expanded entrance exam content seed"


def thicken(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    knowledge = data.setdefault("knowledge", {})
    changes = {
        "lesson_cards": _append_unique(knowledge.setdefault("lesson_cards", []), new_lessons()),
        "practice_blueprints": _append_unique(
            knowledge.setdefault("practice_blueprints", []), new_blueprints()
        ),
        "learning_activity_templates": _append_unique(
            knowledge.setdefault("learning_activity_templates", []), new_activities()
        ),
        "study_sequences": _append_unique(knowledge.setdefault("study_sequences", []), new_sequences()),
        "scenario_cards": _append_unique(knowledge.setdefault("scenario_cards", []), new_scenarios()),
        "flashcard_decks": _append_unique(
            knowledge.setdefault("flashcard_decks", []), new_flashcards()
        ),
        "readiness_checkpoints": _append_unique(
            knowledge.setdefault("readiness_checkpoints", []), new_checkpoints()
        ),
        "error_taxonomy": _append_unique(knowledge.setdefault("error_taxonomy", []), new_errors()),
        "cognisphere_provenance_refs": _append_unique(
            knowledge.setdefault("cognisphere_provenance_refs", []), new_provenance_refs()
        ),
    }
    _sync_metadata(knowledge)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changes


def main() -> None:
    result = {"bundle": thicken(BUNDLE_PATH)}
    if IMPORT_CACHE_PATH.exists():
        result["import_cache"] = thicken(IMPORT_CACHE_PATH)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
