"""Publish detailed OpenMAIC courseware for electrician entrance exam prep."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import time
from typing import Any

import httpx

COURSE_ID = "california-electrical-entrance-courseware-v5"
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
    parser.add_argument(
        "--owner-cookie",
        help="OpenMAIC anonymous_id cookie for overwriting an existing owned document.",
    )
    args = parser.parse_args()

    origin = args.origin.rstrip("/")
    document = build_document(args.course_id)
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
    stage = {
        "id": course_id,
        "name": "电工入门考试详细讲课课件",
        "description": "Detailed OpenMAIC courseware for electrician apprenticeship entrance preparation.",
        "createdAt": now,
        "updatedAt": now,
        "languageDirective": "zh-CN",
        "style": "deeptutor-entrance-courseware",
    }
    scenes = courseware_scenes(course_id)
    return {
        "stage": stage,
        "scenes": scenes,
        "outline": {
            "source": "cognisphereTutor",
            "bundle_id": bundle["bundle_id"],
            "mode": "electrical_entrance_courseware",
            "source_policy": bundle["safety"]["source_of_truth"],
        },
    }


def courseware_scenes(course_id: str) -> list[dict[str, Any]]:
    scene_specs: list[dict[str, Any]] = [
        lecture(
            "课程目标：入门考试不是电工实操考试",
            [
                "本课面向电工学徒/入门选拔常见能力：数学、阅读、机械、空间、证据表达",
                "核心原则：练能力，不背泄露真题；用原创题和可解释步骤训练",
                "不同地区考试结构会不同：有的偏 Algebra + Reading，有的包含机械和纸折叠",
                "学习路线：诊断 -> 分项讲解 -> 随堂测 -> 错因标签 -> 7 天复习计划",
            ],
        ),
        lecture(
            "考试能力地图",
            [
                "数学计算：整数、小数、分数、百分比、比例、单位换算",
                "代数函数：解方程、代入、斜率、表格关系、函数变化",
                "阅读理解：抓主旨、定位证据、分辨题干和原文",
                "机械理解：杠杆、滑轮、齿轮、力的方向、平衡",
                "空间推理：旋转、展开图、纸折叠、镜像陷阱",
                "个人经历表：把真实经历写成可验证证据",
            ],
        ),
        lecture(
            "诊断先行：5 个维度决定学习计划",
            [
                "目标：你申请的是哪类 apprenticeship 或入门项目？",
                "时间：考试前还有几周？每天可练多久？",
                "基础：数学和阅读是否需要从零补？",
                "速度：正确率稳定后才加计时压力",
                "证据：个人经历、课程、证书、推荐信是否已经整理",
            ],
        ),
        quiz(
            "课前诊断测验",
            [
                q(
                    "如果你不知道考试具体版本，最稳妥的备考策略是什么？",
                    [
                        "只刷网上所谓真题",
                        "先练通用能力，再按本地官方通知调整",
                        "跳过阅读理解",
                        "只背电工工具名称",
                    ],
                    1,
                    "不同项目测试结构不同；通用能力训练加官方确认最稳。",
                ),
                q(
                    "如果基础计算经常错，第一周最应强化什么？",
                    ["复杂 NEC 查表", "分数、比例、百分比、单位换算", "C-10 合同法", "企业税务"],
                    1,
                    "入门考试和后续电工计算都会放大基础计算缺口。",
                ),
            ],
        ),
        lecture(
            "数学一：分数、小数、百分比",
            [
                "分数转小数：1/4 = 0.25，3/8 = 0.375",
                "百分比本质：百分之几 = 除以 100",
                "增长率公式：(新值 - 旧值) / 旧值",
                "常见错因：把增加量当百分比、用新值当分母、忘记单位",
            ],
        ),
        lecture(
            "例题：百分比增长",
            [
                "题目：练习正确数从 40 题提高到 50 题，增长百分比是多少？",
                "Step 1：增加量 = 50 - 40 = 10",
                "Step 2：用旧值作分母，10 / 40 = 0.25",
                "Step 3：转成百分比 = 25%",
                "检查：不是 10%，因为 10 是增加的题数，不是百分比",
            ],
        ),
        quiz(
            "随堂测：百分比和比例",
            [
                q(
                    "某练习从 24 题正确增加到 30 题，增长率是多少？",
                    ["6%", "20%", "25%", "30%"],
                    2,
                    "增加 6，旧值 24，6/24 = 25%。",
                ),
                q(
                    "小捆和大捆比例为 3:2，总共 30 捆，大捆有多少？",
                    ["10", "12", "15", "18"],
                    1,
                    "总份数 5，每份 6，大捆 2 份，所以 12。",
                ),
            ],
        ),
        lecture(
            "数学二：代数方程",
            [
                "目标：把文字题翻译成等式",
                "解一元方程：两边做同样操作",
                "常见形式：2x + 5 = 17，x/3 = 8，4(x - 2) = 20",
                "电工相关迁移：未知量、单位、公式选择，比死背更重要",
            ],
        ),
        lecture(
            "例题：线性方程",
            [
                "题目：2x + 5 = 17，求 x",
                "Step 1：两边减 5，2x = 12",
                "Step 2：两边除以 2，x = 6",
                "检查：2*6+5 = 17",
                "错因标签：漏减常数、除法对象错、没有回代检查",
            ],
        ),
        quiz(
            "随堂测：代数",
            [
                q("3x - 4 = 20，x 等于多少？", ["6", "8", "12", "16"], 1, "两边加 4 得 3x=24，所以 x=8。"),
                q("如果 y = 2x + 1，当 x = 5 时 y 等于多少？", ["10", "11", "12", "15"], 1, "代入 x=5，y=10+1=11。"),
            ],
        ),
        lecture(
            "数学四：文字题建模",
            [
                "文字题不要先算，先写变量",
                "关键词：total 表示总和，twice 表示 2 倍，more than 表示加法",
                "建模四步：设未知数 -> 写另一部分 -> 列总量方程 -> 回代检查",
                "考试陷阱：选项里常放“较长那段”或“漏掉额外量”的结果",
            ],
        ),
        lecture(
            "例题：电缆长度文字题",
            [
                "题目：一根电缆分成两段，长段比短段的 2 倍多 3 ft，总长 24 ft，短段多长？",
                "设短段 = x",
                "长段 = 2x + 3",
                "方程：x + 2x + 3 = 24，所以 3x = 21，x = 7",
                "检查：短段 7，长段 17，总长 24",
            ],
        ),
        quiz(
            "随堂测：文字题建模",
            [
                q(
                    "短段为 x，长段比短段 3 倍少 2，总长 26。方程应是？",
                    ["x + 3x - 2 = 26", "x + 3x + 2 = 26", "3x - 2 = 26", "x - 3x = 26"],
                    0,
                    "长段是 3x - 2，总长是短段加长段。",
                ),
                q(
                    "若 x + (2x + 6) = 30，则 x 等于多少？",
                    ["6", "8", "10", "12"],
                    1,
                    "3x + 6 = 30，3x = 24，x = 8。",
                ),
            ],
        ),
        lecture(
            "数学五：数列与表格速率",
            [
                "数列题先判断是等差、等比、交替，还是分组规律",
                "表格题不要被总数迷惑，要看题目要比较 total 还是 rate",
                "速率公式：rate = quantity / time",
                "常见错因：总量更大不代表效率更高",
            ],
        ),
        quiz(
            "随堂测：数列与速率",
            [
                q(
                    "数列 2, 10, 4, 20, 6, 30, __ 下一项是？",
                    ["8", "32", "40", "60"],
                    0,
                    "奇数位是 2,4,6,8；偶数位是 10,20,30。",
                ),
                q(
                    "周一 48 个灯具/6 小时，周二 54 个/9 小时，哪天每小时更多？",
                    ["周一", "周二", "一样", "不能比较"],
                    0,
                    "周一 8 个/小时，周二 6 个/小时。",
                ),
            ],
        ),
        lecture(
            "数学三：单位换算与电工计算入口",
            [
                "单位换算先写已知/未知：known、unknown、unit",
                "常见电工入口：V 电压、I 电流、R 电阻、P 功率",
                "欧姆定律：V = I * R，可变形为 I = V/R，R = V/I",
                "功率关系：P = V * I；不要把功率公式和电阻公式混用",
            ],
        ),
        lecture(
            "例题：欧姆定律",
            [
                "题目：120V 电路中，电流为 2A，等效电阻是多少？",
                "已知：V=120V，I=2A",
                "未知：R",
                "公式：R = V / I = 120 / 2 = 60 ohms",
                "检查：单位是 ohms，不是 watts",
            ],
        ),
        quiz(
            "随堂测：公式选择",
            [
                q("120V、2A 求功率 P，应使用哪个公式？", ["R=V/I", "P=V*I", "I=V/R", "V=I/R"], 1, "功率用 P=V*I。"),
                q("24V、6A 求电阻 R，答案是多少？", ["4 ohms", "30 ohms", "144 watts", "18 amps"], 0, "R=V/I=24/6=4 ohms。"),
            ],
        ),
        lecture(
            "阅读理解：先定位，再判断",
            [
                "第一遍：看题干问主旨、细节、推论还是词义",
                "第二遍：在原文中找证据句，不凭印象答题",
                "答案必须被文本支持；常见陷阱是“听起来对，但文中没说”",
                "计时策略：先做确定题，标记耗时题，最后回看",
            ],
        ),
        lecture(
            "例题：技术说明阅读",
            [
                "短文：A trainee must verify that a circuit is de-energized before inspection.",
                "问题：检查前必须确认什么？",
                "证据词：must verify、de-energized、before inspection",
                "答案方向：确认电路已断电/无电",
                "错因：看到 inspection 就只回答“开始检查”，漏掉 before 条件",
            ],
        ),
        quiz(
            "随堂测：阅读定位",
            [
                q(
                    "短文说：The form must be submitted before the deadline. 题目问必须什么时候提交？",
                    ["截止日前", "截止日后", "任何时候", "面试当天才交"],
                    0,
                    "before the deadline 直接给出时间条件。",
                ),
                q(
                    "阅读题遇到听起来合理但原文没出现的选项，应如何处理？",
                    ["优先选", "只要专业就选", "除非能定位证据，否则不选", "跳过所有细节题"],
                    2,
                    "阅读理解考文本证据，不考个人常识联想。",
                ),
            ],
        ),
        lecture(
            "阅读二：限定词陷阱",
            [
                "重点圈词：before、after、only、unless、except、not、required",
                "限定词会改变动作顺序、条件和例外",
                "答题前先说出控制答案的短语",
                "错因标签：看到关键词但漏掉否定或时间顺序",
            ],
        ),
        lecture(
            "例题：before / instead of",
            [
                "短文：Before a tool is returned to storage, it must be wiped clean and inspected.",
                "短文：If damage is found, report it instead of placing it back on the shelf.",
                "问题一：入库前做什么？答案必须包含 wipe + inspect",
                "问题二：发现损坏后做什么？答案是 report，不是 return",
                "方法：把 before 和 instead of 直接标出来",
            ],
        ),
        quiz(
            "随堂测：阅读限定词",
            [
                q(
                    "Passage: Report damage instead of returning the tool. 哪个动作被替代？",
                    ["报告损坏", "归还工具", "清洁工具", "检查工具"],
                    1,
                    "instead of 后面的 returning the tool 是被替代的动作。",
                ),
                q(
                    "题干含有 EXCEPT 时，最稳的第一步是什么？",
                    ["直接选最熟悉的", "把 EXCEPT 圈出来并找不符合项", "忽略大写词", "只看最后一句"],
                    1,
                    "EXCEPT 要找例外，不是找普通正确项。",
                ),
            ],
        ),
        lecture(
            "阅读三：排除法不是猜",
            [
                "每个选项都问：原文是否支持？是否过度推论？是否偷换时间/对象？",
                "先排掉与原文冲突的选项",
                "再排掉原文没说的选项",
                "最后比较剩下选项的精确程度",
                "如果两个选项都像对，回到证据句，不看个人感觉",
            ],
        ),
        lecture(
            "机械理解：杠杆、滑轮、齿轮",
            [
                "杠杆：力臂越长，所需力通常越小",
                "滑轮：更多承重绳段通常降低单段受力，但改变移动距离",
                "齿轮：相邻齿轮旋转方向相反；大小影响速度和扭矩",
                "平衡题先找支点、力的方向和距离",
            ],
        ),
        lecture(
            "例题：杠杆平衡",
            [
                "题目：同样重量离支点越远，会发生什么？",
                "关键：力矩 = 力 * 距离",
                "距离越远，对平衡影响越大",
                "如果要保持平衡，另一侧需要更大的力或更长距离",
                "错因：只看重量，不看距离",
            ],
        ),
        quiz(
            "随堂测：机械推理",
            [
                q(
                    "两个齿轮咬合，左齿轮顺时针转，右齿轮通常如何转？",
                    ["顺时针", "逆时针", "不动", "上下移动"],
                    1,
                    "相邻咬合齿轮方向相反。",
                ),
                q(
                    "杠杆题中同样重量离支点更远，通常意味着什么？",
                    ["影响更小", "影响更大", "没有影响", "重量变轻"],
                    1,
                    "力矩与距离有关，距离越远力矩越大。",
                ),
            ],
        ),
        lecture(
            "机械二：滑轮和力的方向",
            [
                "固定滑轮主要改变用力方向",
                "动滑轮通常能降低所需力，但绳子要拉更长距离",
                "题目问省力还是改变方向，要分开判断",
                "先数承重绳段，再看拉力方向",
            ],
        ),
        quiz(
            "随堂测：滑轮",
            [
                q(
                    "一个固定滑轮最典型的作用是什么？",
                    ["改变用力方向", "让物体消失", "一定让力变成零", "改变材料重量"],
                    0,
                    "固定滑轮主要改变力的方向，不自动消除重量。",
                ),
                q(
                    "动滑轮省力通常带来的代价是什么？",
                    ["绳子需要拉更长距离", "重量变大", "方向无法改变", "没有任何代价"],
                    0,
                    "机械优势常伴随移动距离增加。",
                ),
            ],
        ),
        lecture(
            "机械三：齿轮链追踪",
            [
                "相邻齿轮方向相反",
                "A 带 B，B 带 C：方向反转两次，C 与 A 同向",
                "奇数次接触：末端与起点反向；偶数次接触：同向",
                "大小齿轮影响速度/扭矩，不改变相邻反向规则",
            ],
        ),
        quiz(
            "随堂测：齿轮链",
            [
                q(
                    "A 咬合 B，B 咬合 C，A 顺时针，则 C 怎么转？",
                    ["顺时针", "逆时针", "不转", "无法判断"],
                    0,
                    "A 到 B 反一次，B 到 C 再反一次，所以 C 与 A 同向。",
                ),
                q(
                    "三个相邻接触的齿轮对方向意味着什么？",
                    ["方向反转三次", "方向永远相同", "没有运动传递", "大小决定方向"],
                    0,
                    "每次直接咬合都会反转方向。",
                ),
            ],
        ),
        lecture(
            "机械四：斜面和力的分解",
            [
                "斜面通常降低直接抬起所需的瞬时力",
                "坡越缓，路径越长，所需推力通常越小",
                "问题问方向时，先画重力向下，再画沿斜面的运动方向",
                "错因：只看高度，不看坡长和方向",
            ],
        ),
        lecture(
            "空间推理：旋转、展开、纸折叠",
            [
                "旋转题：固定一个标记点，跟踪它的位置变化",
                "展开图：找相邻面，不要只看形状相似",
                "纸折叠：先判断折叠轴，再把孔或图案镜像过去",
                "常见错因：把旋转当镜像，把镜像当平移",
            ],
        ),
        lecture(
            "例题：纸折叠思路",
            [
                "题目：纸向右对折，在折后左上角打孔，展开后孔在哪里？",
                "Step 1：折叠轴在中线",
                "Step 2：孔会在折叠轴两侧镜像出现",
                "Step 3：高度不变，左右位置镜像",
                "不要猜图案，先画轴线",
            ],
        ),
        quiz(
            "随堂测：空间推理",
            [
                q(
                    "纸向右对折后打孔，展开时孔的位置关系通常是什么？",
                    ["只保留一个孔", "关于折叠轴镜像", "随机分布", "全部移到下方"],
                    1,
                    "折叠展开后的孔以折叠轴为镜像关系。",
                ),
                q(
                    "旋转题最稳的第一步是什么？",
                    ["凭感觉选", "固定一个标记点跟踪", "只看颜色", "跳过题干"],
                    1,
                    "跟踪标记点可以避免把旋转误判成镜像。",
                ),
            ],
        ),
        lecture(
            "空间二：旋转不是镜像",
            [
                "旋转：图形整体绕中心转，左右手性不改变",
                "镜像：像照镜子，左右关系会翻转",
                "方法：选一个不对称标记点，追踪它转到哪里",
                "如果标记点相对顺序反了，可能是镜像，不是旋转",
            ],
        ),
        quiz(
            "随堂测：旋转与镜像",
            [
                q(
                    "判断旋转题时，为什么要选一个不对称标记点？",
                    ["为了跟踪位置变化", "为了忽略题干", "为了猜最长选项", "为了改变图形大小"],
                    0,
                    "标记点能帮助区分旋转、平移和镜像。",
                ),
                q(
                    "镜像变换最常见的变化是什么？",
                    ["左右关系翻转", "面积一定变大", "颜色一定改变", "图形消失"],
                    0,
                    "镜像会翻转左右关系，但大小通常不变。",
                ),
            ],
        ),
        lecture(
            "空间三：展开图邻接判断",
            [
                "展开图题先找中心面，再找直接相邻的边",
                "对面不能在立方体上共享一条边",
                "不要只按视觉距离判断，要按折叠后的接触边判断",
                "做题顺序：标中心 -> 标上下左右 -> 推对面 -> 排除矛盾",
            ],
        ),
        quiz(
            "随堂测：展开图",
            [
                q(
                    "立方体展开图中，两个折叠后相对的面能否共享一条边？",
                    ["能", "不能", "一定重叠", "一定相邻"],
                    1,
                    "相对面在立方体上不共享边。",
                ),
                q(
                    "展开图题最稳的第一步是什么？",
                    ["找中心面和相邻边", "数颜色", "选最大面", "直接猜立体图"],
                    0,
                    "中心面和相邻边决定折叠关系。",
                ),
            ],
        ),
        lecture(
            "个人经历表：把经历写成证据",
            [
                "不要写空泛形容词：勤奋、感兴趣、愿意学习",
                "要写可验证事实：课程、证书、工作任务、志愿经历、工具使用、安全培训",
                "结构：情境 -> 行动 -> 结果 -> 证据附件",
                "边界：没有做过的事不要编；不确定的资格不要承诺",
            ],
        ),
        quiz(
            "随堂测：证据表达",
            [
                q(
                    "哪一句更像有效证据？",
                    [
                        "我很喜欢电工",
                        "我很努力",
                        "我完成了 40 小时安全课程，并能提供证书",
                        "我以后会学得很快",
                    ],
                    2,
                    "可验证事实比泛泛态度更能支撑申请材料。",
                )
            ],
        ),
        lecture(
            "申请证据清单",
            [
                "身份和联系方式：按项目要求准备，不在课堂里猜具体表格",
                "教育经历：高中、GED、相关课程或培训证明",
                "工作/志愿经历：写清任务、时间、负责人、可验证材料",
                "安全/工具经历：证书、照片、主管证明要能对应到事实",
                "缺口管理：没有材料就列待办，不编造经历",
            ],
        ),
        lecture(
            "PEF 写作框架：STAR-E",
            [
                "S Situation：当时是什么场景",
                "T Task：你负责什么任务",
                "A Action：你具体做了什么",
                "R Result：结果或反馈是什么",
                "E Evidence：有什么证据能证明",
            ],
        ),
        quiz(
            "随堂测：申请材料边界",
            [
                q(
                    "如果没有某项安全培训证书，最合适的写法是什么？",
                    ["写已完成但找不到", "列为待补证据", "夸大为现场经验", "删除所有经历"],
                    1,
                    "高风险申请材料必须区分已有证据和待补证据。",
                ),
                q(
                    "STAR-E 中 E 代表什么？",
                    ["Energy", "Evidence", "Estimate", "Exam"],
                    1,
                    "E 是 Evidence，用来连接可验证材料。",
                ),
            ],
        ),
        lecture(
            "错因标签与补救策略",
            [
                "计算错：回到 known/unknown/unit，再做同型变式",
                "公式错：先判断求什么量，再选公式",
                "阅读错：标证据句，不允许凭印象",
                "机械错：画力、支点、方向、距离",
                "空间错：画折叠轴或跟踪标记点",
                "时间错：先降速保正确率，再逐步计时",
            ],
        ),
        lecture(
            "错题日志模板",
            [
                "题型：数学 / 阅读 / 机械 / 空间 / 证据表达",
                "错因：公式、单位、限定词、方向、镜像、速度、粗心",
                "修复动作：重讲概念、再做一步、同型变式、计时复测",
                "复测证据：第二天同型题是否独立做对",
                "升级条件：连续两次复测达标，再进入混合练习",
            ],
        ),
        lecture(
            "计时策略：先准后快",
            [
                "第一阶段：不计时，保证方法正确",
                "第二阶段：小组计时，例如 5 题 8 分钟",
                "第三阶段：混合计时，训练题型切换",
                "跳题规则：超过预设时间仍没思路，标记后继续",
                "复盘时看错因，不只看总分",
            ],
        ),
        quiz(
            "单元综合测",
            [
                q("2x + 7 = 19，x 等于多少？", ["4", "5", "6", "12"], 2, "两边减 7 得 2x=12，所以 x=6。"),
                q("如果 3 个小捆对应 2 个大捆，总份数是多少？", ["2", "3", "5", "6"], 2, "比例 3:2 的总份数是 5。"),
                q("阅读题最需要依赖什么？", ["文本证据", "常识联想", "最长选项", "专业词数量"], 0, "答案必须由原文支持。"),
                q("相邻咬合齿轮的方向通常怎样？", ["相同", "相反", "随机", "都静止"], 1, "相邻齿轮方向相反。"),
            ],
        ),
        quiz(
            "错因诊断测",
            [
                q(
                    "学习者会选答案，但没有选项时不会列式，这属于什么问题？",
                    ["答案选择依赖", "阅读证据强", "机械推理强", "资格证据完整"],
                    0,
                    "能认选项不等于能独立生成解法，需要切换到无选项练习。",
                ),
                q(
                    "空间题直接猜结果、不画折叠轴，最适合的补救是什么？",
                    ["要求画轴线并说出镜像步骤", "加快计时", "跳到合同法", "只背答案"],
                    0,
                    "视觉推理要先修复过程追踪，再看最终答案。",
                ),
            ],
        ),
        lecture(
            "强化段：考试日解题流水线",
            [
                "第一遍：先做自己稳定拿分的题，不在陌生题上硬耗",
                "第二遍：回到标记题，用 known / unknown / unit 重新建模",
                "第三遍：只检查高风险项：符号、单位、百分比分母、题干限定词",
                "每 10 分钟做一次微检查：我是在推理，还是在猜？",
                "目标不是每题都快，而是把会做题稳定做对",
            ],
        ),
        lecture(
            "数学强化：单位换算三栏表",
            [
                "三栏：已知量 | 换算关系 | 目标单位",
                "例：18 inches 转 feet，换算关系是 12 inches = 1 foot",
                "写成 18 inches x 1 foot / 12 inches，inches 抵消",
                "得到 18/12 = 1.5 feet",
                "错因警报：如果单位没有抵消，式子方向可能反了",
            ],
        ),
        quiz(
            "强化测：单位换算",
            [
                q(
                    "36 inches 等于多少 feet？",
                    ["2", "3", "4", "12"],
                    1,
                    "12 inches = 1 foot，所以 36 / 12 = 3 feet。",
                ),
                q(
                    "5 feet 等于多少 inches？",
                    ["17", "36", "60", "72"],
                    2,
                    "1 foot = 12 inches，所以 5 x 12 = 60 inches。",
                ),
                q(
                    "单位换算列式时，最先检查什么？",
                    ["答案是否最大", "单位是否抵消", "选项是否熟悉", "题干是否很短"],
                    1,
                    "单位抵消能快速发现分子分母放反的问题。",
                ),
            ],
        ),
        lecture(
            "数学强化：平均数、速率和工作量",
            [
                "平均数：总量 / 个数",
                "速率：总距离或总工作量 / 时间",
                "工作题：先设总工作量为 1，再写每小时完成几分之几",
                "表格题：看每一步变化是否固定，不固定时不要套等差",
                "检查：答案单位要和题目问法一致",
            ],
        ),
        quiz(
            "强化测：平均数与速率",
            [
                q(
                    "四次数学练习分数为 70、80、85、85，平均分是多少？",
                    ["78", "80", "82", "85"],
                    1,
                    "总分 320，除以 4 得 80。",
                ),
                q(
                    "一人 3 小时完成 24 个同类任务，平均每小时完成多少个？",
                    ["6", "8", "12", "72"],
                    1,
                    "速率 = 24 / 3 = 8 个/小时。",
                ),
                q(
                    "如果题目问 minutes per item，应该用什么方向？",
                    ["item / minutes", "minutes / item", "item x minutes", "只看最大数"],
                    1,
                    "per 后面的量在分母；minutes per item 是分钟数除以件数。",
                ),
            ],
        ),
        lecture(
            "代数强化：括号与负号",
            [
                "先处理括号，再合并同类项",
                "负号分配：-(a - b) = -a + b",
                "两边同时做同一件事，方程才保持平衡",
                "代入检查：把求出的 x 放回原式，看左右是否相等",
                "常见错因：把 -2(x - 3) 写成 -2x - 6",
            ],
        ),
        quiz(
            "强化测：括号与负号",
            [
                q(
                    "2(x + 3) = 14，x 等于多少？",
                    ["4", "5", "7", "11"],
                    0,
                    "展开得 2x + 6 = 14，所以 2x = 8，x = 4。",
                ),
                q(
                    "-(x - 5) 等于什么？",
                    ["-x - 5", "-x + 5", "x - 5", "x + 5"],
                    1,
                    "负号要分配给括号内每一项，所以是 -x + 5。",
                ),
                q(
                    "解完方程后最可靠的检查方式是什么？",
                    ["看选项位置", "把答案代回原式", "把答案乘 2", "重新读标题"],
                    1,
                    "代回原式能直接验证左右是否相等。",
                ),
            ],
        ),
        lecture(
            "阅读强化：题干先分类",
            [
                "主旨题：问整段在讲什么，不要只抓一个细节词",
                "细节题：回原文定位同义表达",
                "推断题：只能做小推断，不能加入外部常识",
                "否定题：圈出 NOT / EXCEPT / least likely",
                "排序题：把步骤词标出来，例如 first, then, after",
            ],
        ),
        quiz(
            "强化测：阅读题型",
            [
                q(
                    "题干问 main purpose，最应该找什么？",
                    ["整段目的", "最难的单词", "最长数字", "最后一个选项"],
                    0,
                    "main purpose 是主旨/目的题，答案要覆盖整段。",
                ),
                q(
                    "题干出现 EXCEPT 时，第一步是什么？",
                    ["圈出 EXCEPT", "直接选最熟悉的", "跳过原文", "只看第一句"],
                    0,
                    "否定限定词会反转任务，必须先标出来。",
                ),
                q(
                    "推断题最安全的答案通常是什么？",
                    ["原文可支持的小推论", "听起来专业的说法", "外部经验", "绝对化判断"],
                    0,
                    "推断仍要被文本证据约束。",
                ),
            ],
        ),
        lecture(
            "机械强化：杠杆三问",
            [
                "问 1：支点在哪里？",
                "问 2：力臂哪边更长？",
                "问 3：题目问省力、方向，还是平衡？",
                "力臂越长，达到同样转动效果所需力越小",
                "图题先标支点，不标支点就容易凭感觉乱选",
            ],
        ),
        quiz(
            "强化测：杠杆",
            [
                q(
                    "同样重量下，手离支点越远，通常会怎样？",
                    ["更省力", "更费力", "没有影响", "一定断裂"],
                    0,
                    "力臂变长，所需力通常变小。",
                ),
                q(
                    "杠杆题第一步最应该标什么？",
                    ["支点", "颜色", "题号", "最长文字"],
                    0,
                    "支点决定力臂方向和长度。",
                ),
                q(
                    "如果两边重量相同，哪边更容易下沉？",
                    ["离支点更远的一边", "离支点更近的一边", "字母靠前的一边", "无法判断且永远无关"],
                    0,
                    "同重量下，力臂更长的一边转矩更大。",
                ),
            ],
        ),
        lecture(
            "空间强化：坐标跟踪法",
            [
                "给图形选一个明显标记点，例如右上角的小点",
                "旋转题：跟踪这个点绕中心移动到哪里",
                "镜像题：左右或上下翻转，距离镜面相等",
                "折叠题：折线是镜面，孔洞/标记点沿折线翻过去",
                "不要同时凭整体形状和局部点猜，优先跟踪局部点",
            ],
        ),
        quiz(
            "强化测：空间跟踪",
            [
                q(
                    "判断镜像题时，标记点到镜面的距离会怎样？",
                    ["相等", "翻倍", "变成 0", "随机变化"],
                    0,
                    "镜像前后到镜面的垂直距离相等。",
                ),
                q(
                    "旋转题最可靠的策略是什么？",
                    ["跟踪一个标记点", "看哪个选项最大", "只看颜色", "只看题号"],
                    0,
                    "标记点能减少整体形状错觉。",
                ),
                q(
                    "纸折叠打孔题，折线应被看成什么？",
                    ["镜面", "比例尺", "电阻", "速度单位"],
                    0,
                    "折叠后的孔位沿折线镜像展开。",
                ),
            ],
        ),
        lecture(
            "申请材料强化：证据不是口号",
            [
                "弱表达：我很努力、我很感兴趣、我能吃苦",
                "强表达：做过什么、持续多久、谁能证明、结果是什么",
                "电工相关证据：数学课程、动手项目、安全意识、准时可靠、团队合作",
                "不夸大：没有做过的不要写成经验",
                "目标：让面试官能追问、能验证、能相信",
            ],
        ),
        quiz(
            "强化测：证据质量",
            [
                q(
                    "下面哪句更像可验证证据？",
                    ["我很有激情", "我连续 8 周完成晚间数学复习记录", "我一定最强", "我什么都能做"],
                    1,
                    "时间、动作和记录让陈述可验证。",
                ),
                q(
                    "没有正式电工经验时，最应展示什么？",
                    ["可迁移能力和学习证据", "编造项目经验", "只写口号", "隐藏所有经历"],
                    0,
                    "入门阶段重点是可迁移能力、可靠性和学习能力。",
                ),
                q(
                    "申请材料中最危险的做法是什么？",
                    ["夸大无法证明的经历", "列出真实课程", "说明可用时间", "请推荐人作证"],
                    0,
                    "不可验证或夸大的经历会破坏可信度。",
                ),
            ],
        ),
        lecture(
            "小模拟考规则：30 分钟闭卷",
            [
                "结构建议：数学 8 题、阅读 4 题、机械 4 题、空间 4 题",
                "先用原创题模拟，不碰泄露题或来路不明真题",
                "做题时只允许草稿纸，不允许查公式讲义",
                "结束后先分类错因，再看解析",
                "达标线：总正确率 80%，且每类至少 70%",
            ],
        ),
        quiz(
            "小模拟考：混合题",
            [
                q("15 是 60 的百分之几？", ["15%", "20%", "25%", "40%"], 2, "15 / 60 = 0.25 = 25%。"),
                q("4y - 6 = 10，y 等于多少？", ["3", "4", "5", "16"], 1, "4y = 16，所以 y = 4。"),
                q("如果每小时完成 9 题，4 小时完成多少题？", ["13", "27", "36", "45"], 2, "9 x 4 = 36。"),
                q("阅读题问 according to the passage，应优先依据什么？", ["原文证据", "个人经验", "专业猜测", "最长选项"], 0, "according to the passage 要求回到原文。"),
                q("两个直接咬合齿轮方向如何？", ["相同", "相反", "都向上", "都向下"], 1, "相邻咬合齿轮方向相反。"),
                q("一个定滑轮主要改变什么？", ["力的方向", "物体重量", "电压", "长度单位"], 0, "理想定滑轮主要改变施力方向。",
                ),
            ],
        ),
        lecture(
            "小模拟考讲评方法",
            [
                "不要只写对错，要写错因标签",
                "数学错：补同型 3 题，直到不用看选项也能列式",
                "阅读错：回原文标证据句，并说明错误选项为什么不成立",
                "机械/空间错：要求补图，图比口头解释更能暴露误区",
                "讲评结束后生成下一轮 3 天微计划",
            ],
        ),
        lecture(
            "考前一天检查清单",
            [
                "确认考试时间、地点、证件、交通和提前到达时间",
                "准备普通计算草稿策略，但不依赖未允许的工具",
                "复习错题日志中的高频错因，不再大量刷新题",
                "睡眠和节奏比临时硬背更重要",
                "最后一遍提醒：题目问什么，就回答什么",
            ],
        ),
        lecture(
            "7 天复习安排",
            [
                "Day 1：诊断 + 错因分类",
                "Day 2：分数、小数、百分比、比例",
                "Day 3：代数方程、函数代入、表格关系",
                "Day 4：阅读理解定位训练",
                "Day 5：机械推理和空间推理",
                "Day 6：混合练习 + 计时策略",
                "Day 7：综合测 + 个人经历证据清单",
            ],
        ),
        lecture(
            "14 天加厚复习安排",
            [
                "Days 1-2：诊断、基础计算、错题日志模板",
                "Days 3-4：比例/百分比/文字题建模",
                "Days 5-6：数列、表格速率、函数代入",
                "Days 7-8：阅读定位、限定词、证据排除",
                "Days 9-10：杠杆、滑轮、齿轮、斜面",
                "Days 11-12：旋转、镜像、展开图、纸折叠",
                "Days 13-14：混合计时、PEF 证据、readiness gate",
            ],
        ),
        lecture(
            "结课 readiness gate",
            [
                "数学：基础题正确率 >= 80%，能解释错因",
                "阅读：每题能指出证据句",
                "机械/空间：能画出关键关系，而不是凭感觉",
                "证据材料：能列出已具备和待补证明",
                "下一步：按本地 apprenticeship 官方流程确认申请要求和考试版本",
            ],
        ),
    ]
    scenes = []
    order = 1
    for spec in scene_specs:
        if spec["kind"] == "quiz":
            questions = spec["questions"]
            for question_index, question in enumerate(questions, start=1):
                title = (
                    spec["title"]
                    if len(questions) == 1
                    else f"{spec['title']} - 第 {question_index} 题"
                )
                scene_id = f"scene-{order:02d}-{slug(spec['title'])}-q{question_index}"
                scenes.append(quiz_scene(course_id, scene_id, order, title, [question]))
                order += 1
        else:
            scene_id = f"scene-{order:02d}-{slug(spec['title'])}"
            scenes.append(slide_scene(course_id, scene_id, order, spec["title"], spec["lines"]))
            order += 1
    return scenes


def lecture(title: str, lines: list[str]) -> dict[str, Any]:
    return {"kind": "lecture", "title": title, "lines": lines}


def quiz(title: str, questions: list[dict[str, Any]]) -> dict[str, Any]:
    return {"kind": "quiz", "title": title, "questions": questions}


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
                    text_element(f"{scene_id}-title", title, 80, 74, 1040, 58, 34, True),
                    text_element(
                        f"{scene_id}-body",
                        "\n".join(lines),
                        110,
                        164,
                        1060,
                        430,
                        23,
                        False,
                    ),
                ],
            },
        },
        "createdAt": 0,
        "updatedAt": 0,
        "metadata": {"source": "cognisphereTutor", "demo_role": "entrance_courseware"},
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
        "metadata": {"source": "cognisphereTutor", "demo_role": "entrance_assessment"},
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
        "lineHeight": 1.55,
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


if __name__ == "__main__":
    main()
