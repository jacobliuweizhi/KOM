from __future__ import annotations
import json, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "app" / "data" / "kom_workbench.sqlite"

def get_case(case_id: str = "OAI_SHOWCASE_CASE_LOCKED_001") -> dict | None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT raw_json FROM cases WHERE case_id=?", (case_id,)).fetchone()
    con.close()
    return json.loads(row["raw_json"]) if row else None
