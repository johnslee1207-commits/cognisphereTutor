This directory is populated by `scripts/package_openmaic_runtime.py` during
release packaging.

The generated bundle must contain `server.js`, `.next/static`, optional
`public`, and `openmaic-runtime.json`. Tutor discovers that manifest and starts
OpenMAIC as a managed sidecar for ordinary local installs.
