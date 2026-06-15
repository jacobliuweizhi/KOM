from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SERVER_PATH = ROOT / "app" / "backend" / "server.py"


def main() -> int:
    spec = importlib.util.spec_from_file_location("kom_workbench_server", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load server module from {SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.validation_result()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "KOM_ENGLISH_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
