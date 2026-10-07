from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "references" / "generated_ai_cover_swimwear"
REFS = ROOT / "references" / "generated_024_031"

ROLES = ["title", "points", "accent_01", "accent_02"] + [f"section_{i}" for i in range(1, 6)]

PAGE_PROMPTS = {
    "024": "common body-cover swimsuit preparation",
    "025": "slim-looking body-cover swimsuit",
    "026": "soft loose-cover swimsuit",
    "027": "before losing weight honest column",
    "028": "light comic self-conscious pool column",
    "029": "complete set preparation poolside",
    "030": "family waterplay body-cover swimsuit",
    "031": "slim type and soft type comparison",
}


def cover_crop(img: Image.Image, size: tuple[int, int], bias_x: float = 0.0, bias_y: float = 0.0) -> Image.Image:
    target_w, target_h = size
    scale = max(target_w / img.width, target_h / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    max_left = resized.width - target_w
    max_top = resized.height - target_h
    left = round(max_left * (0.5 + bias_x / 2))
    top = round(max_top * (0.5 + bias_y / 2))
    left = max(0, min(max_left, left))
    top = max(0, min(max_top, top))
    return resized.crop((left, top, left + target_w, top + target_h))


def variant(base: Image.Image, page_no: str, role: str) -> Image.Image:
    idx = ROLES.index(role)
    # Keep the subject on the right and the copy space on the left. Small crop
    # and tone changes are for role separation only; the image remains AI-generated.
    bias_x = [-0.10, -0.06, 0.00, 0.05, -0.12, -0.04, 0.02, 0.08, -0.02][idx]
    bias_y = [0.00, -0.04, 0.03, 0.05, -0.02, 0.02, -0.03, 0.04, 0.00][idx]
    img = cover_crop(base, (1800, 1400), bias_x=bias_x, bias_y=bias_y).convert("RGB")
    if role != "title":
        img = ImageEnhance.Color(img).enhance(0.94 + (idx % 3) * 0.04)
        img = ImageEnhance.Brightness(img).enhance(0.98 + (idx % 2) * 0.025)
    if role == "points":
        img = img.filter(ImageFilter.GaussianBlur(0.35))
    return img


def main() -> None:
    REFS.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for page_no, note in PAGE_PROMPTS.items():
        src = BASE_DIR / f"{page_no}_base.png"
        if not src.exists():
            raise FileNotFoundError(src)
        base = Image.open(src).convert("RGB")
        for role in ROLES:
            img = variant(base, page_no, role)
            out = REFS / f"{page_no}_{role}.png"
            img.save(out, quality=95)
            rows.append({
                "content_no": page_no,
                "role": role,
                "source_file": src.name,
                "method": "ai_generated_product_reference",
                "note": note,
            })
    with (REFS / "ai_generated_source_manifest_024_031.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["content_no", "role", "source_file", "method", "note"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
