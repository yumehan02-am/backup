from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "production"
DEFAULT_IMAGE_BASE_URL = "https://image.rakuten.co.jp/u-b-yumehan/cabinet/contents/"
DEFAULT_PAGE_NUMBERS = ["006", "007", "008", "009"]
MAIN_TITLE_MAX_CHARS = 40
SUBTITLE_MAX_CHARS = 20


def clean_heading(line: str) -> str:
    return re.sub(r"^\s{0,3}#{1,6}\s*", "", line).strip()


def clean_section_title(text: str) -> str:
    return re.sub(r"^\s*\d+\.\s*", "", text).strip()


def fit_title(text: str, max_chars: int) -> tuple[str, str]:
    value = text.strip()
    if len(value) <= max_chars:
        return value, ""
    for delimiter in ["｜", "|", "：", ":", "、", "。"]:
        before = value.split(delimiter, 1)[0].strip()
        if 6 <= len(before) <= max_chars:
            return before, f"タイトルを{max_chars}文字以内に短縮: 元={value}"
    shortened = value[:max_chars].rstrip("｜|、。,. ")
    return shortened, f"タイトルを{max_chars}文字以内に短縮: 元={value}"


def image_url_from_path(image_path: str, base_url: str) -> str:
    filename = Path(image_path.strip()).name
    return base_url.rstrip("/") + "/" + filename


