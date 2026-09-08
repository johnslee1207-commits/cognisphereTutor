"""Local course artifact exporter for OpenMAIC-style stage documents."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape, unescape
import json
from pathlib import Path
import re
from typing import Any, Mapping
from zipfile import ZIP_DEFLATED, ZipFile

from pptx import Presentation
from pptx.util import Inches


@dataclass(frozen=True)
class ExportedCourseArtifact:
    artifact_id: str
    artifact_type: str
    format: str
    path: Path
    content_type: str
    size_bytes: int


def export_course_artifact(
    *,
    artifact_id: str,
    artifact_type: str,
    format: str,
    course_id: str,
    version: str,
    stage: Mapping[str, Any],
    scenes: list[Mapping[str, Any]],
    output_root: Path | None = None,
) -> ExportedCourseArtifact:
    """Write a real local HTML, PPTX, or MAIC-ZIP artifact."""
    if output_root is None:
        from cognispheretutor.services.path_service import get_path_service

        root = get_path_service().get_public_outputs_root() / "course_exports"
    else:
        root = output_root
    artifact_dir = root / _safe_name(course_id) / _safe_name(version) / artifact_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    if format == "html":
        path = artifact_dir / "course.html"
        path.write_text(_render_html(stage, scenes), encoding="utf-8")
        content_type = "text/html; charset=utf-8"
    elif format == "pptx":
        path = artifact_dir / "course.pptx"
        _write_pptx(path, stage, scenes)
        content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif format == "maic-zip":
        path = artifact_dir / "course.maic.zip"
        _write_maic_zip(path, stage, scenes)
        content_type = "application/zip"
    else:
        raise ValueError(f"unsupported course export format: {format}")

    return ExportedCourseArtifact(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        format=format,
        path=path,
        content_type=content_type,
        size_bytes=path.stat().st_size,
    )


def _render_html(stage: Mapping[str, Any], scenes: list[Mapping[str, Any]]) -> str:
    title = escape(str(stage.get("name") or stage.get("id") or "Course"))
    description = escape(str(stage.get("description") or ""))
    scene_buttons = "\n".join(
        _render_scene_button(scene, index) for index, scene in enumerate(scenes)
    )
    sections = "\n".join(_render_scene_html(scene, index) for index, scene in enumerate(scenes))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --line: #d8dee9;
      --text: #172033;
      --muted: #63708a;
      --brand: #2563eb;
      --brand-soft: #dbeafe;
      --ok: #059669;
      --bad: #dc2626;
      --warn: #b45309;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.5;
    }}
    .shell {{
      min-height: 100vh;
      display: grid;
      grid-template-columns: minmax(230px, 300px) minmax(0, 1fr);
    }}
    aside {{
      position: sticky;
      top: 0;
      height: 100vh;
      overflow: auto;
      padding: 20px 16px;
      border-right: 1px solid var(--line);
      background: #fbfcff;
    }}
    main {{ min-width: 0; padding: 28px clamp(18px, 4vw, 48px); }}
    h1, h2, h3 {{ color: #0f172a; line-height: 1.18; }}
    h1 {{ margin: 0 0 10px; font-size: clamp(26px, 4vw, 44px); }}
    h2 {{ margin: 0 0 14px; font-size: 28px; }}
    h3 {{ margin: 18px 0 8px; font-size: 18px; }}
    p {{ margin: 0 0 12px; }}
    .brand {{ font-weight: 700; color: var(--brand); margin-bottom: 16px; }}
    .course-desc {{ max-width: 820px; color: var(--muted); font-size: 17px; }}
    .progress-wrap {{
      height: 8px;
      margin: 18px 0 20px;
      overflow: hidden;
      border-radius: 999px;
      background: #e5e7eb;
    }}
    .progress-bar {{
      width: 0%;
      height: 100%;
      background: linear-gradient(90deg, #2563eb, #14b8a6);
      transition: width 160ms ease;
    }}
    .scene-nav {{
      display: grid;
      gap: 8px;
    }}
    .scene-tab {{
      width: 100%;
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--text);
      cursor: pointer;
      display: grid;
      grid-template-columns: 28px 1fr;
      gap: 8px;
      align-items: center;
      padding: 8px;
      text-align: left;
    }}
    .scene-tab:hover, .scene-tab.active {{
      border-color: var(--brand);
      background: var(--brand-soft);
    }}
    .scene-index {{
      width: 26px;
      height: 26px;
      border-radius: 50%;
      display: inline-grid;
      place-items: center;
      background: #e2e8f0;
      color: #334155;
      font-size: 12px;
      font-weight: 700;
    }}
    .scene-title {{ font-size: 13px; overflow-wrap: anywhere; }}
    .scene {{
      display: none;
      max-width: 980px;
      min-height: 62vh;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: clamp(18px, 3vw, 34px);
      box-shadow: 0 14px 40px rgba(15, 23, 42, 0.08);
    }}
    .scene.active {{ display: block; }}
    .kind {{
      display: inline-block;
      margin-bottom: 12px;
      color: var(--brand);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    .bullet-list {{ padding-left: 22px; }}
    .bullet-list li {{ margin: 10px 0; }}
    .quiz-card {{
      margin: 16px 0;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f8fafc;
    }}
    .question-text {{
      font-weight: 700;
      margin-bottom: 12px;
      overflow-wrap: anywhere;
    }}
    .option {{
      width: 100%;
      min-height: 44px;
      margin: 8px 0;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--text);
      cursor: pointer;
      display: grid;
      grid-template-columns: 30px 1fr;
      gap: 10px;
      align-items: start;
      text-align: left;
    }}
    .option:hover {{ border-color: var(--brand); }}
    .option.selected {{ border-color: var(--brand); background: var(--brand-soft); }}
    .option.correct {{ border-color: var(--ok); background: #dcfce7; }}
    .option.incorrect {{ border-color: var(--bad); background: #fee2e2; }}
    .option-label {{
      width: 26px;
      height: 26px;
      border-radius: 50%;
      display: inline-grid;
      place-items: center;
      background: #e2e8f0;
      font-size: 12px;
      font-weight: 700;
    }}
    .feedback {{
      display: none;
      margin-top: 12px;
      padding: 12px;
      border-left: 4px solid var(--brand);
      background: #eff6ff;
      color: #1e3a8a;
    }}
    .feedback.visible {{ display: block; }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 20px;
    }}
    .nav-button {{
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--text);
      cursor: pointer;
      padding: 9px 14px;
      font-weight: 700;
    }}
    .nav-button.primary {{
      border-color: var(--brand);
      background: var(--brand);
      color: #fff;
    }}
    .empty {{ color: var(--muted); }}
    @media (max-width: 780px) {{
      .shell {{ display: block; }}
      aside {{ position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--line); }}
      main {{ padding: 18px; }}
      .scene {{ min-height: auto; }}
    }}
  </style>
</head>
<body>
<div class="shell">
  <aside>
    <div class="brand">OpenMAIC Classroom</div>
    <div class="scene-nav" id="sceneNav">{scene_buttons}</div>
  </aside>
  <main>
    <h1>{title}</h1>
    <p class="course-desc">{description}</p>
    <div class="progress-wrap" aria-label="Course progress">
      <div class="progress-bar" id="progressBar"></div>
    </div>
    {sections}
  </main>
</div>
<script>
(() => {{
  const scenes = Array.from(document.querySelectorAll("[data-scene-index]"));
  const tabs = Array.from(document.querySelectorAll("[data-scene-tab]"));
  const progress = document.getElementById("progressBar");
  let active = 0;

  function showScene(index) {{
    active = Math.max(0, Math.min(index, scenes.length - 1));
    scenes.forEach((scene, i) => scene.classList.toggle("active", i === active));
    tabs.forEach((tab, i) => tab.classList.toggle("active", i === active));
    if (progress && scenes.length) {{
      progress.style.width = `${{((active + 1) / scenes.length) * 100}}%`;
    }}
  }}

  tabs.forEach((tab, index) => tab.addEventListener("click", () => showScene(index)));
  document.querySelectorAll("[data-next]").forEach((button) => {{
    button.addEventListener("click", () => showScene(active + 1));
  }});
  document.querySelectorAll("[data-prev]").forEach((button) => {{
    button.addEventListener("click", () => showScene(active - 1));
  }});
  document.querySelectorAll("[data-option]").forEach((button) => {{
    button.addEventListener("click", () => {{
      const card = button.closest("[data-question]");
      if (!card) return;
      card.querySelectorAll("[data-option]").forEach((option) => {{
        option.classList.remove("selected", "correct", "incorrect");
      }});
      button.classList.add("selected");
      const selected = button.getAttribute("data-value");
      const answers = (card.getAttribute("data-answer") || "").split("||").filter(Boolean);
      const isCorrect = answers.includes(selected);
      button.classList.add(isCorrect ? "correct" : "incorrect");
      if (!isCorrect) {{
        card.querySelectorAll("[data-option]").forEach((option) => {{
          if (answers.includes(option.getAttribute("data-value") || "")) {{
            option.classList.add("correct");
          }}
        }});
      }}
      const feedback = card.querySelector(".feedback");
      if (feedback) {{
        feedback.classList.add("visible");
        feedback.querySelector("[data-result]").textContent = isCorrect ? "Correct" : "Review";
      }}
    }});
  }});
  showScene(0);
}})();
</script>
</body>
</html>
"""


