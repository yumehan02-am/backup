# -*- coding: utf-8 -*-
"""Compare external candidate rules with default rules on registered pages."""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path


def load_app_module(base_dir: Path):
    module_path = base_dir / "inventory_transfer_app_v2.py"
    spec = importlib.util.spec_from_file_location("inventory_transfer_app_v2_registered_test", module_path)
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
    v2_dir = root / "037在庫転記ツール_v2"
    app = load_app_module(v2_dir)
    db = app.AppDB(v2_dir / app.DB_NAME)
    helper = app.TransferWindow.__new__(app.TransferWindow)
    helper.db = db
    helper.base_dir = v2_dir
    helper.excel_rules()

    rows = db.conn.execute(
        """
        SELECT product_code, page_name, inventory_file_path, inventory_sheet_name, excel_start_col
        FROM product_transfer_pages
        WHERE COALESCE(inventory_file_path, '') <> ''
        ORDER BY product_code, page_order, id
        """
    ).fetchall()
    candidates = []
    for row in rows:
        path = Path(app.normalize_windows_path(row["inventory_file_path"]))
        if path.exists():
            candidates.append(row)
    random.seed(723)
    sample = candidates[:]
    random.shuffle(sample)
    sample = sample[:20]

    import win32com.client

    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = True
    excel.DisplayAlerts = False
    results = []
    try:
        for row in sample:
            path = Path(app.normalize_windows_path(row["inventory_file_path"]))
            result = {
                "product_code": row["product_code"],
                "page_name": row["page_name"],
                "path": str(path),
                "sheet": row["inventory_sheet_name"],
                "start_col": row["excel_start_col"] or "A",
            }
            workbook = None
            try:
                workbook = excel.Workbooks.Open(str(path), UpdateLinks=0, ReadOnly=True)
                worksheet = helper.resolve_excel_worksheet(workbook, row["inventory_sheet_name"])
                workbook.Activate()
                worksheet.Activate()
                start_col = row["excel_start_col"] or "A"
                external_candidate = helper.detect_write_candidate_cell(worksheet, excel, start_col)
                external_row = helper.adjust_candidate_after_red_marker(
                    worksheet,
                    external_candidate.row,
                    external_candidate.col,
                    external_candidate.island,
                )
                default_candidate = helper._default_detect_write_candidate_cell(worksheet, excel, start_col)
                default_row = helper._default_adjust_candidate_after_red_marker(
                    worksheet,
                    default_candidate.row,
                    default_candidate.col,
                    default_candidate.island,
                )
                result.update(
                    {
                        "external": cell_address(app, external_row, external_candidate.col),
                        "default": cell_address(app, default_row, default_candidate.col),
                        "matches_default": external_row == default_row and external_candidate.col == default_candidate.col,
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
    output_path = output_dir / "candidate_registered_pages_result.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = [row for row in results if row.get("status") != "ok" or not row.get("matches_default")]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"RESULT_FILE={output_path}")
    print(f"SUMMARY total={len(results)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
