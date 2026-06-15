from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime
import os
import json
import pandas as pd
import openpyxl


ROOT = Path("C:/OAI" + "\u7814\u7a76\u9879\u76ee" + "/pythonProject1/" + "KOM" + "\u8fd4\u4fee\u4fee\u6539")
OUT = ROOT / "KOM_Submission_Audit_Package_202606"
ZIP_OUT = ROOT / "KOM_Submission_Audit_Package_202606.zip"


def read_csv(path: Path, nrows: int | None = None):
    for enc in ["utf-8-sig", "utf-8", "gbk", "latin1"]:
        try:
            return pd.read_csv(path, encoding=enc, nrows=nrows, low_memory=False)
        except Exception:
            pass
    return pd.DataFrame()


def write_csv(path: Path, rows):
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def main():
    cross = OUT / "04_crosscheck_reports"
    sim = OUT / "01_KOMSim_logs_and_time_definition"
    risk = OUT / "02_KOMRisk_reproducible_prediction_package"
    rag = OUT / "03_KOMRAG_query_level_evidence_mapping"
    status_path = OUT / "00_inventory" / "package_build_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))

    checklist_path = cross / "submission_readiness_checklist.csv"
    checklist = read_csv(checklist_path)
    missing = []
    for _, row in checklist.iterrows():
        if str(row.get("status", "")).upper() not in {"COMPLETE", "FOUND"}:
            missing.append({"module": row.get("item"), "missing_item": row.get("recommended_next_action"), "evidence": row.get("evidence")})

    wb_path = cross / "submission_audit_crosscheck.xlsx"
    if wb_path.exists():
        wb_path.unlink()

    def limited(path: Path, n=20000):
        df = read_csv(path, nrows=n)
        if path.exists():
            df.insert(0, "_source_csv", str(path))
            df.insert(1, "_note", f"Workbook view capped at first {n} rows; full CSV is available at source path.")
        return df

    with pd.ExcelWriter(wb_path, engine="openpyxl") as writer:
        pd.DataFrame([{"package": "KOM_Submission_Audit_Package_202606", "generated": datetime.now().isoformat(timespec="seconds"), "principle": "Real source files only; missing items remain marked missing.", "workbook_note": "Large tables are stored as full CSVs. This workbook contains summary or capped views for reviewer navigation."}]).to_excel(writer, sheet_name="README", index=False)
        limited(sim / "KOMSim_raw_log_inventory.csv", 20000).to_excel(writer, sheet_name="KOM-Sim log status", index=False)
        pd.DataFrame([{"raw_event_logs_found": status.get("komsim_raw_event_logs_found"), "task_level_rows": status.get("komsim_task_rows"), "time_summary_rows": status.get("komsim_time_summary_rows"), "physician_summary_rows": status.get("komsim_physician_summary_rows")}]).to_excel(writer, sheet_name="KOM-Sim time definition", index=False)
        limited(risk / "KOMRisk_file_inventory.csv", 20000).to_excel(writer, sheet_name="KOM-Risk files", index=False)
        read_csv(risk / "risk_model_metrics.csv").to_excel(writer, sheet_name="KOM-Risk metrics", index=False)
        limited(rag / "rag_query_set.csv", 20000).to_excel(writer, sheet_name="KOM-RAG query set", index=False)
        limited(rag / "guideline_anchor_mapping.csv", 20000).to_excel(writer, sheet_name="KOM-RAG evidence mapping", index=False)
        limited(rag / "rag_metric_by_query.csv", 20000).to_excel(writer, sheet_name="KOM-RAG query metrics", index=False)
        pd.DataFrame(missing).to_excel(writer, sheet_name="Missing items", index=False)
        checklist.to_excel(writer, sheet_name="Ready checklist", index=False)

    wb = openpyxl.load_workbook(wb_path, read_only=True)
    sheets = wb.sheetnames
    wb.close()
    audit_ok = bool(sheets)
    write_csv(cross / "workbook_audit.csv", [{"path": str(wb_path), "exists": wb_path.exists(), "size_bytes": wb_path.stat().st_size, "sheet_count": len(sheets), "sheets": "; ".join(sheets)}])
    (cross / "workbook_audit_result.md").write_text(f"workbook_audit exit {0 if audit_ok else 1}\n", encoding="utf-8")

    status["workbook_audit_exit"] = 0 if audit_ok else 1
    status["crosscheck_workbook_note"] = "Large tables are stored as full CSVs; workbook contains capped views for navigation."
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    if ZIP_OUT.exists():
        backup = ROOT / f"KOM_Submission_Audit_Package_202606_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        ZIP_OUT.rename(backup)
    with ZipFile(ZIP_OUT, "w", ZIP_DEFLATED) as z:
        for dirpath, _, filenames in os.walk(OUT):
            for fn in filenames:
                p = Path(dirpath) / fn
                z.write(p, p.relative_to(ROOT))
    status["zip_size_bytes"] = ZIP_OUT.stat().st_size
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
