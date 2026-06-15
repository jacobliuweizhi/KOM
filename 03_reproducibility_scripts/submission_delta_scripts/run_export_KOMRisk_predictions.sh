#!/usr/bin/env bash
python export_KOMRisk_predictions_template.py --data_root "$1" --model_dir "$2" --output_dir "$3" --endpoint all --split_csv "$4" --feature_csv "$5" --label_csv "$6" --model_file "$7"