def _render_scene_button(scene: Mapping[str, Any], index: int) -> str:
    title = escape(str(scene.get("title") or scene.get("id") or "Scene"))
    return f"""<button class="scene-tab" type="button" data-scene-tab="{index}">
  <span class="scene-index">{index + 1}</span>
  <span class="scene-title">{title}</span>
</button>"""


def _render_scene_html(scene: Mapping[str, Any], index: int) -> str:
    title = escape(str(scene.get("title") or scene.get("id") or "Scene"))
    scene_type = escape(str(scene.get("type") or "scene"))
    content = scene.get("content") if isinstance(scene.get("content"), Mapping) else {}
    body = (
        _render_quiz_content(content)
        if content.get("type") == "quiz"
        else _render_bullet_content(content)
    )
    active = " active" if index == 0 else ""
    return f"""<section class="scene{active}" data-scene-index="{index}">
  <div class="kind">{scene_type}</div>
  <h2>{title}</h2>
  {body}
  <div class="toolbar">
    <button class="nav-button" type="button" data-prev>Previous</button>
    <button class="nav-button primary" type="button" data-next>Next</button>
  </div>
</section>"""


def _render_bullet_content(content: Mapping[str, Any]) -> str:
    bullets = _content_bullets(content)
    items = "\n".join(f"<li>{escape(item)}</li>" for item in bullets)
    return f'<ul class="bullet-list">{items}</ul>' if items else '<p class="empty">No content.</p>'


