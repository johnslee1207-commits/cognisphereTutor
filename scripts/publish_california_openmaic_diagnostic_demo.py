"""Publish the California electrical career diagnostic demo to OpenMAIC.

This script uses the existing Cognisphere California electrical career bundle
as source material, then publishes an OpenMAIC-native classroom that makes the
Tutor diagnostic and planning loop visible instead of showing only module
overview slides.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import time
from typing import Any

import httpx

COURSE_ID = "csphere-california-electrical-career-diagnostic-planner-v5"
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default=DEFAULT_OPENMAIC_ORIGIN)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--course-id", default=COURSE_ID)
    args = parser.parse_args()

    origin = args.origin.rstrip("/")
    document = build_document(args.course_id)
    headers = {"authorization": f"Bearer {args.token}"}

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
            json={
                "stage": document["stage"],
                "scenes": document["scenes"],
            },
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
    knowledge = bundle["knowledge"]
    now = int(time.time() * 1000)
    stage = {
        "id": course_id,
        "name": "加州电工学习诊断与路径规划",
        "description": "CognisphereTutor diagnostic and planning demo rendered in OpenMAIC.",
        "createdAt": now,
        "updatedAt": now,
        "languageDirective": "zh-CN",
        "style": "deeptutor-diagnostic-planner",
    }
    scenes = [
        slide_scene(
            course_id,
            "scene-01-diagnostic-cockpit",
            1,
            "先诊断，不先讲课",
            [
                "学习者进入后先回答四类问题：目标、基础、资格、时间线",
                "目标：学徒入门 / General Electrician / C-10 / Law & Business",
                "基础：数学、欧姆定律、电路识图、安全词汇、查表习惯",
                "证据：工作小时、证书、个人经历、错题记录、可练习时间",
                "输出不是一张 PPT，而是一条可执行学习路线",
            ],
        ),
        quiz_scene(
            course_id,
            "scene-02-route-diagnostic",
            2,
            "路径诊断：你现在最该走哪条线？",
            [
                {
                    "id": "q-goal",
                    "question": "你的最近目标是什么？",
                    "choices": [
                        "进入 ETI / IBEW 学徒选拔",
                        "准备 California General Electrician",
                        "准备 C-10 Electrical Trade",
                        "先确认自己适不适合电工路径",
                    ],
                    "answer": 3,
                    "rationale": "不确定目标时先进入 shared foundations 与职业路径诊断，避免直接刷错题。",
                },
                {
                    "id": "q-eligibility",
                    "question": "如果学习者还没有工作小时证明和雇主记录，Tutor 应如何处理 GE/C-10 目标？",
                    "choices": [
                        "忽略资格，直接承诺能考试",
                        "把资格证据列成待办，同时先学共同基础",
                        "只讲电工职业故事",
                        "删除 GE/C-10 路线",
                    ],
                    "answer": 1,
                    "rationale": "资格证据和学习准备要分开：Tutor 可以推进学习，但必须把正式资格作为独立证据缺口。",
                },
                {
                    "id": "q-foundation",
                    "question": "如果比例、百分比、单位换算经常错，Tutor 应先安排什么？",
                    "choices": [
                        "直接做 GE 全真模拟",
                        "先做 shared electrical foundations",
                        "只看职业介绍",
                        "直接申请 C-10",
                    ],
                    "answer": 1,
                    "rationale": "基础计算不稳时，后续负载、导线、估算和查表都会被放大拖累。",
                },
                {
                    "id": "q-safety",
                    "question": "做基础排障训练时，哪一项必须先于测量和判断原因？",
                    "choices": [
                        "安全边界和停电/验证假设",
                        "背下所有 NEC 条文",
                        "先猜最可能故障",
                        "先做计时模拟",
                    ],
                    "answer": 0,
                    "rationale": "电工学习中的排障必须先建立安全边界；诊断不是鼓励未经授权的实操。",
                },
            ],
        ),
        slide_scene(
            course_id,
            "scene-03-diagnostic-scoring",
            3,
            "评测结果如何变成规划",
            [
                "路径题：决定主路线，不确定则进入 newcomer foundation",
                "资格题：生成证据待办，不把学习准备误说成考试资格",
                "基础题：决定是否允许进入 GE/C-10 高权重题型",
                "安全题：决定是否开放排障/实验类任务",
                "结果写入 learner model：route / gaps / evidence / next checkpoint",
            ],
        ),
        slide_scene(
            course_id,
            "scene-04-gap-matrix",
            4,
            "诊断结果会落成差距矩阵",
            [
                "示例 learner profile：目标未定，数学中等，电工概念薄弱，没有 NEC 查表经验",
                "已掌握：基础阅读、学习时间可持续、能做简单比例题",
                "高优先缺口：单位换算、欧姆定律、串并联概念、安全边界",
                "暂不推进：C-10 估算、GE 蓝图加权模拟、Law & Business",
                "下一步：生成 7 天 newcomer route，而不是浏览所有模块",
            ],
        ),
        slide_scene(
            course_id,
            "scene-05-personal-plan",
            5,
            "个性化 7 天计划示例",
            [
                "Day 1：路线确认 + 数学/概念 baseline diagnostic",
                "Day 2：比例、百分比、单位换算 worked examples",
                "Day 3：电压、电流、电阻、功率，用一个现场场景解释",
                "Day 4：串联/并联 + 测量和安全验证",
                "Day 5：图纸、工具、材料、安全词汇",
                "Day 6：基础排障：症状 -> 测量 -> 可能原因 -> 安全验证",
                "Day 7：readiness checkpoint，决定进入学徒冲刺或继续 foundations",
            ],
        ),
        slide_scene(
            course_id,
            "scene-06-ohms-law-lesson",
            6,
            "真正课程单元：欧姆定律不是只背公式",
            [
                "场景：一个负载标称 120V，测得电流 2A",
                "已知量：V = 120V，I = 2A",
                "要求量：R，所以 R = V / I = 60 ohms",
                "Tutor 追问：单位是否合理？如果电流变大，等效电阻如何变化？",
                "学习证据：能解释关系、能列式、能检查单位",
            ],
        ),
        quiz_scene(
            course_id,
            "scene-07-error-diagnosis",
            7,
            "错因诊断：错了以后不是只给答案",
            [
                {
                    "id": "q-ohm-error",
                    "question": "学习者把 120V 和 2A 相乘得到 240 ohms，这是什么错因？",
                    "choices": [
                        "单位/公式选择错误",
                        "阅读理解错误",
                        "时间管理错误",
                        "职业路径选择错误",
                    ],
                    "answer": 0,
                    "rationale": "电阻应使用 R = V / I；乘法得到的是功率关系中的 P = V * I。",
                },
                {
                    "id": "q-remediate",
                    "question": "如果错因是单位/公式选择错误，下一步最合理的补救是什么？",
                    "choices": [
                        "直接进入 C-10 估算",
                        "回到 known/unknown/unit，再做一步预测题",
                        "跳过该知识点",
                        "只给最终答案",
                    ],
                    "answer": 1,
                    "rationale": "补救要针对错因：先修复表示和公式选择，再让学习者完成最小下一步。",
                },
            ],
        ),
        slide_scene(
            course_id,
            "scene-08-remediation",
            8,
            "根据错因自动补救",
            [
                "如果是公式错：回到概念关系图，再做一步预测题",
                "如果是单位错：强制写 known / unknown / unit",
                "如果是题意错：先划出要求量，再选择公式",
                "如果是速度错：降低题量，保持正确率后再计时",
                "补救完成后才进入下一个目标",
            ],
        ),
        pbl_scene(
            course_id,
            "scene-09-planning-lab",
            9,
            "规划实验：把诊断结果变成下一节课",
            "你是 Tutor。一个零基础学习者想成为加州电工，但不知道先准备学徒、GE 还是 C-10。请根据诊断输出一周计划。",
            [
                "选择当前主路径",
                "列出前三个知识缺口",
                "安排 7 天学习顺序",
                "定义 readiness checkpoint",
            ],
        ),
        quiz_scene(
            course_id,
            "scene-10-readiness-quiz",
            10,
            "Readiness gate：是否可以进入下一阶段？",
            [
                {
                    "id": "q-readiness",
                    "question": "以下哪组证据最适合解锁“GE 蓝图加权练习”？",
                    "choices": [
                        "只看过职业介绍",
                        "基础数学、欧姆定律、串并联、安全边界都通过 checkpoint",
                        "还不知道目标，但想直接刷模拟题",
                        "没有错题记录",
                    ],
                    "answer": 1,
                    "rationale": "GE 蓝图练习应在 shared foundations 达标后解锁，否则评测会变成随机挫败。",
                }
            ],
        ),
        slide_scene(
            course_id,
            "scene-11-readiness-gate",
            11,
            "进入下一阶段前必须过 readiness gate",
            checkpoint_lines(knowledge),
        ),
        slide_scene(
            course_id,
            "scene-12-why-openmaic",
            12,
            "OpenMAIC 展示，Tutor 决策",
            [
                "OpenMAIC：承载课堂场景、播放、交互、导出",
                "cognisphereTutor：诊断、知识图谱、错因记忆、路径规划、mastery gate",
                "这次演示的重点：OpenMAIC 不只是 PPT 容器，而是 Tutor 学习路线的可视化前端",
                "下一步产品态：每个 checkpoint 都回写学习事件，Tutor 更新 learner model",
            ],
        ),
    ]
    return {
        "stage": stage,
        "scenes": scenes,
        "outline": {
            "source": "cognisphereTutor",
            "bundle_id": bundle["bundle_id"],
            "mode": "diagnostic_planner_demo",
            "readiness_checkpoints": [
                checkpoint["id"] for checkpoint in knowledge["readiness_checkpoints"][:3]
            ],
        },
    }


def checkpoint_lines(knowledge: dict[str, Any]) -> list[str]:
    checkpoint = knowledge["readiness_checkpoints"][1]
    lines = [checkpoint["title"], checkpoint["summary"]]
    lines.extend(checkpoint["mastery_evidence"][:5])
    return lines


def slide_scene(
    course_id: str,
    scene_id: str,
    order: int,
    title: str,
    lines: list[str],
) -> dict[str, Any]:
    content = {
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
                text_element(f"{scene_id}-title", title, 90, 86, 920, 48, 34, True),
                text_element(
                    f"{scene_id}-body",
                    "\n".join(lines),
                    120,
                    180,
                    1000,
                    360,
                    24,
                    False,
                ),
            ],
        },
    }
    return {
        "id": scene_id,
        "stageId": course_id,
        "title": title,
        "order": order,
        "type": "slide",
        "content": content,
        "createdAt": 0,
        "updatedAt": 0,
        "metadata": {"source": "cognisphereTutor", "demo_role": "diagnostic_planner"},
    }


def quiz_scene(
    course_id: str,
    scene_id: str,
    order: int,
    title: str,
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": scene_id,
        "stageId": course_id,
        "title": title,
        "order": order,
        "type": "quiz",
        "content": {
            "type": "quiz",
            "questions": [
                {
                    "id": question["id"],
                    "type": "single",
                    "question": question["question"],
                    "options": [
                        {"value": chr(65 + index), "label": choice}
                        for index, choice in enumerate(question["choices"])
                    ],
                    "answer": [chr(65 + int(question["answer"]))],
                    "analysis": question["rationale"],
                    "points": 1,
                }
                for question in questions
            ],
        },
        "createdAt": 0,
        "updatedAt": 0,
        "metadata": {"source": "cognisphereTutor", "demo_role": "diagnostic"},
    }


def pbl_scene(
    course_id: str,
    scene_id: str,
    order: int,
    title: str,
    scenario: str,
    deliverables: list[str],
) -> dict[str, Any]:
    return {
        "id": scene_id,
        "stageId": course_id,
        "title": title,
        "order": order,
        "type": "pbl",
        "content": {
            "type": "pbl",
            "projectConfig": legacy_pbl_project_config(title, scenario, deliverables),
        },
        "createdAt": 0,
        "updatedAt": 0,
        "metadata": {"source": "cognisphereTutor", "demo_role": "planning_lab"},
    }


def legacy_pbl_project_config(
    title: str,
    scenario: str,
    deliverables: list[str],
) -> dict[str, Any]:
    return {
        "projectInfo": {
            "title": title,
            "description": scenario,
        },
        "agents": [
            {
                "name": "CognisphereTutor",
                "actor_role": "instructor",
                "role_division": "management",
                "system_prompt": "Guide the learner to convert diagnostics into a study plan.",
                "default_mode": "coach",
                "delay_time": 0,
                "env": {},
                "is_user_role": False,
                "is_active": True,
                "is_system_agent": True,
            }
        ],
        "issueboard": {
            "agent_ids": ["CognisphereTutor"],
            "current_issue_id": "plan-route",
            "issues": [
                legacy_pbl_issue(
                    "plan-route",
                    0,
                    "选择当前主路径",
                    "根据目标、资格证据和基础测验结果，选择 newcomer foundation、apprenticeship、GE、C-10 或 Law & Business。",
                    "先写出为什么不直接刷题，再给出当前主路径。",
                ),
                *[
                    legacy_pbl_issue(
                        f"deliverable-{index}",
                        index,
                        item,
                        f"完成交付物：{item}",
                        "用诊断证据支撑，不要只列课程标题。",
                    )
                    for index, item in enumerate(deliverables, start=1)
                ],
            ],
        },
        "chat": {
            "messages": [
                {
                    "id": "msg-planning-brief",
                    "agent_name": "CognisphereTutor",
                    "message": scenario,
                    "timestamp": 0,
                    "read_by": [],
                }
            ]
        },
        "selectedRole": None,
    }


def legacy_pbl_issue(
    issue_id: str,
    index: int,
    title: str,
    description: str,
    generated_questions: str,
) -> dict[str, Any]:
    return {
        "id": issue_id,
        "title": title,
        "description": description,
        "person_in_charge": "learner",
        "participants": ["CognisphereTutor"],
        "notes": "",
        "parent_issue": None,
        "index": index,
        "is_done": False,
        "is_active": index == 0,
        "generated_questions": generated_questions,
        "question_agent_name": "CognisphereTutor",
        "judge_agent_name": "CognisphereTutor",
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
        "content": _text_html(text, font_size, bold),
        "defaultColor": "#111827",
        "defaultFontName": "Arial",
        "lineHeight": 1.55,
        "wordSpace": 0,
        "paragraphSpace": 6,
    }


def _text_html(text: str, font_size: int, bold: bool) -> str:
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