def int_value(value: str) -> int | None:
    value = str(value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def is_article_banner(part: dict[str, str]) -> bool:
    source = part.get("file_or_source", "")
    return (
        part.get("part_type") == "banner"
        and "_title." not in source
        and "_points." not in source
    )


def is_points_image(part: dict[str, str]) -> bool:
    source = part.get("file_or_source", "")
    return part.get("part_type") == "points_image" or "_points." in source


def section_no(part: dict[str, str]) -> int | None:
    for key in ["after_section", "section", "target_section"]:
        value = int_value(part.get(key, ""))
        if value is not None:
            return value
    return None


def placement(part: dict[str, str]) -> str:
    value = part.get("placement", "").strip()
    if value:
        return value
    if part.get("part_type") == "accent_image":
        return "after_body"
    return "before_body"


def extract_image_path(line: str) -> str:
    match = re.search(r"!\[[^\]]*\]\(([^)]+)\)", line)
    if match:
        return match.group(1)
    return ""


def append_text_block(rows: list[dict[str, str]], buffer: list[str], source_label: str) -> None:
    text = "\n\n".join(part.strip() for part in buffer if part.strip()).strip()
    buffer.clear()
    if not text:
        return
    rows.append(
        {
            "ブロック種別": "本文",
            "貼り付け内容": text,
            "元データ": source_label,
            "文字数": str(len(text)),
            "警告": "",
        }
    )


def markdown_sections(md_path: Path) -> dict[str, str]:
    sections: dict[str, str] = {}
    lead: list[str] = []
    current_key = "lead"
    current_lines: list[str] = []
    seen_first_section = False

    def flush() -> None:
        nonlocal current_lines
        text = "\n\n".join(part.strip() for part in current_lines if part.strip()).strip()
        if text:
            sections[current_key] = text
        current_lines = []

    for raw_line in md_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# "):
            sections["title"] = clean_heading(line)
            continue
        if line.startswith("## "):
            if seen_first_section:
                flush()
            else:
                lead_text = "\n\n".join(lead).strip()
                if lead_text:
                    sections["lead"] = lead_text
                seen_first_section = True
            heading = clean_heading(line)
            if "まとめ" in heading:
                current_key = "まとめ"
            else:
                match = re.match(r"^(\d+)", heading)
                current_key = match.group(1) if match else heading
            current_lines = [heading]
            continue
        if seen_first_section:
            current_lines.append(line)
        else:
            lead.append(line)

    if seen_first_section:
        flush()
    elif lead:
        sections["lead"] = "\n\n".join(lead).strip()
    return sections


def markdown_article_parts(md_path: Path) -> dict[str, object]:
    title = ""
    lead: list[str] = []
    sections: list[dict[str, str]] = []
    current_title = ""
    current_body: list[str] = []

    def flush_section() -> None:
        nonlocal current_title, current_body
        if not current_title:
            return
        sections.append(
            {
                "title": current_title,
                "body": "\n\n".join(part for part in current_body if part).strip(),
            }
        )
        current_title = ""
        current_body = []

    for raw_line in md_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# "):
            title = clean_heading(line)
            continue
        if line.startswith("## "):
            flush_section()
            current_title = clean_heading(line)
            continue
        if current_title:
            current_body.append(line)
        else:
            lead.append(line)

    flush_section()
    return {
        "title": title,
        "lead": "\n\n".join(lead).strip(),
        "sections": sections,
    }


def text_keys_from_note(note: str) -> list[str]:
    if "リード文から1章" in note:
        return ["lead", "1"]
    match = re.search(r"(\d+)章から(\d+)章", note)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        return [str(number) for number in range(start, end + 1)]
    match = re.search(r"(\d+)章からまとめ", note)
    if match:
        return [str(number) for number in range(int(match.group(1)), 99)] + ["まとめ"]
    if "まとめ" in note:
        return ["まとめ"]
    return ["lead"]


def text_from_plan_note(sections: dict[str, str], note: str) -> str:
    keys = text_keys_from_note(note)
    values: list[str] = []
    for key in keys:
        if key == "まとめ":
            if key in sections:
                values.append(sections[key])
            continue
        if key.isdigit() and int(key) >= 10:
            continue
        if key in sections:
            values.append(sections[key])
    return "\n\n".join(values).strip()


def row_for_part(part: dict[str, str], sections: dict[str, str], base_url: str) -> dict[str, str] | None:
    part_type = part.get("part_type", "").strip()
    source = part.get("file_or_source", "").strip()
    note = part.get("note", "").strip()

    if part_type in {"thumbnail", "banner"}:
        return {
            "ブロック種別": "画像" if part_type == "banner" else "サムネイル",
            "貼り付け内容": image_url_from_path(source, base_url),
            "元データ": source,
            "文字数": "",
            "警告": note,
        }
    if part_type == "video":
        return {
            "ブロック種別": "動画",
            "貼り付け内容": source,
            "元データ": source,
            "文字数": "",
            "警告": note,
        }
    if part_type == "product_parts":
        return {
            "ブロック種別": "商品パーツ",
            "貼り付け内容": source,
            "元データ": source,
            "文字数": "",
            "警告": note,
        }
    if part_type == "text":
        text = text_from_plan_note(sections, note)
        if not text:
            text = "\n\n".join(
                value for key, value in sections.items() if key != "title"
            ).strip()
        return {
            "ブロック種別": "本文",
            "貼り付け内容": "\n" + text,
            "元データ": source,
            "文字数": str(len(text)),
            "警告": note,
        }
    return None


def product_ids_text(page_dir: Path) -> str:
    product_path = page_dir / "product_ids.csv"
    if not product_path.exists():
        return ""
    values: list[str] = []
    with product_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_id = row.get("product_id", "").strip()
            role = row.get("role", "").strip()
            note = row.get("note", "").strip()
            if product_id:
                suffix = f" / {role}" if role else ""
                detail = f" / {note}" if note else ""
                values.append(f"{product_id}{suffix}{detail}")
    return "\n".join(values)


def product_id_values(page_dir: Path) -> list[str]:
    product_path = page_dir / "product_ids.csv"
    if not product_path.exists():
        return []
    values: list[str] = []
    with product_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_id = row.get("product_id", "").strip()
            if product_id:
                values.append(product_id)
    return values


def page_structure_to_paste_rows(page_dir: Path, base_url: str) -> list[dict[str, str]] | None:
    plan_path = page_dir / "data" / "rakuten_parts_plan.csv"
    md_path = page_dir / "page_copy.md"
    if not plan_path.exists():
        return None

    article = markdown_article_parts(md_path)
    rows: list[dict[str, str]] = []

    with plan_path.open("r", encoding="utf-8-sig", newline="") as f:
        parts = list(csv.DictReader(f))

    title_image = next((p for p in parts if p.get("part_type") == "banner" and "_title." in p.get("file_or_source", "")), None)
    video = next((p for p in parts if p.get("part_type") == "video"), None)
    product_part = next((p for p in parts if p.get("part_type") == "product_parts"), None)
    section_banners = [
        p
        for p in parts
        if is_article_banner(p) and section_no(p) is None
    ]
    positioned_parts = [
        p
        for p in parts
        if not is_points_image(p)
        and p.get("part_type") in {"banner", "accent_image"}
        and section_no(p) is not None
    ]

    if title_image:
        rows.append(
            {
                "ブロック種別": "画像",
                "貼り付け内容": image_url_from_path(title_image["file_or_source"], base_url),
                "元データ": title_image["file_or_source"],
                "文字数": "",
                "警告": "タイトル画像",
            }
        )

    main_title, warning = fit_title(str(article.get("title", "")), MAIN_TITLE_MAX_CHARS)
    rows.append(
        {
            "ブロック種別": "メインタイトル",
            "貼り付け内容": main_title,
            "元データ": str(article.get("title", "")),
            "文字数": str(len(main_title)),
            "警告": warning,
        }
    )

    if video:
        rows.append(
            {
                "ブロック種別": "動画",
                "貼り付け内容": video["file_or_source"],
                "元データ": video["file_or_source"],
                "文字数": "",
                "警告": "タイトル直下の動く目次CM",
            }
        )

    lead = str(article.get("lead", "")).strip()
    if lead:
        rows.append(
            {
                "ブロック種別": "動画下本文",
                "貼り付け内容": "\n" + lead,
                "元データ": "page_copy.md#lead",
                "文字数": str(len(lead)),
                "警告": "本文先頭に余白用改行あり",
            }
        )

    for index, section in enumerate(article.get("sections", []), 1):
        section_title = clean_section_title(str(section.get("title", "")))
        body = str(section.get("body", "")).strip()
        small_title, small_warning = fit_title(section_title, SUBTITLE_MAX_CHARS)
        rows.append(
            {
                "ブロック種別": "小タイトル",
                "貼り付け内容": small_title,
                "元データ": section_title,
                "文字数": str(len(small_title)),
                "警告": small_warning,
            }
        )
        before_body_parts = [
            p
            for p in positioned_parts
            if section_no(p) == index and placement(p) == "before_body"
        ]
        if not before_body_parts and index <= len(section_banners):
            before_body_parts = [section_banners[index - 1]]
        for banner in before_body_parts:
            rows.append(
                {
                    "ブロック種別": "画像",
                    "貼り付け内容": image_url_from_path(banner["file_or_source"], base_url),
                    "元データ": banner["file_or_source"],
                    "文字数": "",
                    "警告": banner.get("note", ""),
                }
            )
        if body:
            rows.append(
                {
                    "ブロック種別": "本文",
                    "貼り付け内容": "\n" + body,
                    "元データ": f"page_copy.md#{index}",
                    "文字数": str(len(body)),
                    "警告": "本文先頭に余白用改行あり",
                }
            )
        for accent in [
            p
            for p in positioned_parts
            if section_no(p) == index and placement(p) == "after_body"
        ]:
            rows.append(
                {
                    "ブロック種別": "画像",
                    "貼り付け内容": image_url_from_path(accent["file_or_source"], base_url),
                    "元データ": accent["file_or_source"],
                    "文字数": "",
                    "警告": accent.get("note", ""),
                }
            )

    if product_part:
        product_ids = product_id_values(page_dir)
        if product_ids:
            for product_id in product_ids:
                rows.append(
                    {
                        "ブロック種別": "関連商品",
                        "貼り付け内容": product_id,
                        "元データ": product_part["file_or_source"],
                        "文字数": "",
                        "警告": "商品IDが必要なパーツ。1商品ID=1行",
                    }
                )
        else:
            rows.append(
                {
                    "ブロック種別": "関連商品",
                    "貼り付け内容": product_part["file_or_source"],
                    "元データ": product_part["file_or_source"],
                    "文字数": "",
                    "警告": "product_ids.csvに商品IDなし",
                }
            )

    for index, row in enumerate(rows, 1):
        row["順番"] = str(index)
    return rows


def parts_plan_to_paste_rows(page_dir: Path, base_url: str) -> list[dict[str, str]] | None:
    plan_path = page_dir / "data" / "rakuten_parts_plan.csv"
    md_path = page_dir / "page_copy.md"
    if not plan_path.exists():
        return None

    sections = markdown_sections(md_path)
    rows: list[dict[str, str]] = []
    with plan_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for part in reader:
            row = row_for_part(part, sections, base_url)
            if row:
                rows.append(row)

    for index, row in enumerate(rows, 1):
        row["順番"] = str(index)
    return rows


def markdown_to_paste_rows(md_path: Path, base_url: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    text_buffer: list[str] = []
    source_parts: list[str] = []

    for raw_line in md_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        image_path = extract_image_path(line)
        if image_path:
            append_text_block(rows, text_buffer, "\n".join(source_parts))
            source_parts.clear()
            rows.append(
                {
                    "ブロック種別": "画像",
                    "貼り付け内容": image_url_from_path(image_path, base_url),
                    "元データ": line.strip(),
                    "文字数": "",
                    "警告": "",
                }
            )
            continue

        if re.match(r"^\s{0,3}#{1,6}\s+", line):
            append_text_block(rows, text_buffer, "\n".join(source_parts))
            source_parts.clear()
            title, warning = fit_title(clean_heading(line), SUBTITLE_MAX_CHARS)
            rows.append(
                {
                    "ブロック種別": "タイトル",
                    "貼り付け内容": title,
                    "元データ": line.strip(),
                    "文字数": str(len(title)),
                    "警告": warning,
                }
            )
            continue

        if line.strip():
            text_buffer.append(line.strip())
            source_parts.append(line.strip())
        elif text_buffer:
            source_parts.append("")

    append_text_block(rows, text_buffer, "\n".join(source_parts))
    for index, row in enumerate(rows, 1):
        row["順番"] = str(index)
    return rows


def page_dirs(page_numbers: list[str]) -> list[Path]:
    result: list[Path] = []
    for page_no in page_numbers:
        matches = sorted(path for path in PRODUCTION.glob(f"{page_no}_*") if path.is_dir())
        if not matches:
            raise FileNotFoundError(f"production配下に {page_no}_ で始まるページフォルダが見つかりません。")
        result.append(matches[0] / "納品用")
    return result


def export_page(page_dir: Path, base_url: str) -> Path:
    md_path = page_dir / "page_copy.md"
    if not md_path.exists():
        raise FileNotFoundError(f"{md_path} が見つかりません。")
    rows = page_structure_to_paste_rows(page_dir, base_url)
    if rows is None:
        rows = markdown_to_paste_rows(md_path, base_url)
    out_path = page_dir / "page_paste_blocks.tsv"
    fieldnames = ["順番", "ブロック種別", "貼り付け内容", "元データ", "文字数", "警告"]
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, dialect="excel-tab")
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="page_copy.mdをRMSコピペ用TSVへ変換します。")
    parser.add_argument("pages", nargs="*", default=DEFAULT_PAGE_NUMBERS, help="出力するページ番号。例: 006 007")
    parser.add_argument("--image-base-url", default=DEFAULT_IMAGE_BASE_URL, help="画像URLのベースパス")
    args = parser.parse_args()

    for page_dir in page_dirs(args.pages):
        out_path = export_page(page_dir, args.image_base_url)
        print(out_path)


if __name__ == "__main__":
    main()
