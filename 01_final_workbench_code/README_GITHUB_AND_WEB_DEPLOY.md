# KOM Workbench GitHub and Web Deployment

This package supports two distribution modes.

## 1. GitHub Release zip for Windows users

Use this mode when reviewers or collaborators need a complete local copy.

1. Upload `KOM_WB_V24.zip` to a GitHub Release.
2. The user downloads the zip, extracts the full folder and double-clicks `Start_KOM_Workbench_Portable.bat`.
3. The workbench opens at `http://127.0.0.1:8027/dashboard`. If port 8027 is busy, the portable launcher tries 8067.
4. The package uses `runtime\python\python.exe`; system Python is not required.

Compatibility boundary: this local package includes a 64-bit Python 3.12 embedded runtime and is designed for modern 64-bit Windows. Very old Windows builds can fail to start current embedded Python runtimes; in that case, use the web/Docker deployment below.

## 2. Public web URL

GitHub Pages is not enough for the full workbench because KOM-Risk, KOM-RAG, Settings, profile persistence and validation are backend API routes backed by Python and SQLite. Use a Docker web service instead.

Recommended path:

1. Push the extracted folder to a GitHub repository.
2. On Render, Railway, Fly.io or a VPS, create a Docker web service from that repository.
3. Use the included `Dockerfile`. The server reads the platform `PORT` variable automatically.
4. Set `KOM_PUBLIC_DEMO=1` for public deployments.
5. Use `/api/v9/validate` as the health-check path.
6. Open the deployed `/dashboard` URL.

Local Docker test:

```bash
docker build -t kom-clinical-workbench .
docker run --rm -p 8027:8027 -e KOM_HOST=0.0.0.0 -e KOM_PUBLIC_DEMO=1 kom-clinical-workbench
```

Then open:

```text
http://127.0.0.1:8027/dashboard
```

## API-key privacy for public deployments

Do not write a shared private API key through the web Settings page on a public server. In `KOM_PUBLIC_DEMO=1`, the backend intentionally refuses to persist private keys to disk. For a controlled private deployment, set `OPENAI_API_KEY` or `XIAOAI_API_KEY` as a server-side environment variable.

## What should be hosted on GitHub

Keep these files in the repository:

- `app/`
- `tools/`
- `.github/workflows/windows-package-validation.yml`
- `Dockerfile`
- `.dockerignore`
- `render.yaml`
- `README_START_HERE.md`
- `README_GITHUB_AND_WEB_DEPLOY.md`
- `package_integrity.py`
- `PACKAGE_MANIFEST.json`

Do not commit local private files:

- `app/config/llm_config.local.json`
- `app/data/current_profile_config.json`
- `app/data/final_rx_prescription.json`

For Release downloads, upload the rebuilt zip separately rather than committing the zip into the repository.
