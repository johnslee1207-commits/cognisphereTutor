"""Add visual prompt metadata for California apprenticeship entrance lessons."""

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
    "cec.entrance_exam_practice_boundary.2026-09-04",
]


def _visual(
    visual_id: str,
    title: str,
    template: str,
    objective_ids: list[str],
    focus: str,
    prompt: str,
    steps: list[str],
) -> dict[str, Any]:
    return {
        "id": visual_id,
        "title": title,
        "summary": "Tutor visual aid metadata for apprenticeship entrance reasoning.",
        "visual_mode": "diagram_storyboard",
        "render_type": "mermaid",
        "visual_template": template,
        "applies_to_objective_ids": objective_ids,
        "diagram_focus": focus,
        "prompt": prompt,
        "animation_steps": steps,
        "source_ref_ids": SOURCE_IDS,
    }


def visual_prompts() -> list[dict[str, Any]]:
    return [
        _visual(
            "cec-visual-entrance-lever-force-arm",
            "Lever force-arm diagram",
            "lever",
            ["cec-apprentice-mechanical"],
            "force, fulcrum, load, and lever-arm length",
            "Show why a longer handle can require less effort force for the same load.",
            [
                "Mark the fulcrum.",
                "Compare effort-arm distance and load-arm distance.",
                "Explain less force over more hand movement.",
            ],
        ),
        _visual(
            "cec-visual-entrance-fixed-pulley-direction",
            "Fixed pulley direction storyboard",
            "fixed_pulley",
            ["cec-apprentice-mechanical"],
            "pull-down direction changes into load-up movement",
            "Show that a fixed pulley mainly changes force direction.",
            [
                "Locate ceiling support.",
                "Trace rope over pulley.",
                "Connect hand pull direction to load motion direction.",
            ],
        ),
        _visual(
            "cec-visual-entrance-movable-pulley-effort",
            "Movable pulley effort storyboard",
            "movable_pulley",
            ["cec-apprentice-mechanical"],
            "force-distance tradeoff",
            "Show why a movable pulley can lower effort force while requiring more rope movement.",
            [
                "Attach pulley to the load.",
                "Trace supporting rope segments.",
                "Explain why the hand pulls more rope distance.",
            ],
        ),
        _visual(
            "cec-visual-entrance-three-gear-direction",
            "Three-gear direction trace",
            "three_gears",
            ["cec-apprentice-mechanical"],
            "direction reversal across each gear contact",
            "Show A clockwise, B counterclockwise, and C clockwise after two reversals.",
            [
                "Set Gear A direction.",
                "Reverse once for Gear B.",
                "Reverse again for Gear C.",
            ],
        ),
        _visual(
            "cec-visual-entrance-open-belt",
            "Open-belt pulley direction",
            "open_belt",
            ["cec-apprentice-mechanical"],
            "same-direction rotation with an uncrossed belt",
            "Show that an open belt usually keeps pulley rotation direction.",
            [
                "Trace belt without crossing.",
                "Copy direction to the second pulley.",
                "Separate direction from speed ratio.",
            ],
        ),
        _visual(
            "cec-visual-entrance-crossed-belt",
            "Crossed-belt pulley direction",
            "crossed_belt",
            ["cec-apprentice-mechanical"],
            "opposite-direction rotation with a crossed belt",
            "Show that crossing the belt reverses pulley rotation direction.",
            [
                "Find where belt paths cross.",
                "Flip the direction at the driven pulley.",
                "Avoid mixing up crossing with pulley size.",
            ],
        ),
        _visual(
            "cec-visual-entrance-one-fold-hole",
            "One-fold hole-punch mirror",
            "paper_one_fold_hole",
            ["cec-apprentice-spatial"],
            "one fold creates one mirrored hole when unfolded",
            "Show folded paper, a hole near the folded edge, then two mirrored holes after unfolding.",
            [
                "Fold left over right.",
                "Punch through the folded layer.",
                "Unfold and mirror the hole across the fold line.",
            ],
        ),
        _visual(
            "cec-visual-entrance-two-fold-unfold",
            "Two-fold unfold storyboard",
            "paper_two_fold_unfold",
            ["cec-apprentice-spatial"],
            "reverse the last fold first",
            "Show why unfolding must happen backward: last fold first, then first fold.",
            [
                "Record fold order.",
                "Undo the last fold first.",
                "Mirror marks once per unfold.",
            ],
        ),
        _visual(
            "cec-visual-entrance-rotation-reflection",
            "Rotation versus reflection diagram",
            "rotation_vs_reflection",
            ["cec-apprentice-spatial"],
            "turning versus flipping",
            "Show how rotation turns a shape while reflection flips it across a line.",
            [
                "Identify the transformation.",
                "Check whether left-right order reversed.",
                "Use the correct transformation before selecting an answer.",
            ],
        ),
        _visual(
            "cec-visual-entrance-mechanical-spatial-remediation",
            "Visual remediation selector",
            "auto",
            ["cec-apprentice-mechanical", "cec-apprentice-spatial"],
            "choose the right visual template from the missed item",
            "Use after a wrong answer to select lever, pulley, gear, belt, fold, or transformation aid.",
            [
                "Classify the visual miss.",
                "Call mastery_visual with the matching template or auto.",
                "Reteach one visual reasoning move before the replacement quick check.",
            ],
        ),
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


def update(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    knowledge = data.setdefault("knowledge", {})
    added = _append_unique(knowledge.setdefault("visual_prompts", []), visual_prompts())
    metadata = knowledge.setdefault("pack_metadata", {})
    metadata["visual_prompt_count"] = len(knowledge.get("visual_prompts") or [])
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def main() -> None:
    result = {"bundle_added": update(BUNDLE_PATH)}
    if IMPORT_CACHE_PATH.exists():
        result["import_cache_added"] = update(IMPORT_CACHE_PATH)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
