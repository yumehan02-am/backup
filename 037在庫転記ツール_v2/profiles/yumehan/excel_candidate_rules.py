"""Write-candidate detection for the Yumehan Excel profile.

This module owns the profile-specific decision flow for choosing where the
next transfer row should be written. Low-level helpers are still reused from
the common app during the first migration step.
"""

profile_id = "yumehan"


def _app_global(helper, name: str):
    return helper._default_detect_write_candidate_cell.__globals__[name]


def detect_write_candidate_cell(helper, worksheet, excel, excel_start_col: str = ""):
    WriteCandidate = _app_global(helper, "WriteCandidate")
    excel_column_to_index = _app_global(helper, "excel_column_to_index")

    used = worksheet.UsedRange
    used_start_row = used.Row
    used_start_col = used.Column
    used_end_row = used_start_row + used.Rows.Count - 1
    used_end_col = used_start_col + used.Columns.Count - 1

    if excel_start_col:
        helper.scroll_excel_to_start_col(excel, excel_start_col)
    visible = excel.ActiveWindow.VisibleRange
    visible_start_row = visible.Row
    visible_end_row = visible.Row + visible.Rows.Count - 1
    visible_end_col = visible.Column + visible.Columns.Count - 1
    target_col = excel_column_to_index(excel_start_col, visible.Column) if excel_start_col else visible.Column

    start_row = max(used_start_row, visible_start_row - 40)
    end_row = min(used_end_row, visible_end_row + 80)
    start_col = max(used_start_col, target_col)
    end_col = min(used_end_col, max(visible_end_col, target_col + 24, 20))
    values, formulas = helper.range_values_and_formulas(worksheet, start_row, start_col, end_row, end_col)
    visible_values = values
    visible_formulas = formulas
    visible_range_start_row = start_row
    visible_candidate = helper.detect_left_island_candidate_in_range(
        values,
        formulas,
        start_row,
        start_col,
        target_col,
        require_lower_context=True,
    )

    upper_blocks, bottom_blocks = helper.write_candidate_search_blocks(used_start_row, used_end_row, visible_start_row)
    blank_lower_candidate = None
    for block_start, block_end in bottom_blocks:
        values, formulas = helper.range_values_and_formulas(worksheet, block_start, start_col, block_end, end_col)
        candidate = helper.detect_left_island_candidate_in_range(values, formulas, block_start, start_col, target_col)
        if candidate:
            if visible_candidate and visible_candidate.row > candidate.row:
                return visible_candidate
            if candidate.island and not helper.island_has_real_shipment_rows(values, formulas, block_start, start_col, candidate.island):
                if blank_lower_candidate is None:
                    blank_lower_candidate = candidate
                continue
            if (
                blank_lower_candidate
                and candidate.row < blank_lower_candidate.row
                and block_start < blank_lower_candidate.start_row - 260
            ):
                continue
            return candidate

    if visible_candidate:
        return visible_candidate
    if blank_lower_candidate:
        return blank_lower_candidate

    for block_start, block_end in upper_blocks:
        values, formulas = helper.range_values_and_formulas(worksheet, block_start, start_col, block_end, end_col)
        candidate = helper.detect_left_island_candidate_in_range(values, formulas, block_start, start_col, target_col)
        if candidate:
            return candidate

    candidate = helper.detect_candidate_from_totals(visible_values, visible_formulas, visible_range_start_row, start_col)
    if candidate:
        end_col_for_candidate = start_col + len(visible_values[0]) - 1 if visible_values else start_col
        if helper.is_writable_candidate_row(
            visible_values,
            visible_formulas,
            visible_range_start_row,
            candidate[0],
            candidate[1],
            start_col,
            end_col_for_candidate,
        ):
            return WriteCandidate(candidate[0], candidate[1], visible_range_start_row, start_col, visible_values, visible_formulas, None)

    raise RuntimeError("表示範囲周辺で書き込み候補を検出できませんでした。手動で開始セルを選択してください。")
