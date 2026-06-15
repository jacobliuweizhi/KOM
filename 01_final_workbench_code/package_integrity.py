from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / "runtime" / "python" / "python.exe"
REPORT = ROOT / "validation" / "package_integrity_report.json"
PORT = int(os.environ.get("KOM_PORT", "8027"))
BASE = f"http://127.0.0.1:{PORT}"


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def fetch(path: str, retries: int = 3) -> tuple[bool, str]:
    last_error = ""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(BASE + path, timeout=5) as response:
                body = response.read(200000).decode("utf-8", errors="replace")
                return response.status == 200, body
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.4 * (attempt + 1))
    return False, last_error


def main() -> int:
    checks: list[dict] = []

    def add(name: str, passed: bool, detail: str):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    add("embedded_python_exists", PYTHON.exists(), rel(PYTHON))
    add("static_index_exists", (ROOT / "app" / "static" / "index.html").exists(), "app/static/index.html")
    add("server_entry_exists", (ROOT / "app" / "start_server.py").exists(), "app/start_server.py")
    add("start_script_exists", (ROOT / "Start_KOM_Workbench.bat").exists(), "Start_KOM_Workbench.bat")
    add("portable_start_script_exists", (ROOT / "Start_KOM_Workbench_Portable.bat").exists(), "Start_KOM_Workbench_Portable.bat")
    add("dockerfile_exists", (ROOT / "Dockerfile").exists(), "Dockerfile")
    add("render_blueprint_exists", (ROOT / "render.yaml").exists(), "render.yaml")
    add("github_web_deploy_readme_exists", (ROOT / "README_GITHUB_AND_WEB_DEPLOY.md").exists(), "README_GITHUB_AND_WEB_DEPLOY.md")
    add("github_actions_windows_validation_exists", (ROOT / ".github" / "workflows" / "windows-package-validation.yml").exists(), ".github/workflows/windows-package-validation.yml")

    started_here = False
    proc = None
    if not port_open(PORT):
        proc = subprocess.Popen(
            [str(PYTHON), str(ROOT / "app" / "start_server.py"), "--port", str(PORT)],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform.startswith("win") else 0,
        )
        started_here = True
        for _ in range(25):
            if port_open(PORT):
                break
            time.sleep(0.5)

    add("server_port_open", port_open(PORT), f"{BASE}")

    ok, body = fetch("/api/v9/validate")
    validation_status = ""
    if ok:
        try:
            parsed = json.loads(body)
            validation_status = parsed.get("data", parsed).get("status", "")
        except Exception:
            validation_status = "json_parse_failed"
    add("api_v9_validate_http_200", ok, body[:500])
    add("api_v9_validate_ready", validation_status == "KOM_ENGLISH_READY", validation_status)

    for path in ["/dashboard", "/rx", "/rag", "/api/routes", "/api/v10/evidence/units", "/api/v10/evidence/patient-fit?q=knee%20osteoarthritis%20NSAID%20exercise&domain=exercise_rehabilitation"]:
        ok, body = fetch(path)
        add(f"route_{path.replace('/', '_') or 'root'}", ok, body[:300])

    if started_here and proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    status = "PASS" if all(item["passed"] for item in checks) else "FAIL"
    report = {
        "status": status,
        "base_url": BASE,
        "requires_system_python": False,
        "embedded_python": rel(PYTHON),
        "checks": checks,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
