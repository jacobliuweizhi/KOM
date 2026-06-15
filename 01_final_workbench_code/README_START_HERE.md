# KOM Knee Osteoarthritis Clinical Workbench

This folder is a self-contained local clinical workbench for knee osteoarthritis assessment and treatment planning. The interactive 20260615 release is bilateral: KOM-Profile, KOM-Rad and KOM-Risk retain left and right knees separately, and KOM-Treat uses side-specific evidence retrieval, MDT prescription generation, KOM-Safe audit negotiation, clinician-selectable KOM-Rx reporting and KOM-Score validation.

## 20260615 Bilateral Coupled Risk, Source-Enriched RAG, Evidence-Linked Rx and Web-Ready Updates

- Left and right knees each carry KL grade, pain NRS, WOMAC function, progression status, imaging findings and risk outputs.
- Dashboard layer buttons jump directly to KOM-Profile, KOM-RAG, KOM-MDT, KOM-Safe and KOM-Rx.
- KOM-Profile now uses four compact selectable patient cases, locked left/right KL display fields, smooth WOMAC/NRS/BMI sliders and saved profile configuration for downstream modules.
- KOM-Risk locks left and right KL grades from KOM-Profile. The Risk page only changes modifiable or follow-up scenario variables such as BMI, pain and WOMAC function. The local risk engine is now bilateral-coupled: changing one knee's pain or WOMAC function can influence both knee predictions through contralateral load and shared-burden terms.
- KOM-RAG evidence nodes and specialty-chain cards open floating Evidence Unit detail; the detail overlay closes by either the close button or backdrop click. The current local catalog contains 3267 Evidence Units and includes a targeted STEP 9 semaglutide obesity-and-knee-OA evidence unit.
- KOM-RAG full graph is now an interactive patient/query evidence network rather than a static image. Arbitrary catalog searches such as `OA`, `semaglutide`, `PRP`, `cycling` or `CBT` update the visible evidence neighborhood and catalog rows.
- KOM-RAG catalog rendering is paginated and has JSON export so the full database can be inspected without freezing the interface.
- Evidence Unit detail now extracts population fingerprint, sample size, result direction and quantitative-effect availability, and warns when exact effect size is absent from local metadata.
- KOM-RAG patient-fit retrieval uses a success rule: at least L1, L2 and L3 evidence with at least six unique Evidence Units after no more than three retrieval rounds.
- Treatment content includes explicit nutrition targets, named medication options with dose/frequency gates, sodium hyaluronate and PRP injection boundary options, CBT-informed psychology intervention steps, orthopedic referral-screen reasons and mandatory pre-referral screening.
- Exercise prescription now separates guideline-core content from meta-analysis/synthesis signals, RCT/modality signals and patient-fit safety modules such as stationary cycling, aquatic exercise and neuromotor/balance work.
- Each KOM-MDT specialty agent has quick prompts and a local dialogue API. The agent can identify itself, use the current patient profile, draft a specialty prescription and report safety gates without requiring a model API key.
- KOM-Safe now separates cross-specialty prescription compatibility gates from patient-data completeness gates. Negotiation events carry audit IDs, event IDs, input gate status and adoption rules.
- KOM-Rx includes a clinician-selectable prescription builder for medication, injection, exercise, nutrition, psychology/communication and orthopedic-boundary modules. Clicking modules edits the prescription draft; clicking `Confirm final KOM-Rx` saves the final prescription locally. Each selected item carries L1-L7 Evidence Unit support in the draft and final report.
- GitHub/web delivery files are included: `Start_KOM_Workbench_Portable.bat`, `Dockerfile`, `.dockerignore`, `render.yaml` and `README_GITHUB_AND_WEB_DEPLOY.md`.

## Quick Start

1. Extract the full folder.
2. Double-click `Start_KOM_Workbench_Portable.bat` for the most robust portable launch, or use `Start_KOM_Workbench.bat` for the fixed-port launcher.
3. The launcher starts the embedded local server and opens `http://127.0.0.1:8027/dashboard` after the validation API responds. If port 8027 is busy, the portable launcher tries 8067.
4. Double-click `Stop_KOM_Workbench.bat` when finished.

The package includes `runtime\python\python.exe` (Python 3.12, 64-bit); it does not require system Python and does not depend on the Windows Store Python alias.

For older Windows systems, first try `Start_KOM_Workbench_Portable.bat`. If the embedded Python runtime cannot start on that operating system, use the public web/Docker deployment path in `README_GITHUB_AND_WEB_DEPLOY.md`.

## GitHub and Public Web Deployment

- GitHub Release mode: upload the rebuilt `KOM_WB_V24.zip`; users download, extract and run `Start_KOM_Workbench_Portable.bat`.
- Public URL mode: push the extracted folder to a repository and deploy the included `Dockerfile` on Render, Railway, Fly.io or a VPS. The server automatically uses the platform `PORT` variable.
- GitHub Pages alone is not sufficient for the full dynamic workbench because KOM-Risk, KOM-RAG, Settings, profile persistence and validation require Python API routes and the local SQLite evidence database.
- For public web deployments, set `KOM_PUBLIC_DEMO=1`. In that mode the backend does not persist private API keys to shared server disk. Use server-side environment variables for controlled private deployments.

## Validation

Browser validation endpoint:

```text
http://127.0.0.1:8027/api/v9/validate
```

One-click validation:

```bat
Run_Validation.bat
```

Full package integrity check:

```bat
runtime\python\python.exe package_integrity.py
```

A passing package reports `KOM_ENGLISH_READY` with bilateral/deep-treatment checks for the application validation and `PASS` for the package integrity check. Reports are written under `validation\`.

## Model API

No private API key is bundled. If model-based refinement is needed, configure an OpenAI-compatible endpoint in the Settings page. Without an API key, the deterministic local pathway remains available.

## Clinical Boundary

This system is for medical research and clinician decision-support validation. It does not replace licensed clinician judgment. Medication, injection, surgery, exercise, nutrition and psychology recommendations require clinician review.
