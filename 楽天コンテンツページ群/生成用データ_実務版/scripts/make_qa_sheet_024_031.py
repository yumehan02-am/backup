from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "production"
PAGES = [
    "024_cover_swimwear_preparation",
    "025_slim_look_cover_swimwear",
    "026_soft_hide_cover_swimwear",
    "027_before_weight_loss_swimwear",
    "028_belly_self_conscious_swimwear",
    "029_poolside_set_preparation",
    "030_family_waterplay_cover_swimwear",
    "031_slim_or_soft_cover_swimwear",
]


def font(size: int):
    for candidate in [r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\yumin.ttf"]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def thumb(path: Path, size: tuple[int, int]) -> Image.Image:
    img = Image.open(path).convert("RGB")
    scale = min(size[0] / img.width, size[1] / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    out = Image.new("RGB", size, (246, 246, 246))
    out.paste(resized, ((size[0] - resized.width) // 2, (size[1] - resized.height) // 2))
    return out


def main() -> None:
    cols = 4
    cell_w, cell_h = 430, 510
    out = Image.new("RGB", (cols * cell_w, 2 * cell_h), (238, 238, 238))
    draw = ImageDraw.Draw(out)
    title_font = font(22)
    for idx, page in enumerate(PAGES):
        no = page[:3]
        base = PRODUCTION / page / "納品用" / "images" / "delivery"
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x + 8, y + 8, x + cell_w - 8, y + cell_h - 8), fill=(255, 255, 255), outline=(210, 210, 210))
        draw.text((x + 18, y + 18), page, font=title_font, fill=(40, 40, 40))
        title_img = thumb(base / f"{no}_title.jpg", (390, 220))
        out.paste(title_img, (x + 20, y + 56))
        for i in range(1, 4):
            section = thumb(base / f"{no}_section_{i}.jpg", (124, 74))
            out.paste(section, (x + 20 + (i - 1) * 132, y + 294))
        for i, name in enumerate([f"{no}_accent_01.jpg", f"{no}_accent_02.jpg"]):
            accent = thumb(base / name, (124, 124))
            out.paste(accent, (x + 20 + i * 132, y + 380))
    out.save(PRODUCTION / "_qa_024_031_actual_product_photo.jpg", quality=94)


if __name__ == "__main__":
    main()
