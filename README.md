# cognisphereTutor Learning Packs Starter

一个面向普通学习者的本地 AI 学习项目：内置 **AWS Certification**、
**AP Calculus**、**LeetCode** 三个学习包，让用户
下载本仓库后即可进入课程学习、Mastery Path、Quick Quiz 和学习进度追踪。

## 项目起点

本仓的目标是提供一个可直接使用的本地 AI 学习体验：

- 普通用户只下载本仓库即可开始 AWS 初级认证学习。
- AWS/AP/LeetCode 学习包随项目分发，不需要额外下载 Cognisphere 或
  CognisphereLearningPlugins。
- Learning Space 中以“课程库”呈现，不暴露 plugin、domain、compose、seed 等
  工程术语。
- 每条课程会生成 Mastery Path，并通过 Chat agent loop 进行讲解、测验和推进。
- 开发者仍可接入外部 CognisphereLearningPlugins，外部插件优先于内置包。

## 当前内置课程

| 课程 | 内置文件 | 当前学习目标 |
| --- | --- | --- |
| AWS Certification | `cognispheretutor/integrations/cognisphere/bundled_packs/aws_certification_bundle.json` | 6 个模块 / 46 个目标 |
| AP Calculus | `cognispheretutor/integrations/cognisphere/bundled_packs/ap_calculus_bundle.json` | 22 个目标 |
| LeetCode | `cognispheretutor/integrations/cognisphere/bundled_packs/leetcode_bundle.json` | 7 个目标 |

## 普通用户快速开始

### 1. 准备环境

需要安装：

- Git
- Python 3.11+
- Node.js 20+

Windows PowerShell 可检查：

```powershell
git --version
python --version
node --version
npm --version
```

### 2. 下载本仓库

```powershell
cd D:\Projects
git clone https://github.com/johnslee1207-commits/cognisphereTutor.git
cd cognisphereTutor
```

### 3. 安装

```powershell
python -m pip install -e .
```

初始化本地配置：

```powershell
cognispheretutor init
```

### 4. 启动

```powershell
cognispheretutor start
```

默认访问地址：

```text
http://127.0.0.1:3782
```

学习空间：

```text
http://127.0.0.1:3782/space/learning
```

## 第一次学习 AWS

1. 打开 `http://127.0.0.1:3782/space/learning`
2. 在左侧找到 `课程库`
3. 找到 `AWS Certification`
4. 点击 `添加课程`
5. 等待学习路径生成
6. 点击 `继续学习`
7. 在学习对话中输入：`我是新手，请从第一课开始`
8. 阅读小课并完成课后 Quick Quiz

也可以在课程库输入框中直接写：

```text
我是 AWS 新手，想从零开始准备初级认证
```

然后点击 `生成学习路径`。

更完整的中文使用说明见：

[guides/AWS_BEGINNER_USER_GUIDE_ZH.md](guides/AWS_BEGINNER_USER_GUIDE_ZH.md)

## 是否需要额外下载 AWS 原始资料

不需要。

AWS 学习课程包已经随本仓库提供。普通用户只需要下载、安装并运行本项目，就可以
开始 AWS 学习。

需要注意的是，模型仍然负责讲解和互动。因此第一次使用前，需要在
`Settings -> Models` 中配置一个可用模型。可以使用云端模型，也可以使用本地
Ollama。

## 学习进度

学习进度保存在本地工作区，通常位于：

```text
data/user/workspace/learning/
```

只要不删除该目录，课程进度会保留。代码升级后通常可以继续之前的学习。

## 架构说明

本项目遵循两层边界：

- **Tutor 核心：** 负责通用编排、课程包发现、导入、Mastery Path、Chat agent
  loop、Quick Quiz、学习进度与 UI。
- **Domain Pack：** 负责领域知识、课程结构、目标、参考资料元数据与领域运行时。

内置 learning packs 是数据包，不把 AWS/AP/LeetCode 的专属教学逻辑硬编码到
Tutor 核心中。

## 开发者路径

