# OpenMAIC Course Runtime Export Contract

DeepTutor owns learning objectives, evidence gates, learner state, and publish
approval. OpenMAIC, or a dedicated export service beside it, owns concrete
PPTX/HTML/MAIC-ZIP artifact generation.

## DeepTutor Configuration

Fresh installs default to `openmaic_course_runtime_mode: "auto"`. In that mode
Tutor first honors explicit environment/settings endpoints, then probes the
configured managed candidates and local OpenMAIC origins such as
`http://127.0.0.1:33100`. If no endpoint is reachable, Tutor keeps using the
in-process course runtime so course authoring still works.

Operators can still configure the runtime adapter explicitly through
`data/user/settings/integrations.json`:

```json
{
  "openmaic_course_runtime_mode": "configured",
  "openmaic_course_runtime_base_url": "https://openmaic.example",
  "openmaic_course_runtime_auto_candidates": [
    "https://managed-openmaic.example"
  ],
  "openmaic_course_runtime_headers": {
    "authorization": "Bearer <runtime-token>"
  },
  "openmaic_course_export_routes": {
    "pptx": "/api/export/pptx",
    "html": "/api/export/html",
    "maic-zip": "/api/export/classroom"
  }
}
```

Deployment overrides may provide the same values through:

- `OPENMAIC_COURSE_RUNTIME_MODE` (`auto`, `configured`, or `disabled`)
- `OPENMAIC_COURSE_RUNTIME_BASE_URL`
- `OPENMAIC_COURSE_RUNTIME_MANAGED_URL`
- `OPENMAIC_COURSE_RUNTIME_AUTO_CANDIDATES`
- `COGNISPHERETUTOR_OPENMAIC_URL`
- `OPENMAIC_COURSE_RUNTIME_HEADERS`
- `OPENMAIC_COURSE_EXPORT_ROUTES`

`OPENMAIC_COURSE_RUNTIME_AUTO_CANDIDATES` is a comma-separated list of
OpenMAIC origins. `OPENMAIC_COURSE_RUNTIME_HEADERS` and
`OPENMAIC_COURSE_EXPORT_ROUTES` are JSON objects. Route values may be relative
to `openmaic_course_runtime_base_url` or absolute URLs for a separate service.

## Managed Local Sidecar

`cognispheretutor start` can also launch an OpenMAIC sidecar before the Tutor
backend starts. This keeps the ordinary-user path to one command while still
letting deployment packages decide where the OpenMAIC app binary lives:

- `OPENMAIC_COURSE_RUNTIME_MANAGED_COMMAND` — shell-style command line, for
  example `node server.js` or `npm run start:course-runtime`.
- `OPENMAIC_COURSE_RUNTIME_MANAGED_CWD` — optional working directory for that
  command. Defaults to the active Tutor runtime home.
- `OPENMAIC_COURSE_RUNTIME_MANAGED_ORIGIN` — expected origin. Defaults to
  `http://127.0.0.1:33100`.
- `OPENMAIC_COURSE_RUNTIME_MANAGED_HEALTH_PATH` — health endpoint path.
  Defaults to `/api/health`.

Tutor starts the sidecar only when `openmaic_course_runtime_mode` is `auto`, no
configured runtime URL is present, and no existing managed/local OpenMAIC
endpoint is reachable. The backend then receives
`OPENMAIC_COURSE_RUNTIME_BASE_URL` pointing at the managed origin, so course
render/export calls use the real OpenMAIC adapter instead of the in-memory
fallback.

## Export Endpoint

Each configured route must accept:

```http
POST <configured route>
content-type: application/json
```

```json
{
  "stageId": "course-id",
  "courseId": "course-id",
  "version": "1.0.0",
  "format": "pptx",
  "profile": {}
}
```

The endpoint may return JSON:

```json
{
  "artifact_id": "artifact-123",
  "download_url": "https://openmaic.example/downloads/artifact-123.pptx"
}
```

Accepted ID fields are `artifact_id`, `artifactId`, `id`, or `jobId`.
Accepted URI fields are `url`, `download_url`, `downloadUrl`, `artifact_url`,
or `artifactUrl`.

The endpoint may also stream binary content directly. In that case DeepTutor
uses the `Location` response header as the artifact URI when present.

## DeepTutor API

Callers can request a specific export through:

```http
POST /api/v1/courses/{course_id}/exports/{format}
```

```json
{
  "version": "1.0.0",
  "profile": {},
  "idempotency_key": "optional-stable-key"
}
```

If a format has no configured route, DeepTutor returns
`openmaic_export_route_unconfigured` with HTTP 501. This is intentional: stored
OpenMAIC documents are not treated as PPTX/HTML/ZIP export artifacts.

## Local Demo Export

Before a deployed OpenMAIC export service exists, DeepTutor can run the same
course-runtime contract locally through the in-memory adapter:

```bash
cognispheretutor cognisphere course-demo "vLLM network troubleshooting"
```

The command creates one runnable course manifest, compiles it to OpenMAIC-style
stage/scenes, and writes real `course.html`, `course.pptx`, and
`course.maic.zip` files under `data/user/course_exports/`.