def _render_quiz_content(content: Mapping[str, Any]) -> str:
    questions = content.get("questions") if isinstance(content.get("questions"), list) else []
    cards = [
        _render_quiz_question(question, index)
        for index, question in enumerate(questions)
        if isinstance(question, Mapping)
    ]
    if not cards:
        return '<p class="empty">Answer the checkpoint question and review evidence.</p>'
    return "\n".join(cards)


def _render_quiz_question(question: Mapping[str, Any], index: int) -> str:
    prompt = escape(_question_text(question) or f"Question {index + 1}")
    options = _question_options(question)
    answers = _question_answers(question)
    answer_attr = escape("||".join(answers), quote=True)
    rendered_options = "\n".join(
        _render_quiz_option(option, option_index)
        for option_index, option in enumerate(options)
    )
    analysis = escape(str(question.get("analysis") or question.get("rationale") or ""))
    if not rendered_options:
        rendered_options = '<p class="empty">No options provided.</p>'
    return f"""<article class="quiz-card" data-question="{index}" data-answer="{answer_attr}">
  <div class="question-text">{index + 1}. {prompt}</div>
  <div>{rendered_options}</div>
  <div class="feedback"><strong data-result>Review</strong><p>{analysis}</p></div>
</article>"""


def _render_quiz_option(option: Mapping[str, str], index: int) -> str:
    label = escape(option.get("label") or chr(65 + index))
    value = escape(option.get("value") or label, quote=True)
    text = escape(option.get("text") or option.get("label") or value)
    return f"""<button class="option" type="button" data-option data-value="{value}">
  <span class="option-label">{chr(65 + index)}</span>
  <span>{text}</span>
</button>"""


