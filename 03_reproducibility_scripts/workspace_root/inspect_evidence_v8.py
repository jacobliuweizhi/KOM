import sqlite3
from pathlib import Path

root = Path(r"C:\OAI研究项目\pythonProject1\KOM返修修改\投稿使用\KOM_Local_Clinical_Workbench_FINAL_202606")
db = root / "app" / "data" / "kom_workbench.sqlite"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row

domains = {
    "exercise": "exercise_rehabilitation",
    "nutrition": "nutrition_weight_management",
    "medication": "pharmacologic_or_injection",
    "orthopaedic": "surgery_or_escalation",
    "psychology": "psychology_behavior_selfmanagement",
}

sql = """
select EU_ID, Title, Evidence_Level, Agent_Database, year, source_link
from evidence_units
where lower(Agent_Database) like ?
order by
  case
    when Evidence_Level like 'L1%' then 1
    when Evidence_Level like 'L2%' then 2
    when Evidence_Level like 'L3%' then 3
    else 4
  end,
  cast(year as int) desc
limit 18
"""

for name, dom in domains.items():
    print("\nDOMAIN", name)
    for r in con.execute(sql, ("%" + dom + "%",)):
        print(r["EU_ID"], "|", r["Evidence_Level"], "|", r["year"], "|", r["Title"][:120])
