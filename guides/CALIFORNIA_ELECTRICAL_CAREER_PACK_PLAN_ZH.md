# California Electrical Career 课程包实施计划

本文基于 `DeepTutor_California_Electrical_Career_Domain_Pack_v1.0.md`，记录当前在 Tutor 中落地的第一版范围和后续开发路线。

## 当前已实现

已新增内置课程包：

```text
cognispheretutor/integrations/cognisphere/bundled_packs/california_electrical_career_bundle.json
```

该 pack 可被 Learning Space 的课程库自动发现，并可导入为：

```text
csphere-california_electrical_career
```

当前版包含 6 个模块、39 个学习目标，并补充了 29 张可用于 Tutor
mini-lesson 的 lesson cards、8 个 practice blueprint、8 个 learning
activity templates、5 条 study sequences、6 张 scenario cards、3 组
flashcard decks、3 个 readiness checkpoints 和 5 类 error taxonomy：

1. Career Orientation
2. Shared Electrical Foundations
3. ETI / IBEW Local 11 Apprenticeship Entrance
4. California General Electrician
5. California C-10 Electrical Trade
6. California Contractor Law and Business

新增 lesson cards 覆盖：

- 职业路径选择和学习边界
- 电工入门数学、Ohm's Law、series/parallel/combination circuits
- Inside Wireman aptitude test 与 PEF 证据组织
- GE eligibility、GE blueprint、NEC navigation、GE installation
- C-10 blueprint、estimating、safety
- Law & Business blueprint 和 contractor qualifying experience
- GE exam logistics、symbols/diagrams、conductors/raceways、grounding/bonding、
  overcurrent protection、motors/transformers、testing/troubleshooting
- C-10 rough wiring vs finish wiring、special systems / energy storage
- Law & Business contracts/change orders、employment/payroll、liens/insurance/finance
- Public works、prevailing wage、apprenticeship requirements、certified payroll
- Cal/OSHA hazardous energy / lockout-tagout safety

新增 practice blueprints 覆盖：

- Apprenticeship aptitude mixed practice
- GE blueprint-weighted practice
- C-10 closed-book scenario and calculation practice
- Law & Business scenario practice
- GE NEC navigation sprints
- Electrical calculation ladder
- Testing and troubleshooting scenarios
- Public works compliance scenarios

新增 learning activity templates 覆盖：

- mini-lesson followed by one quick check
- worked example with hidden next step
- open-book NEC navigation rehearsal
- contractor scenario judgment
- flashcard ladder
- timed mixed set
- field visualization prompt
- document evidence coach

新增连续学习与个性化复习数据：

- Beginner first-week path
- Inside Wireman apprenticeship entry path
- California General Electrician core path
- C-10 contractor trade path
- Contractor Law and Business scenario path
- aptitude ratio、Ohm's Law、NEC navigation、change order、public works、lockout/tagout 原创场景卡
- electrical foundations、GE navigation、Law & Business scenario cues 闪卡组
- foundations、GE navigation、C-10/Law readiness checkpoints
- topic classification、unit/setup、safety sequencing、documentation boundary、memorization-over-navigation 错因分类

## Cognisphere 来源管理边界

所有官方公开资料、URL、版本号、provenance、变更检测和事实验证都应由
Cognisphere 管理。Tutor 不维护官方 source registry，也不负责 watch 官方网页。

Tutor 只消费 Cognisphere 已物化的 domain pack，并把其中的学习目标、课程结构和
claim 摘要转化为学习体验。

2026-09-03 当前 pack 依赖的 Cognisphere-managed claim refs 覆盖：

