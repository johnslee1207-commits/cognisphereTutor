# AI Infra Twin Integration

cognisphereTutor is the learner-facing shell. AetherAI-Infra-Twin is the lab engine that owns AI infrastructure scenarios, execution, evidence, diagnosis scoring, and competency artifacts.

AI infra course content comes from `CognisphereLearningPlugins`. If a learner only
installs `cognisphereTutor` plus `CognisphereLearningPlugins`, the Mastery Path
and source-backed lessons are available in content-only mode. Running labs,
opening the Twin console, and generating new evidence require the third
repository, `AetherAI-Infra-Twin`.

Local development endpoints:

- Tutor frontend: `http://127.0.0.1:8766/space/ai-infra`
- Tutor backend proxy: `http://127.0.0.1:8001/api/v1/learning/ai-infra-twin/status`
- Twin engine: `http://127.0.0.1:8765/`

Environment configuration:

- `AETHERINFRA_TWIN_BASE_URL`: backend-to-Twin API base URL. Defaults to `http://127.0.0.1:8765`.
- `AETHERINFRA_TWIN_EMBED_URL`: browser iframe URL. Defaults to `AETHERINFRA_TWIN_BASE_URL`.

Current integration surface:

- `GET /api/v1/learning/ai-infra-twin/status`
- `GET /api/v1/learning/ai-infra-twin/labs`
- `GET /api/v1/learning/ai-infra-twin/labs/{lab_id}`
- `POST /api/v1/learning/ai-infra-twin/labs/{lab_id}/run`
- `POST /api/v1/learning/ai-infra-twin/labs/{lab_id}/diagnosis`
- `GET /api/v1/learning/ai-infra-twin/curriculum`
- `GET /api/v1/learning/ai-infra-twin/maturity`

The Tutor page at `/space/ai-infra` renders curriculum and maturity summaries in Tutor, then embeds the selected Twin lab console through an iframe. Domain content remains in AetherAI-Infra-Twin; Tutor only owns navigation and presentation.

Full deployment instructions are in
`docs/AI_INFRA_THREE_REPO_DEPLOYMENT_ZH.md`.
