"""Export committed METHOD.md as a precise Google Sheets batchUpdate payload."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from method_policy import metadata, sheet_rows


def build_requests(sheet_id, revision):
    if not revision["method_committed"] or not revision["method_commit"]:
        raise ValueError("Commit METHOD.md before generating an authoritative mirror")
    requests = []
    for row, label, value in sheet_rows():
        requests.append({"updateCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": row-1, "endRowIndex": row,
                      "startColumnIndex": 0, "endColumnIndex": 2},
            "rows": [{"values": [{"userEnteredValue": {"stringValue": label}},
                                  {"userEnteredValue": {"stringValue": value}}]}],
            "fields": "userEnteredValue",
        }})
    provenance = [
        ["Method source", revision["method_source"]],
        ["Method revision", revision["method_commit"]],
        ["Method SHA-256", revision["method_sha256"]],
    ]
    requests.append({"updateCells": {
        "range": {"sheetId": sheet_id, "startRowIndex": 53, "endRowIndex": 56,
                  "startColumnIndex": 0, "endColumnIndex": 2},
        "rows": [{"values": [{"userEnteredValue": {"stringValue": v}} for v in row]}
                 for row in provenance],
        "fields": "userEnteredValue",
    }})
    return requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    workbook = os.environ.get("BBB_SPREADSHEET_ID", "")
    tab = os.environ.get("BBB_METHOD_SHEET_ID", "")
    if not workbook or not tab.isdigit():
        parser.error("Set the existing BBB_SPREADSHEET_ID and numeric BBB_METHOD_SHEET_ID privately")
    result = {"spreadsheet_id": workbook, "requests": build_requests(int(tab), metadata())}
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
