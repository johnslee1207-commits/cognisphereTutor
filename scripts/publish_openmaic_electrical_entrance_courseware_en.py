"""Publish English OpenMAIC courseware for electrician entrance exam prep."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import time
from typing import Any

import httpx

COURSE_ID = "california-electrical-entrance-courseware-en-v1"
DEFAULT_OPENMAIC_ORIGIN = "http://127.0.0.1:33100"
DEFAULT_TOKEN = "openmaic-dev-token"
ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = (
    ROOT
    / "cognispheretutor"
    / "integrations"
    / "cognisphere"
    / "bundled_packs"
    / "california_electrical_career_bundle.json"
)
SEED_DIR = ROOT / "cognispheretutor" / "vendor" / "openmaic-courseware"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default=DEFAULT_OPENMAIC_ORIGIN)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--course-id", default=COURSE_ID)
    parser.add_argument(
        "--owner-cookie",
        help="OpenMAIC anonymous_id cookie for overwriting an existing owned document.",
    )
    parser.add_argument(
        "--write-seed",
        action="store_true",
        help="Write the English classroom JSON into Tutor's packaged seed directory.",
    )
    args = parser.parse_args()

    origin = args.origin.rstrip("/")
    document = build_document(args.course_id)
    if args.write_seed:
        seed_path = write_seed_document(document, args.course_id)
        print(json.dumps({"ok": True, "seed_path": str(seed_path)}, ensure_ascii=False, indent=2))
        return

    headers = {"authorization": f"Bearer {args.token}"}
    if args.owner_cookie:
        headers["cookie"] = f"anonymous_id={args.owner_cookie}"

    with httpx.Client(timeout=60) as client:
        persistence = client.put(
            f"{origin}/api/persistence/documents/{args.course_id}",
            headers=headers,
            json=document,
        )
        persistence_status: dict[str, Any] = {"status_code": persistence.status_code}
        if persistence.is_success:
            persistence_status["ok"] = True
        else:
            persistence_status["ok"] = False
            persistence_status["message"] = persistence.text[:300]

        classroom = client.post(
            f"{origin}/api/classroom",
            json={"stage": document["stage"], "scenes": document["scenes"]},
        )
        classroom.raise_for_status()
        classroom_payload = classroom.json()

    print(
        json.dumps(
            {
                "ok": True,
                "course_id": args.course_id,
                "scene_count": len(document["scenes"]),
                "persistence": persistence_status,
                "classroom_url": classroom_payload.get(
                    "url", f"{origin}/classroom/{args.course_id}"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_document(course_id: str) -> dict[str, Any]:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    now = int(time.time() * 1000)
    return {
        "stage": {
            "id": course_id,
            "name": "California Electrical Entrance Exam Prep Courseware",
            "description": (
                "Full English OpenMAIC courseware for electrician apprenticeship "
                "entrance preparation, diagnostics, instruction, and practice."
            ),
            "createdAt": now,
            "updatedAt": now,
            "languageDirective": "en-US",
            "style": "deeptutor-entrance-courseware-en",
        },
        "scenes": courseware_scenes(course_id),
        "outline": {
            "source": "cognisphereTutor",
            "bundle_id": bundle["bundle_id"],
            "mode": "electrical_entrance_courseware_en",
            "source_policy": bundle["safety"]["source_of_truth"],
        },
    }


def write_seed_document(document: dict[str, Any], course_id: str) -> Path:
    packaged = json.loads(json.dumps(document, ensure_ascii=False))
    packaged["stage"]["createdAt"] = 0
    packaged["stage"]["updatedAt"] = 0
    for scene in packaged["scenes"]:
        scene["createdAt"] = 0
        scene["updatedAt"] = 0
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    path = SEED_DIR / f"{course_id}.json"
    path.write_text(json.dumps(packaged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def courseware_scenes(course_id: str) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = [
        lecture(
            "Course Goal: Prepare for the Entrance Exam, Not Field Licensing",
            [
                "This course targets common electrician apprenticeship entrance skills.",
                "You will train math, reading, mechanical reasoning, spatial reasoning, and evidence-based self-planning.",
                "The course uses original practice items and step-by-step explanations.",
                "Do not depend on leaked test questions. Build transferable speed and accuracy.",
            ],
        ),
        quiz(
            "Readiness Check: What This Course Is For",
            [
                q(
                    "What is the safest preparation strategy when the exact local exam version is unknown?",
                    [
                        "Memorize unverified online answer keys",
                        "Build core skills, then adjust to the official local notice",
                        "Skip reading comprehension",
                        "Study only tool names",
                    ],
                    1,
                    "Exam structures vary. Core skills plus official local guidance is the most reliable path.",
                )
            ],
        ),
    ]
    for module in MODULES:
        specs.extend(module_scenes(module))

    scenes: list[dict[str, Any]] = []
    for order, spec in enumerate(specs, start=1):
        scene_id = f"electrical-en-{order:03d}-{slug(spec['title'])[:40]}"
        if spec["kind"] == "lecture":
            scenes.append(slide_scene(course_id, scene_id, order, spec["title"], spec["lines"]))
        else:
            scenes.append(quiz_scene(course_id, scene_id, order, spec["title"], spec["questions"]))
    return scenes


def module_scenes(module: dict[str, Any]) -> list[dict[str, Any]]:
    name = module["name"]
    skill = module["skill"]
    return [
        lecture(
            f"{name}: What the Exam Is Testing",
            [
                module["purpose"],
                f"Target skill: {skill}.",
                "Work slowly first. Add time pressure only after the method is stable.",
                "During review, write the exact step where the error happened.",
            ],
        ),
        lecture(
            f"{name}: Core Method",
            module["method"],
        ),
        lecture(
            f"{name}: Worked Example",
            module["example"],
        ),
        lecture(
            f"{name}: Common Traps",
            module["traps"],
        ),
        lecture(
            f"{name}: Tutor Diagnosis and Planning",
            [
                f"If errors cluster here, tag the gap as: {module['gap']}.",
                f"Recommended drill: {module['drill']}.",
                "Mastery target: 80 percent accuracy before adding speed.",
                "Planning rule: one concept drill, one mixed drill, and one timed mini-set.",
            ],
        ),
        quiz(
            f"Practice Check: {name}",
            module["questions"],
        ),
    ]


def q(
    question: str,
    choices: list[str],
    answer: int,
    rationale: str,
) -> dict[str, Any]:
    return {
        "id": slug(question)[:48],
        "question": question,
        "choices": choices,
        "answer": answer,
        "rationale": rationale,
    }


def slug(value: str) -> str:
    chars = []
    for char in value.lower():
        if char.isascii() and char.isalnum():
            chars.append(char)
        elif char in {" ", "-", "_"}:
            chars.append("-")
    out = "".join(chars).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out or "course-scene"


MODULES: list[dict[str, Any]] = [
    {
        "name": "Diagnostic Baseline",
        "skill": "turning a score into a study plan",
        "purpose": "The first job is to locate weak skills before choosing practice volume.",
        "method": [
            "Separate accuracy problems from speed problems.",
            "Mark each missed question by skill, not by page number.",
            "Look for repeated causes: arithmetic slip, setup error, vocabulary, or visual rotation.",
            "Build the next practice block from the largest repeated gap.",
        ],
        "example": [
            "A learner misses 5 of 8 fraction questions and 1 of 8 reading questions.",
            "The plan should start with fraction operations, not general test anxiety.",
            "A second short quiz confirms whether the gap is setup, calculation, or both.",
            "Only then should the learner move to mixed timed practice.",
        ],
        "traps": [
            "Do not call every miss a careless mistake.",
            "Do not study only the topic that feels familiar.",
            "Do not use a full-length test when a ten-question diagnostic is enough.",
            "Do not add speed before the method is correct.",
        ],
        "gap": "baseline classification",
        "drill": "10 mixed questions, each labeled by skill and error cause",
        "questions": [
            q(
                "A learner misses mostly ratio questions but finishes on time. What should the next plan emphasize?",
                ["Faster guessing", "Ratio setup practice", "Skipping math", "Mechanical vocabulary only"],
                1,
                "The dominant gap is ratio setup, not speed.",
            ),
            q(
                "Which review note is most useful after a missed question?",
                ["I am bad at tests", "Missed at equation setup", "The answer was B", "Study more"],
                1,
                "A precise error label can drive the next practice block.",
            ),
        ],
    },
    {
        "name": "Whole Numbers and Order of Operations",
        "skill": "accurate arithmetic with multi-step expressions",
        "purpose": "Entrance exams often test whether you can keep operations in the correct order.",
        "method": [
            "Handle parentheses first.",
            "Then multiply and divide from left to right.",
            "Then add and subtract from left to right.",
            "Write one line per operation when the expression is dense.",
        ],
        "example": [
            "Compute 18 + 6 x 3 - 4.",
            "Multiply first: 6 x 3 = 18.",
            "Then 18 + 18 - 4 = 32.",
            "The answer is 32, not 68.",
        ],
        "traps": [
            "Do not add before multiplying just because addition appears first.",
            "Do not skip a line when negative signs are present.",
            "Do not use mental math for every step under time pressure.",
            "Check whether the question asks for a value, a difference, or a total.",
        ],
        "gap": "operation order",
        "drill": "15 expressions with one written intermediate line each",
        "questions": [
            q("What is 7 + 5 x 4?", ["27", "48", "35", "22"], 0, "Multiply first: 5 x 4 = 20; 7 + 20 = 27."),
            q("What should be done first in 3 x (8 - 2)?", ["3 x 8", "8 - 2", "3 + 8", "2 x 3"], 1, "Parentheses come first."),
        ],
    },
    {
        "name": "Fractions",
        "skill": "adding, subtracting, multiplying, and simplifying fractions",
        "purpose": "Fractions appear directly and inside measurement, ratio, and algebra problems.",
        "method": [
            "For addition or subtraction, find a common denominator.",
            "For multiplication, multiply numerators and denominators.",
            "For division, multiply by the reciprocal.",
            "Simplify only after the operation is clear.",
        ],
        "example": [
            "Compute 1/2 + 1/4.",
            "Use denominator 4: 1/2 = 2/4.",
            "Then 2/4 + 1/4 = 3/4.",
            "The answer is 3/4.",
        ],
        "traps": [
            "Do not add denominators when adding fractions.",
            "Do not invert the wrong fraction in division.",
            "Do not convert to decimals if the fraction form is easier.",
            "Watch mixed numbers; convert them before multiplying.",
        ],
        "gap": "fraction operation selection",
        "drill": "four sets: add, subtract, multiply, divide, then one mixed set",
        "questions": [
            q("What is 2/3 + 1/6?", ["3/9", "5/6", "1/2", "2/9"], 1, "2/3 is 4/6, and 4/6 + 1/6 = 5/6."),
            q("What is 3/4 x 8?", ["6", "24/4", "3/32", "8/3"], 0, "8 is 8/1, so 3 x 8 / 4 = 24/4 = 6."),
        ],
    },
    {
        "name": "Decimals and Percent",
        "skill": "converting and using percent change",
        "purpose": "Percent and decimal fluency supports measurement, pay, score, and material questions.",
        "method": [
            "Percent means out of 100.",
            "Move from percent to decimal by dividing by 100.",
            "Percent change equals change divided by original value.",
            "Always identify the original value before calculating.",
        ],
        "example": [
            "A score rises from 40 to 50.",
            "The change is 10.",
            "10 divided by the original 40 equals 0.25.",
            "The increase is 25 percent.",
        ],
        "traps": [
            "Do not divide by the new value unless the question asks for that comparison.",
            "Do not confuse percentage points with percent change.",
            "Do not forget to convert 0.25 into 25 percent.",
            "Read whether the problem asks for increase, decrease, or final value.",
        ],
        "gap": "percent base identification",
        "drill": "10 percent increase/decrease items with the original value circled",
        "questions": [
            q("A practice score increases from 24 to 30. What is the percent increase?", ["6%", "20%", "25%", "30%"], 2, "The change is 6, and 6/24 = 25%."),
            q("What decimal equals 12 percent?", ["12.0", "1.2", "0.12", "0.012"], 2, "12 percent means 12/100 = 0.12."),
        ],
    },
    {
        "name": "Ratios and Proportions",
        "skill": "setting up equivalent relationships",
        "purpose": "Ratio problems test whether you can translate wording into matched quantities.",
        "method": [
            "Label the two quantities before writing a proportion.",
            "Keep units aligned across the numerator and denominator.",
            "Cross-multiply only after the setup is correct.",
            "Estimate the answer to catch impossible results.",
        ],
        "example": [
            "If 3 boxes hold 48 connectors, how many connectors are in 5 boxes?",
            "48 divided by 3 equals 16 connectors per box.",
            "5 boxes hold 5 x 16 = 80 connectors.",
            "The answer is 80.",
        ],
        "traps": [
            "Do not swap the order of quantities halfway through.",
            "Do not cross-multiply a setup you have not labeled.",
            "Do not ignore per-unit language.",
            "Check whether the relationship is direct or inverse.",
        ],
        "gap": "proportion setup",
        "drill": "12 direct proportion items with unit labels on every line",
        "questions": [
            q("If 4 identical boxes hold 60 parts, how many parts are in 6 boxes?", ["90", "80", "66", "40"], 0, "60/4 = 15 per box; 6 x 15 = 90."),
            q("In a 3:2 ratio with 30 total bundles, how many are in the second group?", ["10", "12", "15", "18"], 1, "There are 5 total parts; each part is 6; the second group has 2 parts = 12."),
        ],
    },
    {
        "name": "Measurement Conversion",
        "skill": "converting units without losing scale",
        "purpose": "Electrical preparation often uses feet, inches, fractions, and simple unit changes.",
        "method": [
            "Write the starting unit and target unit.",
            "Use a conversion factor that cancels the old unit.",
            "Keep fraction inches exact when possible.",
            "Check whether the answer should be larger or smaller.",
        ],
        "example": [
            "Convert 6 feet to inches.",
            "1 foot equals 12 inches.",
            "6 x 12 = 72 inches.",
            "The answer is 72 inches.",
        ],
        "traps": [
            "Do not multiply when you should divide.",
            "Do not mix feet and inches in the same number without converting.",
            "Do not round too early.",
            "Watch words like radius, diameter, length, and distance.",
        ],
        "gap": "unit conversion direction",
        "drill": "inch-foot-yard conversions, then mixed measurement word problems",
        "questions": [
            q("How many inches are in 5 feet?", ["17", "50", "60", "72"], 2, "5 x 12 = 60 inches."),
            q("Which answer is reasonable for 36 inches converted to feet?", ["1 ft", "2 ft", "3 ft", "12 ft"], 2, "36 / 12 = 3 feet."),
        ],
    },
    {
        "name": "Basic Algebra",
        "skill": "solving one-step and two-step equations",
        "purpose": "Algebra checks whether you can isolate an unknown without changing equality.",
        "method": [
            "Undo addition or subtraction first when isolating the variable.",
            "Then undo multiplication or division.",
            "Do the same operation to both sides.",
            "Substitute the answer back into the original equation.",
        ],
        "example": [
            "Solve 3x + 4 = 22.",
            "Subtract 4 from both sides: 3x = 18.",
            "Divide by 3: x = 6.",
            "Check: 3 x 6 + 4 = 22.",
        ],
        "traps": [
            "Do not move a term without changing its sign.",
            "Do not divide only one side.",
            "Do not forget the final substitution check.",
            "Watch equations with negative numbers.",
        ],
        "gap": "equation isolation",
        "drill": "20 two-step equations with a substitution check",
        "questions": [
            q("Solve 2x + 5 = 17.", ["4", "5", "6", "11"], 2, "Subtract 5 to get 2x = 12, then x = 6."),
            q("What is the best check after solving an equation?", ["Guess again", "Substitute the value back", "Erase the work", "Change the variable"], 1, "Substitution confirms the value satisfies the original equation."),
        ],
    },
    {
        "name": "Formulas and Substitution",
        "skill": "using a formula when values are given",
        "purpose": "Technical exams may give a formula and ask you to substitute correctly.",
        "method": [
            "Identify the formula exactly as written.",
            "Replace each symbol with the matching value.",
            "Use parentheses around substituted values.",
            "Calculate in operation order.",
        ],
        "example": [
            "Use A = L x W with L = 8 and W = 3.",
            "A = 8 x 3.",
            "A = 24.",
            "The area is 24 square units.",
        ],
        "traps": [
            "Do not use a value for the wrong variable.",
            "Do not drop units when the final answer needs them.",
            "Do not change the formula unless solving for another variable is required.",
            "Watch squared units in area problems.",
        ],
        "gap": "formula substitution",
        "drill": "10 formula cards: identify variables, substitute, calculate",
        "questions": [
            q("If P = 2L + 2W, L = 5, and W = 4, what is P?", ["9", "18", "20", "40"], 1, "2 x 5 + 2 x 4 = 10 + 8 = 18."),
            q("Why use parentheses when substituting values?", ["To slow down", "To preserve the intended operation", "To remove units", "To make answers longer"], 1, "Parentheses reduce sign and operation-order mistakes."),
        ],
    },
    {
        "name": "Tables, Graphs, and Slope",
        "skill": "reading change from structured information",
        "purpose": "Some entrance items ask you to infer a rule from a table or simple graph.",
        "method": [
            "Read the labels before the numbers.",
            "Find how one quantity changes when the other changes.",
            "Slope is change in output divided by change in input.",
            "Use the pattern to predict the next value.",
        ],
        "example": [
            "A table shows 1 hour = 12 parts and 2 hours = 24 parts.",
            "The output increases by 12 for each hour.",
            "At 5 hours, 5 x 12 = 60 parts.",
            "The rate is 12 parts per hour.",
        ],
        "traps": [
            "Do not read a graph without checking the scale.",
            "Do not assume every table is linear.",
            "Do not confuse total amount with rate.",
            "Check whether the question asks for input or output.",
        ],
        "gap": "rate from table",
        "drill": "table-to-rule problems with one sentence explaining the pattern",
        "questions": [
            q("A machine makes 15 parts per hour. How many in 4 hours?", ["19", "45", "60", "75"], 2, "15 x 4 = 60."),
            q("On a graph, what must you check before reading a point?", ["The title only", "The axis labels and scale", "The color", "The page number"], 1, "Axis labels and scale tell what the numbers mean."),
        ],
    },
    {
        "name": "Reading for Main Idea",
        "skill": "identifying what a passage is mostly about",
        "purpose": "Reading sections test evidence, not personal opinions about trade work.",
        "method": [
            "Read the question first.",
            "Look for repeated nouns and the final sentence.",
            "Choose the answer that covers the whole passage.",
            "Avoid answers that mention only one detail.",
        ],
        "example": [
            "A passage describes cleaning tools, inspecting them, and reporting damage.",
            "The main idea is safe tool return procedure.",
            "A single detail, such as wiping a handle, is too narrow.",
            "A personal opinion about tools is not supported by the passage.",
        ],
        "traps": [
            "Do not choose an answer just because it contains a familiar word.",
            "Do not add outside knowledge.",
            "Do not choose an answer that is true but too narrow.",
            "Return to the sentence that controls the answer.",
        ],
        "gap": "main idea evidence",
        "drill": "short passages with one main idea sentence and one evidence sentence",
        "questions": [
            q("What makes a strong main idea answer?", ["It covers the whole passage", "It is the longest option", "It uses a technical word", "It feels familiar"], 0, "The main idea must represent the whole passage."),
            q("Why can a true detail still be a wrong main idea answer?", ["It is too broad", "It may be too narrow", "It has no letters", "It is always false"], 1, "A detail can be true but not broad enough."),
        ],
    },
    {
        "name": "Reading for Sequence and Conditions",
        "skill": "tracking before, after, unless, except, and required",
        "purpose": "Small words often decide the correct answer in workplace-style reading.",
        "method": [
            "Circle sequence words such as before and after.",
            "Underline condition words such as unless and if.",
            "Treat except and not as direction-changing words.",
            "Answer from the marked phrase, not from memory.",
        ],
        "example": [
            "Passage: Before a tool is stored, it must be wiped and inspected.",
            "Question: What happens before storage?",
            "The answer must include wiping and inspection.",
            "Returning the tool without inspection violates the sequence.",
        ],
        "traps": [
            "Do not ignore capitalized EXCEPT.",
            "Do not reverse before and after.",
            "Do not treat unless as optional.",
            "Do not answer from what seems practical if the passage says otherwise.",
        ],
        "gap": "condition and sequence words",
        "drill": "20 sentence-level items focused on before, after, unless, except, and not",
        "questions": [
            q("In 'Report damage instead of returning the tool,' which action is replaced?", ["Reporting damage", "Returning the tool", "Cleaning the tool", "Inspecting the tool"], 1, "The phrase after instead of is the action being replaced."),
            q("What should you do first when a question contains EXCEPT?", ["Ignore it", "Circle it and look for the exception", "Pick the first answer", "Skip the passage"], 1, "EXCEPT reverses the usual task."),
        ],
    },
    {
        "name": "Mechanical Reasoning: Levers",
        "skill": "using force, distance, and pivot location",
        "purpose": "Mechanical items test simple physical reasoning, often without advanced formulas.",
        "method": [
            "Find the pivot or fulcrum.",
            "Identify the force and the distance from the pivot.",
            "Longer distance from the pivot usually creates greater turning effect.",
            "Compare both sides before choosing an answer.",
        ],
        "example": [
            "Two equal weights are placed on a lever.",
            "The weight farther from the pivot creates more turning effect.",
            "To balance it, the other side needs more weight or more distance.",
            "Distance matters as much as weight.",
        ],
        "traps": [
            "Do not compare weight alone.",
            "Do not miss the pivot location.",
            "Do not assume the longer side always rises.",
            "Draw an arrow for turning direction.",
        ],
        "gap": "lever moment reasoning",
        "drill": "lever sketches with pivot, force, and distance marked",
        "questions": [
            q("With equal weights on a lever, which side has more turning effect?", ["Closer to the pivot", "Farther from the pivot", "Neither side ever moves", "The lighter color"], 1, "Greater distance from the pivot creates greater turning effect."),
            q("What should you identify first in a lever problem?", ["The pivot", "The font", "The answer letter", "The page number"], 0, "The pivot controls distances and turning direction."),
        ],
    },
    {
        "name": "Mechanical Reasoning: Pulleys",
        "skill": "distinguishing direction change from mechanical advantage",
        "purpose": "Pulley questions check whether you can reason about force and distance tradeoffs.",
        "method": [
            "A fixed pulley mainly changes pull direction.",
            "A movable pulley can reduce required force.",
            "More supporting rope segments usually mean less force per segment.",
            "The tradeoff is pulling more rope distance.",
        ],
        "example": [
            "A single fixed pulley lets a worker pull down to lift a load up.",
            "The direction changes.",
            "The load does not become weightless.",
            "A movable pulley system may reduce effort but requires more rope movement.",
        ],
        "traps": [
            "Do not assume every pulley reduces force.",
            "Do not forget the distance tradeoff.",
            "Do not count the free end as a supporting segment unless appropriate.",
            "Answer whether the question asks force, direction, or distance.",
        ],
        "gap": "pulley force-direction distinction",
        "drill": "fixed vs movable pulley diagrams with support segments counted",
        "questions": [
            q("What is the most typical role of a fixed pulley?", ["Change pull direction", "Make force zero", "Change material weight", "Remove friction completely"], 0, "A fixed pulley mainly changes direction."),
            q("What tradeoff often comes with mechanical advantage in a pulley?", ["More rope distance", "No movement", "Less load height", "No setup needed"], 0, "Less force often requires pulling more rope."),
        ],
    },
    {
        "name": "Mechanical Reasoning: Gears",
        "skill": "tracking rotation direction and speed relationships",
        "purpose": "Gear problems test careful visual tracing from one gear to the next.",
        "method": [
            "Adjacent meshed gears rotate in opposite directions.",
            "Insert an idler gear to flip direction again.",
            "Smaller gears usually rotate more times than larger gears.",
            "Trace one contact point at a time.",
        ],
        "example": [
            "Gear A turns clockwise and touches Gear B.",
            "Gear B turns counterclockwise.",
            "If Gear B touches Gear C, Gear C turns clockwise.",
            "The direction flips at each mesh.",
        ],
        "traps": [
            "Do not skip the middle gear.",
            "Do not assume all gears turn the same way.",
            "Do not confuse belt systems with meshed gears.",
            "Mark each gear with an arrow before answering.",
        ],
        "gap": "gear-chain tracing",
        "drill": "three-gear and four-gear chains with arrows drawn on each gear",
        "questions": [
            q("If two gears mesh and the left gear turns clockwise, the right gear usually turns:", ["Clockwise", "Counterclockwise", "Upward", "Not at all"], 1, "Meshed adjacent gears rotate in opposite directions."),
            q("What happens to direction when a third meshed gear is added?", ["It flips again", "It disappears", "It always stops", "It ignores the first gear"], 0, "Each mesh reverses direction."),
        ],
    },
    {
        "name": "Spatial Reasoning: Rotation",
        "skill": "mentally turning shapes without changing their structure",
        "purpose": "Spatial items measure whether you can recognize the same object in a new orientation.",
        "method": [
            "Pick one anchor feature and track it.",
            "Rotate the entire shape, not one piece at a time.",
            "Check left-right relationships after the turn.",
            "Eliminate mirror images unless the problem allows flipping.",
        ],
        "example": [
            "A shape has a notch on the upper right.",
            "After a 90-degree clockwise turn, that notch moves to the lower right.",
            "The shape is still the same object.",
            "A mirrored notch on the lower left would be wrong.",
        ],
        "traps": [
            "Do not confuse rotation with reflection.",
            "Do not track only the outer outline.",
            "Do not ignore a small notch or mark.",
            "Use the same anchor feature for every option.",
        ],
        "gap": "rotation versus reflection",
        "drill": "shape cards rotated 90, 180, and 270 degrees with one anchor mark",
        "questions": [
            q("What is the key difference between rotation and reflection?", ["Rotation turns; reflection flips", "They are always identical", "Reflection keeps every side unchanged", "Rotation removes details"], 0, "Rotation turns the object; reflection creates a mirror image."),
            q("What should you track first in a rotation item?", ["One anchor feature", "The longest answer", "The page color", "The option letter"], 0, "An anchor feature prevents losing orientation."),
        ],
    },
    {
        "name": "Spatial Reasoning: Folding and Nets",
        "skill": "predicting where faces and marks meet after folding",
        "purpose": "Folding questions test careful adjacency and opposite-side reasoning.",
        "method": [
            "Identify the center face first.",
            "Mark which faces touch the center.",
            "Opposite faces cannot share an edge after folding.",
            "Trace symbols through one fold at a time.",
        ],
        "example": [
            "A cube net has a center square with four neighbors.",
            "Those four neighbors fold up around the center.",
            "A square two steps away may become opposite the center.",
            "Use adjacency, not guesswork.",
        ],
        "traps": [
            "Do not place opposite faces next to each other.",
            "Do not flip a symbol unless the fold causes it.",
            "Do not judge only by color.",
            "Redraw the net if the answer choices are crowded.",
        ],
        "gap": "folding adjacency",
        "drill": "cube nets with center, adjacent, and opposite faces labeled",
        "questions": [
            q("In a cube net, can opposite faces share an edge after folding?", ["Yes, always", "No", "Only if they are colored", "Only on paper"], 1, "Opposite faces do not share an edge on the folded cube."),
            q("What is a useful first step for cube nets?", ["Find the center face", "Guess the prettiest option", "Ignore symbols", "Count answer letters"], 0, "The center face anchors adjacency."),
        ],
    },
    {
        "name": "Word Problems",
        "skill": "translating practical wording into math operations",
        "purpose": "Word problems combine reading accuracy with arithmetic choice.",
        "method": [
            "Underline the requested quantity.",
            "Circle the given numbers and units.",
            "Choose the operation before calculating.",
            "Write a final sentence with the unit.",
        ],
        "example": [
            "A worker needs 3 lengths of conduit, each 8 feet long.",
            "The requested quantity is total length.",
            "3 x 8 = 24.",
            "The worker needs 24 feet.",
        ],
        "traps": [
            "Do not calculate before identifying the question.",
            "Do not mix units.",
            "Do not answer an intermediate value.",
            "Check if the question asks each, total, remaining, or difference.",
        ],
        "gap": "word-problem translation",
        "drill": "10 word problems with requested quantity, operation, and unit written",
        "questions": [
            q("A job uses 4 boxes with 25 parts each. What is the total?", ["29", "75", "100", "125"], 2, "4 x 25 = 100."),
            q("Which phrase usually points to subtraction?", ["In all", "Remaining", "Each", "Per hour"], 1, "Remaining often asks for what is left after subtracting."),
        ],
    },
    {
        "name": "Personal Experience Evidence",
        "skill": "turning experience into clear, verifiable statements",
        "purpose": "Some programs ask about work habits, training, attendance, or related experience.",
        "method": [
            "Use concrete actions, not vague traits.",
            "Name the setting, task, tool, and result when appropriate.",
            "Keep claims honest and verifiable.",
            "Connect the example to reliability, safety, teamwork, or learning speed.",
        ],
        "example": [
            "Weak answer: I am hardworking.",
            "Stronger answer: I completed a six-week evening math course while working part time.",
            "The stronger answer gives evidence, duration, and effort.",
            "Evidence is easier to trust than adjectives.",
        ],
        "traps": [
            "Do not invent experience.",
            "Do not list every job if only one strong example is needed.",
            "Do not use unsafe work as a positive example.",
            "Do not confuse confidence with proof.",
        ],
        "gap": "evidence-based application response",
        "drill": "write three STAR-style examples: situation, task, action, result",
        "questions": [
            q("Which statement is strongest?", ["I am reliable", "I like electricity", "I finished a 10-week evening class with perfect attendance", "I want a job"], 2, "It gives specific, verifiable evidence."),
            q("What should you avoid in an experience response?", ["Concrete examples", "Honest limits", "Invented claims", "Relevant training"], 2, "Invented claims create trust and safety problems."),
        ],
    },
    {
        "name": "Timed Test Strategy",
        "skill": "balancing accuracy, pacing, and review",
        "purpose": "A good plan protects easy points and prevents one hard item from taking the whole section.",
        "method": [
            "Make a first pass through questions you can solve cleanly.",
            "Mark hard items and return after collecting easier points.",
            "Use estimates to catch answer choices that are impossible.",
            "Reserve final minutes for skipped items and answer transfer checks.",
        ],
        "example": [
            "A 30-minute section has 30 questions.",
            "The rough pace is one minute per question.",
            "If a problem takes three minutes with no progress, mark it and move.",
            "Return after the first pass.",
        ],
        "traps": [
            "Do not spend five minutes protecting one point early.",
            "Do not rush so much that you miss simple wording.",
            "Do not leave answer bubbles misaligned.",
            "Do not change answers without a reason from the work.",
        ],
        "gap": "pacing and recovery",
        "drill": "three 10-question timed sets with skipped-item review",
        "questions": [
            q("If one question blocks you early in a timed section, what is usually best?", ["Stay forever", "Mark it and return later", "Erase all work", "Quit the section"], 1, "Protecting the whole section matters more than one early item."),
            q("Why estimate before choosing?", ["To catch impossible answers", "To avoid reading", "To skip units", "To make every answer exact"], 0, "Estimation helps detect scale errors."),
        ],
    },
    {
        "name": "Seven-Day Review Plan",
        "skill": "turning course results into final-week practice",
        "purpose": "The final week should sharpen weak areas while preserving confidence on strengths.",
        "method": [
            "Day 1: diagnostic review and error labels.",
            "Days 2-4: focused drills on the top two weak skills.",
            "Day 5: mixed timed set and explanation review.",
            "Days 6-7: light review, sleep, logistics, and confidence checks.",
        ],
        "example": [
            "If fraction errors and sequence-word errors dominate, split practice blocks.",
            "Do 20 fraction items, then 10 reading condition items.",
            "Review every miss with a one-line cause.",
            "The next day starts with the same two causes.",
        ],
        "traps": [
            "Do not cram every topic equally.",
            "Do not take a full test every day if review quality drops.",
            "Do not ignore sleep and test-day logistics.",
            "Do not measure progress only by time spent.",
        ],
        "gap": "final-week planning",
        "drill": "make a seven-day calendar from the top two error labels",
        "questions": [
            q("What should drive the final-week plan?", ["Random topics", "Top error labels", "Only the easiest items", "A friend's score"], 1, "The plan should respond to diagnosed gaps."),
            q("What is a good final-day priority?", ["All-night cramming", "Light review and logistics", "Learning every topic from zero", "Skipping sleep"], 1, "The final day should protect readiness and reduce avoidable mistakes."),
        ],
    },
]


def lecture(title: str, lines: list[str]) -> dict[str, Any]:
    return {"kind": "lecture", "title": title, "lines": lines}


def quiz(title: str, questions: list[dict[str, Any]]) -> dict[str, Any]:
    return {"kind": "quiz", "title": title, "questions": questions}


def slide_scene(
    course_id: str,
    scene_id: str,
    order: int,
    title: str,
    lines: list[str],
) -> dict[str, Any]:
    return {
        "id": scene_id,
        "stageId": course_id,
        "title": title,
        "order": order,
        "type": "slide",
        "content": {
            "type": "slide",
            "schemaVersion": 1,
            "canvas": {
                "id": f"canvas-{scene_id}",
                "viewportSize": {"width": 1280, "height": 720},
                "viewportRatio": "16:9",
                "theme": {
                    "background": "#F8FAFC",
                    "accent": "#2563EB",
                    "text": "#111827",
                },
                "elements": [
                    text_element(f"{scene_id}-title", title, 72, 68, 1120, 70, 32, True),
                    text_element(
                        f"{scene_id}-body",
                        "\n".join(lines),
                        100,
                        154,
                        1080,
                        455,
                        23,
                        False,
                    ),
                ],
            },
        },
        "createdAt": 0,
        "updatedAt": 0,
        "metadata": {"source": "cognisphereTutor", "demo_role": "entrance_courseware_en"},
    }


def quiz_scene(
    course_id: str,
    scene_id: str,
    order: int,
    title: str,
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    def question_id(question_index: int) -> str:
        return f"{scene_id}::q{question_index + 1}"

    def option_value(question_index: int, choice_index: int) -> str:
        return f"{question_id(question_index)}::{chr(65 + choice_index)}"

    def build_question(question_index: int, question: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": question_id(question_index),
            "type": "single",
            "question": question["question"],
            "options": [
                {"value": option_value(question_index, index), "label": choice}
                for index, choice in enumerate(question["choices"])
            ],
            "answer": [option_value(question_index, int(question["answer"]))],
            "analysis": question["rationale"],
            "points": 1,
        }

    return {
        "id": scene_id,
        "stageId": course_id,
        "title": title,
        "order": order,
        "type": "quiz",
        "content": {
            "type": "quiz",
            "questions": [
                build_question(question_index, question)
                for question_index, question in enumerate(questions)
            ],
        },
        "createdAt": 0,
        "updatedAt": 0,
        "metadata": {"source": "cognisphereTutor", "demo_role": "entrance_assessment_en"},
    }


def text_element(
    element_id: str,
    text: str,
    x: int,
    y: int,
    width: int,
    height: int,
    font_size: int,
    bold: bool,
) -> dict[str, Any]:
    return {
        "id": element_id,
        "type": "text",
        "left": x,
        "top": y,
        "width": width,
        "height": height,
        "rotate": 0,
        "fill": "transparent",
        "opacity": 1,
        "content": text_html(text, font_size, bold),
        "defaultColor": "#111827",
        "defaultFontName": "Arial",
        "lineHeight": 1.5,
        "wordSpace": 0,
        "paragraphSpace": 6,
    }


def text_html(text: str, font_size: int, bold: bool) -> str:
    weight = 700 if bold else 400
    lines = [line for line in text.splitlines() if line.strip()]
    return "".join(
        (
            f'<p style="font-size: {font_size}px; font-weight: {weight}; '
            f'margin: 0 0 8px 0;">{html.escape(line)}</p>'
        )
        for line in lines
    )


if __name__ == "__main__":
    main()
