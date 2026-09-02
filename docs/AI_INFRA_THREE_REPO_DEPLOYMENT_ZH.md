# AI Infra 学习系统三仓部署说明

AI Infra 学习系统由 Tutor、LearningPlugins、Twin 三个仓库协作完成。它不是 Tutor 单仓内置课程，也不是由大模型临时生成课程路径。

## 仓库职责

| 仓库 | 职责 | 新用户是否必须安装 |
| --- | --- | --- |
| `cognisphereTutor` | 原生学习会话、Mastery Path、学习进度、Web UI、后端代理 | 必须 |
| `CognisphereLearningPlugins` | AI infra 课程包、可信上下文绑定、课程结构、测验、学习路径种子 | 必须 |
| `AetherAI-Infra-Twin` | 实验运行、孪生 WebUI、证据包、诊断评分、仿真/回放 | 做实验时必须 |

## 如果只下载 Tutor 和 LearningPlugins

这是内容学习模式。可用：

- 课程总介绍
- 按顺序推进的 Mastery Path
- 对话式小课
- 测验、诊断问题、反思
- 已整理的可信来源上下文

不可用：

- 运行真实 lab
- 生成新的 evidence bundle
- 打开 Twin lab 控制台
- 使用实验证据完成诊断评分

Tutor 应把这种状态显示为“学习内容可用，Twin 实验未连接”，而不是课程不可用。

## 完整安装

```powershell
cd D:\Projects
git clone https://github.com/johnslee1207-commits/cognisphereTutor.git
git clone https://github.com/johnslee1207-commits/CognisphereLearningPlugins.git
git clone https://github.com/johnslee1207-commits/AetherAI-Infra-Twin.git
```

启动 Twin：

```powershell
cd D:\Projects\AetherAI-Infra-Twin
python -m pip install -e .
python -m unittest discover -s tests
python -m aetherinfra.cli validate-contracts
python -m aetherinfra.cli serve-web --host 127.0.0.1 --port 8765
```

启动 Tutor：

```powershell
$env:COGNISPHERE_LEARNING_PLUGINS_ROOT = "D:\Projects\CognisphereLearningPlugins"
$env:AETHERINFRA_TWIN_BASE_URL = "http://127.0.0.1:8765"
$env:AETHERINFRA_TWIN_EMBED_URL = "http://127.0.0.1:8765"

cd D:\Projects\cognisphereTutor
python -m pip install -e .
cognispheretutor start
```

常用入口：

- 学习空间：`http://127.0.0.1:3782/space/learning?domains=ai_infra`
- 原生学习会话：`http://127.0.0.1:3782/home/csphere-ai_infra?capability=mastery_path`
- Twin 控制台：`http://127.0.0.1:8765/`

## 健康检查

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/summary
Invoke-RestMethod http://127.0.0.1:3782/api/v1/learning/ai-infra-twin/status
```

第二个接口通过 Tutor 代理检查 Twin 状态。返回 `ok=true` 表示实验能力已接通；返回不可用时仍可继续内容学习。
