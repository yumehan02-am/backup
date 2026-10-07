import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont


BASE = pathlib.Path(__file__).resolve().parent
IMAGES = BASE / "images"
GENERATED = pathlib.Path(r"C:\Users\i58400am\.codex\generated_images\01a03bd9-3f16-70d1-81ca-80d9bbc91430")
SOURCE = GENERATED / "call_r3J0H6aIT9TW7yhKTL7pQevT.png"


def mincho(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\yumindb.ttf" if bold else r"C:\Windows\Fonts\yumin.ttf",
        r"C:\Windows\Fonts\YuMincho.ttc",
        r"C:\Windows\Fonts\meiryo.ttc",
    ]
    for path in candidates:
        if pathlib.Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def cover_crop(img, size):
    target_w, target_h = size
    scale = max(target_w / img.width, target_h / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def text_bbox(text, font):
    scratch = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    draw = ImageDraw.Draw(scratch)
    return draw.textbbox((0, 0), text, font=font)


def text_size(text, font):
    box = text_bbox(text, font)
    return box[2] - box[0], box[3] - box[1]


def fit_font(text, start_size, max_width, bold=True):
    size = start_size
    while size >= 48:
        font = mincho(size, bold)
        if text_size(text, font)[0] <= max_width:
            return font
        size -= 2
    return mincho(size, bold)


def draw_soft_glow_text(img, xy, text, font, fill, glow_rgb=(255, 255, 255), glow_strength=0.62):
    draw = ImageDraw.Draw(img)
    x, y = xy
    bbox = draw.textbbox((x, y), text, font=font)
    pad = 82
    w = max(1, bbox[2] - bbox[0] + pad * 2)
    h = max(1, bbox[3] - bbox[1] + pad * 2)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.text((pad + x - bbox[0], pad + y - bbox[1]), text, font=font, fill=255)
    alpha = mask.filter(ImageFilter.MaxFilter(21)).filter(ImageFilter.GaussianBlur(16))
    alpha = alpha.point(lambda v: min(150, int(v * glow_strength)))
    glow = Image.new("RGBA", (w, h), (*glow_rgb, 0))
    glow.putalpha(alpha)
    img.alpha_composite(glow, (bbox[0] - pad, bbox[1] - pad))
    draw.text((x, y), text, font=font, fill=fill)


def make_thumbnail():
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    IMAGES.mkdir(parents=True, exist_ok=True)
    bg = cover_crop(Image.open(SOURCE).convert("RGB"), (1600, 900)).convert("RGBA")
    bg.convert("RGB").save(IMAGES / "thumbnail_background.jpg", quality=95)

    main_lines = ["尿もれ対策を", "ふつうの準備に。"]
    sub_line = "吸水ショーツの新しい考え方"

    x = 96
    y = 230
    max_width = 760
    main_font = fit_font(max(main_lines, key=len), 92, max_width, True)
    sub_font = fit_font(sub_line, 50, max_width, False)
    fill = (43, 38, 36, 252)

    line_gap = 118
    for i, line in enumerate(main_lines):
        draw_soft_glow_text(bg, (x, y + i * line_gap), line, main_font, fill)

    draw_soft_glow_text(bg, (x + 4, y + line_gap * 2 + 42), sub_line, sub_font, fill, glow_strength=0.52)

    out = IMAGES / "thumbnail.jpg"
    bg.convert("RGB").save(out, quality=94)
    print(out)


if __name__ == "__main__":
    make_thumbnail()