def _write_pptx(path: Path, stage: Mapping[str, Any], scenes: list[Mapping[str, Any]]) -> None:
    prs = Presentation()
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = str(stage.get("name") or stage.get("id") or "Course")
    title_slide.placeholders[1].text = str(stage.get("description") or "")

    for scene in scenes:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = str(scene.get("title") or scene.get("id") or "Scene")
        body = slide.placeholders[1].text_frame
        body.clear()
        content = scene.get("content") if isinstance(scene.get("content"), Mapping) else {}
        for index, item in enumerate(_content_bullets(content)):
            paragraph = body.paragraphs[0] if index == 0 else body.add_paragraph()
            paragraph.text = item
            paragraph.level = 0

    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    prs.save(path)


def _write_maic_zip(path: Path, stage: Mapping[str, Any], scenes: list[Mapping[str, Any]]) -> None:
    manifest = {
        "formatVersion": 1,
        "stage": dict(stage),
        "scenes": [dict(scene) for scene in scenes],
        "mediaIndex": {},
    }
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("course.html", _render_html(stage, scenes))


def _content_bullets(content: Mapping[str, Any]) -> list[str]:
    if content.get("type") == "quiz":
        questions = content.get("questions") if isinstance(content.get("questions"), list) else []
        return [_question_text(q) for q in questions if isinstance(q, Mapping)] or [
            "Answer the checkpoint question and review evidence."
        ]
    if content.get("type") == "pbl":
        project = content.get("project") if isinstance(content.get("project"), Mapping) else {}
        tasks = project.get("tasks") if isinstance(project.get("tasks"), list) else []
        return [str(task) for task in tasks] or ["Complete the project task and submit evidence."]
    if content.get("type") == "interactive":
        return ["Explore the embedded interactive activity.", "Record observations as evidence."]
    canvas = content.get("canvas") if isinstance(content.get("canvas"), Mapping) else {}
    elements = canvas.get("elements") if isinstance(canvas.get("elements"), list) else []
    texts = [
        _strip_html(str(item.get("text") or item.get("content")))
        for item in elements
        if isinstance(item, Mapping) and (item.get("text") or item.get("content"))
    ]
    return texts or ["Review the concept and connect it to the learning objective."]


def _question_text(question: Mapping[str, Any]) -> str:
    return str(question.get("question") or question.get("prompt") or question.get("text") or "")


def _question_options(question: Mapping[str, Any]) -> list[dict[str, str]]:
    raw_options = question.get("options") if isinstance(question.get("options"), list) else []
    options: list[dict[str, str]] = []
    for index, raw in enumerate(raw_options):
        fallback_label = chr(65 + index)
        if isinstance(raw, Mapping):
            label = str(raw.get("label") or raw.get("text") or raw.get("title") or fallback_label)
            value = str(raw.get("value") or raw.get("id") or label)
            text = _strip_html(str(raw.get("text") or raw.get("label") or label))
        else:
            label = str(raw)
            value = label
            text = label
        options.append({"label": label, "value": value, "text": text})
    return options


def _question_answers(question: Mapping[str, Any]) -> list[str]:
    raw_answer = question.get("answer")
    if isinstance(raw_answer, list):
        answers = [str(item) for item in raw_answer if str(item).strip()]
    elif raw_answer is None:
        answers = []
    else:
        answers = [str(raw_answer)]
    options = _question_options(question)
    option_values = {option["value"] for option in options}
    normalized: list[str] = []
    for answer in answers:
        if answer in option_values:
            normalized.append(answer)
            continue
        if len(answer) == 1 and answer.upper().isalpha():
            idx = ord(answer.upper()) - 65
            if 0 <= idx < len(options):
                normalized.append(options[idx]["value"])
                continue
        normalized.append(answer)
    return list(dict.fromkeys(normalized))


def _strip_html(value: str) -> str:
    stripped = re.sub(r"<[^>]+>", " ", value)
    return " ".join(unescape(stripped).split())


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)
    return cleaned.strip("._") or "course"
