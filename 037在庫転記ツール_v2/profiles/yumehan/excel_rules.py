"""Excel transfer rules for the Yumehan profile.

Company-specific Excel judgement rules should be changed here, not in the
common GUI/database layer.
"""

import importlib.util
from pathlib import Path

profile_id = "yumehan"

_candidate_rules = None


def _load_sibling_module(module_name: str):
    module_path = Path(__file__).with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(f"yumehan_{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"プロファイルモジュールを読み込めません: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate_rules():
    global _candidate_rules
    if _candidate_rules is None:
        _candidate_rules = _load_sibling_module("excel_candidate_rules")
    return _candidate_rules


def detect_write_candidate_cell(helper, worksheet, excel, excel_start_col: str = ""):
    return candidate_rules().detect_write_candidate_cell(helper, worksheet, excel, excel_start_col)


def adjust_candidate_after_red_marker(helper, worksheet, row: int, col: int, island):
    return helper._default_adjust_candidate_after_red_marker(worksheet, row, col, island)


def ensure_excel_row_is_writable(helper, worksheet, row: int, start_col: int, roles):
    return helper._default_ensure_excel_row_is_writable(worksheet, row, start_col, roles)


def infer_copy_rule_from_candidate(helper, candidate, product_tasks):
    return helper._default_infer_copy_rule_from_candidate(candidate, product_tasks)


def extend_inventory_island_on_sheet(helper, worksheet, excel, excel_start_col: str):
    return helper._default_extend_inventory_island_on_sheet(worksheet, excel, excel_start_col)


def find_stock_remaining_row(helper, worksheet, start_row: int, start_col: int, labels: list[str]) -> int:
    return helper._default_find_stock_remaining_row(worksheet, start_row, start_col, labels)
