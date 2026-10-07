from __future__ import annotations

import csv
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "references" / "generated_024_031"
PRODUCT_DIR = ROOT / "references" / "product_images" / "cover_swimwear"

SIZE = (1800, 1400)


PAGE_PRODUCTS: dict[str, list[str]] = {
    "024": ["h-mzg20", "c-mizugi_nbf", "usbswc", "usbswb", "b-mizugi-3"],
    "025": ["h-mzg20", "c-mizugi_nbf"],
    "026": ["usbswc", "usbswb", "b-mizugi-3"],
    "027": ["h-mzg20", "c-mizugi_nbf", "usbswc", "usbswb", "b-mizugi-3"],
    "028": ["usbswc", "usbswb", "b-mizugi-3"],
    "029": ["h-mzg20", "c-mizugi_nbf", "usbswc", "usbswb", "b-mizugi-3"],
    "030": ["usbswc", "usbswb", "b-mizugi-3"],
    "031": ["h-mzg20", "c-mizugi_nbf", "usbswc", "usbswb", "b-mizugi-3"],
}

PAGE_TONE: dict[str, tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]] = {
    "024": ((221, 239, 242), (77, 145, 160), (245, 231, 213)),
    "025": ((225, 236, 243), (50, 91, 126), (233, 237, 230)),
    "026": ((241, 232, 220), (143, 112, 91), (220, 235, 231)),
    "027": ((239, 229, 225), (166, 91, 89), (222, 238, 241)),
    "028": ((244, 234, 220), (191, 135, 83), (224, 238, 240)),
    "029": ((225, 239, 242), (55, 132, 150), (243, 235, 217)),
    "030": ((237, 243, 225), (88, 141, 113), (242, 226, 205)),
    "031": ((230, 238, 244), (68, 102, 137), (242, 230, 219)),
}

TITLE_MAIN: dict[str, list[str]] = {
    "024": ["h-mzg20", "usbswc", "b-mizugi-3"],
    "025": ["c-mizugi_nbf", "h-mzg20"],
    "026": ["usbswc", "usbswb", "b-mizugi-3"],
    "027": ["usbswc", "h-mzg20", "b-mizugi-3"],
    "028": ["b-mizugi-3", "usbswb"],
    "029": ["h-mzg20", "c-mizugi_nbf", "usbswc"],
    "030": ["usbswb", "b-mizugi-3"],
    "031": ["h-mzg20", "usbswc"],
}

ROLES = ["title", "points", "accent_01", "accent_02"] + [f"section_{i}" for i in range(1, 6)]

# Crops avoid the product-page headline area where possible and keep the real
# swimwear silhouette. They are deliberately product-photo based, not AI redraws.
CROPS: dict[str, tuple[float, float, float, float]] = {
    "h-mzg20": (0.30, 0.02, 1.00, 0.98),
    "c-mizugi_nbf": (0.48, 0.02, 1.00, 0.98),
    "usbswc": (0.00, 0.02, 0.58, 0.98),
    "usbswb": (0.45, 0.02, 1.00, 0.98),
    "b-mizugi-3": (0.36, 0.02, 1.00, 1.00),
}

FULL_CROPS: dict[str, tuple[float, float, float, float]] = {
    "h-mzg20": (0.00, 0.00, 1.00, 1.00),
    "c-mizugi_nbf": (0.00, 0.00, 1.00, 1.00),
    "usbswc": (0.00, 0.00, 1.00, 1.00),
    "usbswb": (0.00, 0.00, 1.00, 1.00),
    "b-mizugi-3": (0.00, 0.00, 1.00, 1.00),
}


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in [r"C:\Windows\Fonts\yumin.ttf", r"C:\Windows\Fonts\meiryo.ttc"]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def blend(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))