- ETI / LAETT Inside Wireman 页面：aptitude test 包含 mathematical reasoning、numerical reasoning、reading comprehension、mechanical reasoning、paper folding；考试时长 2 小时 20 分钟；PEF 可占最终评分最高 40%。
- California DIR Electrician Certification Program：C-10 contractor 下从事 electrician work 的人员需要符合 DLSE certification standards；2026-06-01 后考试调度流程使用 CPS HR Consulting；online application 已开放，trainee online registration 尚未开放。
- California DIR Electrician Certification FAQ：electrician certification exam 为 open-book，测试材料由考点提供，学习范围应参考 Test Info / CIB outline。
- California DIR / DLSE Test Info：General Electrician 为 100 题、4 小时 30 分钟；权重为 Safety 6%、Electrical System Requirements 22%、Installation 66%、Maintenance and Repair 6%。
- California DIR / DLSE General Electrician eligibility：GE 申请要求 8,000 小时 qualifying work。
- California DIR ECCC General Electrician curriculum：覆盖 safety、tools/materials、electrical theory、code requirements、conductors、raceways、lighting、overcurrent devices、grounding、plans/specifications、transformers、testing 等。
- DGS / California Building Standards Commission：Title 24 / California Electrical Code edition metadata 和代码引用边界由 Cognisphere 管理。
- NFPA：NEC / NFPA 70 的 standards-body metadata 和概念引用由 Cognisphere 管理；Tutor 不分发 NEC 全文。
- CSLB C-10 Study Guide：C-10 trade blueprint 覆盖 Planning and Estimating、Rough Wiring、Finish Wiring and Trim、Startup/Troubleshooting/Maintenance、Safety；考试为 closed-book、multiple-choice、每题四个选项，部分题目需要计算。
- CSLB Law & Business Study Guide：覆盖 Business Organization and Licensing、Business Finances、Employment Requirements、Insurance and Liens、Contract Requirements and Execution、Public Works、Safety；考试为 closed-book、multiple-choice、每题四个选项，部分题目需要计算。
- CSLB Studying for the Examination：contractor applicant 需要准备 Law & Business 和 trade examination，study guide 会列出 topic areas、weights、sample questions 和 resources。
- CSLB Qualifying Experience：contractor exam 通常要求 4 年 classification 相关经验；技术/职业培训最多可折抵 3 年，但至少 1 年必须是 practical experience。
- Cal/OSHA / OSHA：hazardous energy、lockout/tagout、电气安全用于安全情境练习。
- California DIR Public Works：public works contractor responsibilities、prevailing wage、apprenticeship、certified payroll 用于 Law & Business 情境练习。

## 为什么先做课程 seed

这份 domain pack 的完整目标很大，包括官方资料摄取、知识图谱、个性化诊断、原创题库、错因模型、模拟考试、证据报告和版本更新 watch。

当前 Tutor 已经具备 bundled pack distribution/import layer、Mastery Path 教学流、
lesson grounding 和 quick quiz 流程，因此第一阶段最合适的落地点是：

- 先让普通用户能在课程库看到这门课
- 先生成可学习的 Mastery Path
- 先让每个主模块有可直接教学的 lesson cards
- 先让后续练习引擎有 practice blueprint
- 先让 Tutor 在同一课程里切换多种学习形式，而不是只有讲解/问答
- 先让 Tutor 能按 study sequence 组织连续学习、按 readiness checkpoint 做阶段门控、
  按 error taxonomy 做错因复习
- 先验证从职业目标到学习目标的基本路径
- 后续再逐步增加诊断、练习、模拟考试和法规/蓝图更新能力

## 后续开发路线

### M1 Apprentice Track

- aptitude diagnostic
- math/numerical/reading/mechanical/spatial 原创练习
- timed mixed practice
- PEF preparation coach

### M2 California GE Core

- 28 个 GE 细分模块
- NEC navigation mastery
- open-book reference navigation phases
- GE blueprint-weighted sectional practice

### M3 C-10 Trade

- planning and estimating
- blueprint reasoning
- material/labor calculation
- startup, troubleshooting, maintenance
- C-10 blueprint mock

### M4 Law & Business

- licensing scenario practice
- contract/change order scenarios
- employment/payroll/tax/insurance
- liens/public works/safety compliance
- Law & Business mock

### M5 Adaptive Tutor

- learner model
- error taxonomy memory
- dynamic remediation plan
- readiness score

### M6 Cognisphere Governance Binding

- 消费 Cognisphere official source watch 结果
- 消费 Cognisphere blueprint version diff
- 根据 Cognisphere impact report 调整 Tutor 课程/题目
- 在 Tutor 侧生成 learner evidence report，但 source evidence 仍引用 Cognisphere provenance

## 当前边界

当前实现不是题库，也不是完整执照考试模拟器。它是一个可进入学习体验的第一版课程包：

- 可以添加课程
- 可以生成学习路径
- 可以逐步进入 Mastery Path
- 可以作为后续题库、诊断和模拟考试的骨架

不包含：

- 泄露真题
- 付费题库内容
- NEC 全文
- 可替代官方资格审查或法律建议的内容
- 官方 source registry 或官方网页 update watch
