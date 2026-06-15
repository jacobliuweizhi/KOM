#!/usr/bin/env python
"""Template for exporting KOM-Risk endpoint-specific longitudinal predictions.

This template intentionally does not mix OAKNet imaging predictions with
KOM-Risk longitudinal predictions.
"""
from __future__ import annotations

import argparse
from pathlib import Path

OUTPUT_COLUMNS = [
    "sample_id", "person_id", "knee_id", "side", "endpoint", "split", "fold",
    "event_time", "censor_time", "event_observed", "y_true",
    "predicted_probability", "risk_score", "predicted_class", "model_name",
    "algorithm", "feature_set",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_root", required=True)
    parser.add_argument("--model_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--endpoint", required=True, choices=[
        "structural_progression", "tkr_knee_surgery", "symptom_function_worsening", "all"
    ])
    parser.add_argument("--split_csv", required=True)
    parser.add_argument("--feature_csv", required=True)
    parser.add_argument("--label_csv", required=True)
    parser.add_argument("--model_file", required=True)
    args = parser.parse_args()

    model_file = Path(args.model_file)
    if not model_file.exists():
        raise FileNotFoundError(
            "Model file not found. Please provide trained KOM-Risk model artifact "
            "or rerun model training/export."
        )

    raise NotImplementedError(
        "Load the trained KOM-Risk model artifact, join split/features/labels by "
        "sample_id or person_id/knee_id, compute predicted_probability or risk_score, "
        "and write OUTPUT_COLUMNS. Do not mix OAKNet imaging predictions with "
        "KOM-Risk longitudinal predictions."
    )


if __name__ == "__main__":
    main()
