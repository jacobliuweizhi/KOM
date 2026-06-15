#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
DEMO_FILE="$PWD/KOM_Reviewer_Demo_Single_File.html"
if [ -f "$DEMO_FILE" ]; then
  echo "Opening KOM Reviewer Demo single-file version..."
  if command -v open >/dev/null 2>&1; then
    open "$DEMO_FILE"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$DEMO_FILE"
  else
    echo "Open this file manually: $DEMO_FILE"
  fi
else
  echo "Missing KOM_Reviewer_Demo_Single_File.html"
  exit 1
fi