def cover_crop(img: Image.Image, size: tuple[int, int], crop: tuple[float, float, float, float] | None = None) -> Image.Image:
    if crop:
        l, t, r, b = crop
        img = img.crop((round(img.width * l), round(img.height * t), round(img.width * r), round(img.height * b)))
    target_w, target_h = size
    scale = max(target_w / img.width, target_h / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def contain(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    scale = min(target_w / img.width, target_h / img.height)
    out = Image.new("RGB", size, (255, 255, 255))
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    out.paste(resized, ((target_w - resized.width) // 2, (target_h - resized.height) // 2))
    return out


def round_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def make_background(page_no: str, role: str) -> Image.Image:
    base, accent, warm = PAGE_TONE[page_no]
    w, h = SIZE
    img = Image.new("RGB", SIZE, base)
    draw = ImageDraw.Draw(img, "RGBA")

    # Soft resort/public-pool atmosphere. No fake swimwear is drawn here.
    for y in range(h):
        t = y / h
        col = blend(blend(base, (255, 255, 255), 0.28), warm, t * 0.18)
        draw.line((0, y, w, y), fill=col)

    seed = int(page_no) * 97 + sum(ord(c) for c in role)
    horizon = 800 + (seed % 5) * 42
    draw.rectangle((0, horizon, w, h), fill=(*blend(accent, (255, 255, 255), 0.50), 88))
    for i in range(7):
        y = horizon + 40 + i * 68
        draw.arc((-180 + i * 28, y, 1120 + i * 74, y + 210), 190, 350, fill=(*blend(accent, (255, 255, 255), 0.15), 50), width=8)

    if seed % 3 == 0:
        draw.rounded_rectangle((1080, 110, 1720, 1160), radius=58, fill=(*blend(warm, (255, 255, 255), 0.40), 94))
        draw.ellipse((1220, 80, 1940, 760), fill=(*blend(accent, (255, 255, 255), 0.58), 72))
    elif seed % 3 == 1:
        draw.polygon([(1110, 0), (1800, 0), (1800, 980), (1280, 1200)], fill=(*blend(warm, (255, 255, 255), 0.30), 110))
        for x in range(1150, 1840, 110):
            draw.line((x, 0, x - 360, 1300), fill=(*blend(accent, (255, 255, 255), 0.2), 46), width=9)
    else:
        draw.rounded_rectangle((1040, 240, 1740, 1190), radius=72, fill=(*blend(base, warm, 0.45), 92))
        for i in range(5):
            draw.ellipse((1040 + i * 118, 190 + (i % 2) * 82, 1110 + i * 118, 260 + (i % 2) * 82), fill=(*accent, 55))

    # Left side is kept calm because the build script adds page text there.
    draw.rounded_rectangle((56, 94, 760, 1240), radius=80, fill=(255, 255, 255, 38))
    draw.line((880, 140, 820, 1260), fill=(*blend(accent, warm, 0.35), 65), width=5)
    return img


def load_product_images() -> dict[str, Image.Image]:
    images: dict[str, Image.Image] = {}
    for sku in {sku for skus in PAGE_PRODUCTS.values() for sku in skus}:
        path = PRODUCT_DIR / f"{sku}.jpg"
        if not path.exists():
            raise FileNotFoundError(f"Missing product image: {path}")
        images[sku] = Image.open(path).convert("RGB")
    return images


def paste_card(
    canvas: Image.Image,
    product: Image.Image,
    box: tuple[int, int, int, int],
    crop: tuple[float, float, float, float],
    *,
    contain_mode: bool = False,
    rotate: float = 0.0,
) -> None:
    x, y, w, h = box
    card = contain(product.crop((
        round(product.width * crop[0]),
        round(product.height * crop[1]),
        round(product.width * crop[2]),
        round(product.height * crop[3]),
    )), (w, h)) if contain_mode else cover_crop(product, (w, h), crop)
    card = card.convert("RGBA")

    shadow = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((30, 30, 30 + w, 30 + h), radius=38, fill=(52, 47, 45, 80))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    canvas.alpha_composite(shadow, (x - 30, y - 18))

    mask = round_mask((w, h), 36)
    frame = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    frame.alpha_composite(card, (0, 0))
    if rotate:
        frame = frame.rotate(rotate, resample=Image.Resampling.BICUBIC, expand=True)
        mask = Image.new("L", frame.size, 255)
    canvas.paste(frame, (x, y), mask)

    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle((x, y, x + w, y + h), radius=36, outline=(255, 255, 255, 150), width=5)


def add_small_caption(canvas: Image.Image, text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    f = font(30)
    box = draw.textbbox((0, 0), text, font=f)
    w = box[2] - box[0] + 46
    h = box[3] - box[1] + 28
    draw.rounded_rectangle((x, y, x + w, y + h), radius=22, fill=(255, 255, 255, 165))
    draw.text((x + 23, y + 12), text, font=f, fill=(*color, 210))


def role_layout(page_no: str, role: str, skus: list[str], products: dict[str, Image.Image]) -> Image.Image:
    canvas = make_background(page_no, role).convert("RGBA")
    accent = PAGE_TONE[page_no][1]
    seed = int(page_no) * 83 + sum(ord(ch) for ch in role)

    if role == "title":
        title_skus = TITLE_MAIN[page_no]
        main = title_skus[0]
        sub = title_skus[1] if len(title_skus) > 1 else skus[(seed + 1) % len(skus)]
        third = title_skus[2] if len(title_skus) > 2 else None
        layout = int(page_no) % 4
        if layout == 0:
            paste_card(canvas, products[main], (980, 205, 520, 920), CROPS[main])
            paste_card(canvas, products[sub], (1365, 670, 300, 420), FULL_CROPS[sub], contain_mode=True)
            if third:
                paste_card(canvas, products[third], (1200, 855, 250, 310), FULL_CROPS[third], contain_mode=True)
        elif layout == 1:
            paste_card(canvas, products[main], (1060, 185, 560, 940), CROPS[main])
            paste_card(canvas, products[sub], (930, 735, 310, 380), FULL_CROPS[sub], contain_mode=True)
        elif layout == 2:
            paste_card(canvas, products[main], (1080, 180, 500, 930), CROPS[main])
            paste_card(canvas, products[sub], (1390, 330, 270, 520), CROPS[sub])
            if third:
                paste_card(canvas, products[third], (1010, 855, 270, 310), FULL_CROPS[third], contain_mode=True)
        else:
            paste_card(canvas, products[main], (1110, 215, 455, 900), CROPS[main])
            paste_card(canvas, products[sub], (1380, 700, 300, 390), FULL_CROPS[sub], contain_mode=True)
        add_small_caption(canvas, "実商品イメージ", 980, 1210, accent)
    elif role == "points":
        for i, sku in enumerate(skus[:3]):
            paste_card(canvas, products[sku], (920 + i * 270, 250 + (i % 2) * 60, 250, 640), CROPS[sku])
    elif role.startswith("accent"):
        chosen = skus[:]
        if role == "accent_02":
            chosen = list(reversed(chosen))
        positions = [(160, 220, 520, 760), (720, 150, 460, 700), (1190, 250, 450, 680)]
        for i, sku in enumerate(chosen[:3]):
            paste_card(canvas, products[sku], positions[i], CROPS[sku] if i != 1 else FULL_CROPS[sku], contain_mode=i == 1)
        add_small_caption(canvas, "水辺の準備に", 1220, 1020, accent)
    else:
        idx = int(role.split("_")[1])
        main = skus[(seed + idx) % len(skus)]
        alt = skus[(seed + idx + 1) % len(skus)]
        if idx % 2:
            paste_card(canvas, products[main], (1080, 155, 540, 1010), CROPS[main])
            paste_card(canvas, products[alt], (1375, 785, 250, 350), FULL_CROPS[alt], contain_mode=True)
        else:
            paste_card(canvas, products[main], (950, 210, 430, 900), CROPS[main])
            paste_card(canvas, products[alt], (1340, 265, 360, 760), CROPS[alt])
        # Add non-product cues without drawing a false product.
        draw = ImageDraw.Draw(canvas, "RGBA")
        for i in range(3):
            x = 1130 + i * 160 + (idx % 2) * 70
            y = 1120 + i * 20
            draw.arc((x, y, x + 240, y + 90), 190, 340, fill=(*accent, 82), width=8)

    return canvas.convert("RGB")


def write_manifest(rows: list[dict[str, str]]) -> None:
    path = REFS / "product_photo_source_manifest_024_031.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["content_no", "role", "skus", "method"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    REFS.mkdir(parents=True, exist_ok=True)
    products = load_product_images()
    rows: list[dict[str, str]] = []
    for page_no, skus in PAGE_PRODUCTS.items():
        for role in ROLES:
            img = role_layout(page_no, role, skus, products)
            img.save(REFS / f"{page_no}_{role}.png", quality=95)
            rows.append({
                "content_no": page_no,
                "role": role,
                "skus": " ".join(skus),
                "method": "actual_product_photo_composite",
            })
    write_manifest(rows)


if __name__ == "__main__":
    main()