普通用户不需要外部插件仓库。开发者如果要测试最新领域包，可以设置：

```powershell
$env:COGNISPHERE_LEARNING_PLUGINS_ROOT = "D:\Projects\CognisphereLearningPlugins"
```

当外部插件仓库存在时，Tutor 会优先使用外部插件；否则自动使用本仓内置 pack。

Handshake SoT（勿在 Tutor 双活协议）：见 `docs/LEARNING_PLUGINS_HANDSHAKE_SOT.md`。
薄客户端：`from cognispheretutor.integrations.cognisphere import handshake`。
Learning→twin 组合流：`learning_twin_flow` / `list_learning_twin_pairs`（SDK SoT；twin stub 默认可容忍；`composition_intent` 透传 `learn_then_practice` \| `failure_drill`）。
Context API 可选绑定：`bind_context_api` / `context_api_status`（SDK SoT；无 `COGNISPHERE_CONTEXT_API_BASE_URL` 时 fail-closed）。
Twin `visualization` 广告薄消费（N-15）：`consume_visualization_advert` / `run_visualization_advert_smoke`（`visualization_advert_client`；仅 status/smoke，无 twin UI）。
AWS CP Product UX 合约（CP-08）：`cp_product_ux_status` / `get_cp_ux_contract_bundle` / `consume_cp_visualization_advert` / `run_cp_product_ux_smoke`（`cp_product_ux_client`；复用 N-15；无 LP/Tutor twin UI）。
AWS CP Socratic（CP-06）：`cp_socratic_tutor_status` / `start_cp_socratic_tutor_session`（`cp_socratic_tutor_client`）。
AWS CP Runtime Interaction（CP-04）：`runtime_interaction_status` / `run_cp_package_experience`（`cp_runtime_interaction_client`）。
AWS twin MVP-2：`mvp_product_status` / `run_mvp_product_flow`（`cp_mvp_product_client`）。
AWS Digital Twin 离线 Mastery：`aws_digital_twin_mastery_status` / `run_aws_digital_twin_mastery`（`aws_digital_twin_mastery_client`；CP-04→可选 CP-06/12；无 Tutor UI 仪式）。
Guided Learning 薄路由：`GET|POST /api/v1/learning/cognisphere/handshake`（及 `/handshake/learning-twin*`）；`GET|POST /api/v1/learning/cognisphere/aws-twin-mastery`；无 packs root 时 fail-closed。CLI：`cognispheretutor cognisphere handshake` / `learning-twin [--intent …]` / `aws-twin-mastery`。
Learning Space（`/space/learning`）侧栏提供 **AWS Digital Twin Mastery** 入口：显示 `gates.aws_twin_mastery` 就绪态、一键跑离线 fixture 练习、**Handshake + Learning→Twin**（`learn_then_practice`），并可将 `aws_certification` 导入为 Mastery Path 后进入 Chat（`?capability=mastery_path`）。在 `csphere-aws_certification` 地图视图中同样可触发 twin 练习 / handshake。Twin 包不走 import-and-seed 课程库（`kind=twin`）。

常用检查命令：

```powershell
python -m pytest tests/learning/test_cognisphere_seed.py tests/integrations/test_cognisphere_registry.py -q
npx tsc --noEmit
```

## 关键目录

```text
cognispheretutor/integrations/cognisphere/
  pack_distribution.py          # 内置 pack 发现、合并、导入
  bundled_packs/                # AWS/AP/LeetCode 内置学习包

cognispheretutor/learning/
  cognisphere_seed.py           # pack knowledge -> Mastery Path

web/app/(utility)/space/learning/
  page.tsx                      # Learning Space / 课程库 UI

guides/
  AWS_BEGINNER_USER_GUIDE_ZH.md # 普通用户 AWS 学习指南
```

## 上游参考

- 上游项目：<https://github.com/HKUDS/cognisphereTutor>
- 上游文档：<https://cognispheretutor.info>
- 上游论文：<https://arxiv.org/abs/2604.26962>

## License

本项目沿用上游仓库许可证，见 [LICENSE](LICENSE)。
