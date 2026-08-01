# AWS Digital Twin — Tutor 加载演示包

| Field | Value |
|-------|-------|
| **Document ID** | `cognisphere.tutor.aws_dt_demo_pack.v1` |
| **As of** | 2026-08-01 |
| **LP SoT** | `CognisphereLearningPlugins/manifests/ops/aws_dt_tutor_demo_package_profile.json` |
| **Demo CLI** | `cognispheretutor cognisphere aws-twin-mastery` |
| **Constraint** | Install twin from LP wheels — do **not** copy fat engine into Tutor |

Fixture-only：无 live AWS、无 LLM。Pack 缺失时 fail-closed。

---

## 背景

Tutor 通过进程环境 `COGNISPHERE_LEARNING_PLUGINS_ROOT` 发现 Learning Plugins（项目根 `.env` **不会**被读取）。  
`aws-twin-mastery` 薄客户端再 `import cognisphere_plugins.aws_certification_twin…`（site-packages 或 monorepo `plugins/.../src`）。

推荐路径：在 LP 仓构建 **演示包**（sdk + twin + meta wheel），`pip install` 后把 packs root 指到 `dist/aws_dt_tutor_demo` 或 monorepo 根。

---

## 构建（Learning Plugins）

```powershell
cd D:\Projects\CognisphereLearningPlugins
python scripts/build_aws_dt_tutor_demo_package.py
# 或: powershell -File scripts/build_aws_dt_tutor_demo_package.ps1
```

产物：`D:\Projects\CognisphereLearningPlugins\dist\aws_dt_tutor_demo\`

---

## 安装到本机 Tutor Python

```powershell
powershell -File D:\Projects\CognisphereLearningPlugins\dist\aws_dt_tutor_demo\install.ps1
```

或手工：

```powershell
python -m pip install --no-index --find-links=D:\Projects\CognisphereLearningPlugins\dist\aws_dt_tutor_demo\wheels cognisphere-plugin-sdk cognisphere-plugins-aws-certification-twin cognisphere-plugins-aws-dt-tutor-demo
$env:COGNISPHERE_LEARNING_PLUGINS_ROOT = "D:\Projects\CognisphereLearningPlugins\dist\aws_dt_tutor_demo"
```

开发者 editable（仍指向 monorepo）：

```powershell
$env:COGNISPHERE_LEARNING_PLUGINS_ROOT = "D:\Projects\CognisphereLearningPlugins"
```

环境模板（需自行导入进程）：[`../../examples/aws_dt_demo.env.example`](../../examples/aws_dt_demo.env.example)

---

## 校验 + 演示命令

```powershell
cd D:\Projects\cognisphereTutor
powershell -File scripts/verify_aws_dt_demo_load.ps1
cognispheretutor cognisphere aws-twin-mastery
```

期望：`ok=true` / `runtime_mode=fixture_stub`。API：`GET|POST /api/v1/learning/cognisphere/aws-twin-mastery`。

Python 校验：

```powershell
python -c "from cognispheretutor.integrations.cognisphere.aws_dt_demo_pack import verify_aws_dt_demo_pack; import json; print(json.dumps(verify_aws_dt_demo_pack(), indent=2))"
```

---

## 故障排查

| 现象 | 处理 |
|------|------|
| `plugins_root_missing` / verify fail | 设置进程 env `COGNISPHERE_LEARNING_PLUGINS_ROOT` 到存在的目录 |
| `twin_digital_twin_mastery_unavailable` | 未 `pip install` twin/meta wheel，或 Python 环境与 CLI 不一致 |
| 想用 monorepo 源码 | packs root 指 LP 根；`domain_package.py install --unit sdk/aws_certification_twin --editable` |
