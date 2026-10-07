from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "production"


@dataclass
class ImageRecord:
    page: str
    scope: str
    role: str
    path: Path
    dhash: int


def dhash(path: Path, hash_size: int = 16) -> int:
    with Image.open(path) as img:
        img = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    if hasattr(img, "get_flattened_data"):
        pixels = list(img.get_flattened_data())
    else:
        pixels = list(img.getdata())
    value = 0
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        for col in range(hash_size):
            value <<= 1
            if pixels[offset + col] > pixels[offset + col + 1]:
                value |= 1
    return value


def distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def page_dir_for(content_no: str) -> Path:
    matches = sorted(PRODUCTION.glob(f"{content_no}_*"))
    if not matches:
        raise FileNotFoundError(f"production page not found for {content_no}")
    return matches[0] / "納品用"


def image_files_for(page_dir: Path) -> list[tuple[str, Path]]:
    delivery = page_dir / "images" / "delivery"
    if not delivery.exists():
        raise FileNotFoundError(f"delivery image folder not found: {delivery}")
    files = []
    for path in sorted(delivery.glob("*.jpg")):
        name = path.name.lower()
        if "_thumbnail" in name:
            continue
        files.append(("delivery", path))
    scenes = page_dir / "video" / "scene_backgrounds"
    if scenes.exists():
        for path in sorted(scenes.glob("*.jpg")):
            files.append(("video_scene", path))
    return files


def role_for(path: Path, content_no: str) -> str:
    stem = path.stem
    prefix = f"{content_no}_"
    return stem[len(prefix):] if stem.startswith(prefix) else stem


def records_for(content_no: str) -> list[ImageRecord]:
    page_dir = page_dir_for(content_no)
    records = []
    for scope, path in image_files_for(page_dir):
        records.append(ImageRecord(content_no, scope, role_for(path, content_no), path, dhash(path)))
    return records


def load_source_manifest(page_dir: Path) -> list[dict[str, str]]:
    path = page_dir / "data" / "image_source_manifest.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def source_reuse_warnings(content_no: str) -> list[str]:
    page_dir = page_dir_for(content_no)
    rows = load_source_manifest(page_dir)
    by_source: dict[str, list[str]] = {}
    for row in rows:
        source = (row.get("source_file") or "").strip()
        role = (row.get("role") or "").strip()
        if not source or not role:
            continue
        by_source.setdefault(source, []).append(role)
    warnings = []
    for source, roles in sorted(by_source.items()):
        if len(roles) > 1:
            warnings.append(f"{content_no}: source reused {source}: {', '.join(roles)}")
    return warnings


def compare(records: list[ImageRecord], threshold: int) -> list[str]:
    warnings = []
    for idx, left in enumerate(records):
        for right in records[idx + 1:]:
            dist = distance(left.dhash, right.dhash)
            if left.scope != right.scope:
                continue
            if dist <= threshold:
                warnings.append(
                    f"{left.scope}: {left.page}/{left.path.name} ~= {right.page}/{right.path.name} "
                    f"(dhash distance {dist})"
                )
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect reused or near-duplicate delivery images.")
    parser.add_argument("content_no", nargs="+", help="content numbers such as 019 020")
    parser.add_argument("--threshold", type=int, default=18, help="dhash distance threshold; lower is stricter")
    parser.add_argument("--warn-only", action="store_true", help="print warnings but exit 0")
    args = parser.parse_args()

    all_records: list[ImageRecord] = []
    warnings: list[str] = []
    for content_no in args.content_no:
        all_records.extend(records_for(content_no))
        warnings.extend(source_reuse_warnings(content_no))
    warnings.extend(compare(all_records, args.threshold))

    if warnings:
        for warning in warnings:
            print(f"WARNING: {warning}")
        return 0 if args.warn_only else 1

    print("image reuse check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
