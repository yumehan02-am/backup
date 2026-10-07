# -*- coding: utf-8 -*-
"""Smoke-test Yumehan write-candidate detection against known Excel cases.

This script opens workbooks read-only through Excel COM, so it is intended for
local manual/agent verification, not normal application startup.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_app_module(base_dir: Path):
    module_path = base_dir / "inventory_transfer_app_v2.py"
    spec = importlib.util.spec_from_file_location("inventory_transfer_app_v2_test_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module load failed: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def cell_address(app, row: int, col: int) -> str:
    return f"{app.excel_index_to_column(int(col))}{int(row)}"


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    current_dir = root / "037在庫転記ツール"
    v2_dir = root / "037在庫転記ツール_v2"
    app = load_app_module(v2_dir)
    db = app.AppDB(v2_dir / app.DB_NAME)
    helper = app.TransferWindow.__new__(app.TransferWindow)
    helper.db = db
    helper.base_dir = v2_dir
    rules = helper.excel_rules()

    cases = [
        {
            "name": "80スムースカップ付ラン型",
            "path": current_dir / "在庫" / "夢販流通" / "西川合繊" / "80スムースカップ付ラン型.xlsx",
            "start_col": "A",
            "expected": "A241",
        },
        {
            "name": "ほっそり見えカバーアップ水着",
            "path": current_dir / "在庫" / "夢販流通" / "クライム" / "水着" / "ほっそり見えカバーアップ水着.xlsx",
            "start_col": "A",
            "expected": "A216",
        },
        {
            "name": "【NEW】フィットブラ付きスクエアネック フレンチ",
            "path": current_dir / "在庫" / "夢販流通" / "クライム" / "【NEW】フィットブラ付きスクエアネック　フレンチ.xlsx",
            "start_col": "A",
            "expected": "A630",
        },
        {
            "name": "冷感ストール",
            "path": current_dir / "在庫" / "夢販流通" / "成願" / "冷感ストール.xlsx",
            "start_col": "B",
            "expected": "B450",
        },
        {
            "name": "150CC綿変わり織りショーツ",
            "path": current_dir / "在庫" / "夢販流通" / "西川合繊" / "150CC綿変わり織りショーツ.xlsx",
            "start_col": "A",
            "expected": "A749",
        },
        {
            "name": "キルトノーマル、キルト 一分丈",
            "path": current_dir / "在庫" / "夢販流通" / "西川合繊" / "キルトノーマル、キルト 一分丈.xlsx",
            "sheet": "キルトノーマル丈",
            "start_col": "A",
            "expected": "A1026",
        },
        {
            "name": "【NEW】吸水パッドレースショーツ",
            "path": current_dir / "在庫" / "夢販流通" / "川本産業㈱（ニシキ）" / "【NEW】吸水パッドレースショーツ.xlsx",
            "start_col": "A",
            "expected": "A1959",
        },
        {
            "name": "渡嘉 吸水パッド",
            "path": current_dir / "在庫" / "夢販流通" / "渡嘉" / "吸水パッド.xlsx",
            "start_col": "B",
            "expected": "B355",
            "note": "過去に在庫表側の修正対象と判断した事例",
        },
        {
            "name": "シアーリブハイネック長袖インナー",
            "path": current_dir / "在庫" / "夢販流通" / "クライム" / "シアーリブハイネック長袖インナー.xlsx",
            "start_col": "A",
        },
        {
            "name": "New細っそり見えスタイルカバーアップ水着23001",
            "path": current_dir / "在庫" / "夢販流通" / "上杉　水着" / "New細っそり見えスタイルカバーアップ水着23001.xlsx",
            "start_col": "A",
        },
    ]

    import win32com.client

    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = True
    excel.DisplayAlerts = False
    results = []
    try:
        for case in cases:
            path = Path(case["path"])
            result = {
                "name": case["name"],
                "path": str(path),
                "exists": path.exists(),
                "expected": case.get("expected", ""),
                "note": case.get("note", ""),
            }
            if not path.exists():
                result["status"] = "missing"
                results.append(result)
                continue
            workbook = None
            try:
                workbook = excel.Workbooks.Open(str(path), UpdateLinks=0, ReadOnly=True)
                sheet_name = case.get("sheet", "")
                if sheet_name:
                    worksheet = workbook.Worksheets(sheet_name)
                else:
                    worksheet = workbook.ActiveSheet
                workbook.Activate()
                worksheet.Activate()
                start_col = case.get("start_col", "A")

                external_candidate = helper.detect_write_candidate_cell(worksheet, excel, start_col)
                external_row = helper.adjust_candidate_after_red_marker(
                    worksheet,
                    external_candidate.row,
                    external_candidate.col,
                    external_candidate.island,
                )
                external_address = cell_address(app, external_row, external_candidate.col)

                default_candidate = helper._default_detect_write_candidate_cell(worksheet, excel, start_col)
                default_row = helper._default_adjust_candidate_after_red_marker(
                    worksheet,
                    default_candidate.row,
                    default_candidate.col,
                    default_candidate.island,
                )
                default_address = cell_address(app, default_row, default_candidate.col)

                result.update(
                    {
                        "external": external_address,
                        "default": default_address,
                        "matches_default": external_address == default_address,
                        "matches_expected": (not case.get("expected")) or external_address == case.get("expected"),
                        "status": "ok",
                    }
                )
            except Exception as exc:
                result["status"] = "error"
                result["error"] = str(exc)
            finally:
                if workbook is not None:
                    try:
                        workbook.Close(SaveChanges=False)
                    except Exception as exc:
                        result["close_warning"] = str(exc)
            results.append(result)
    finally:
        try:
            excel.DisplayAlerts = True
        except Exception:
            pass
        try:
            excel.Quit()
        except Exception:
            pass
        db.conn.close()

    output_dir = v2_dir / "output" / "test"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "candidate_cases_result.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = [
        row
        for row in results
        if row.get("status") != "ok" or not row.get("matches_default") or not row.get("matches_expected", True)
    ]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"RESULT_FILE={output_path}")
    print(f"SUMMARY total={len(results)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
