from __future__ import annotations

import math
import shutil
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


BASE = Path(__file__).resolve().parent
IMAGES = BASE / "images"
VIDEO = BASE / "video"
SCENES = VIDEO / "scene_backgrounds"
NO = "006"


def mincho(size: int, bold: bool = False):
    candidates = [
        r"C:\Windows\Fonts\yumindb.ttf" if bold else r"C:\Windows\Fonts\yumin.ttf",
        r"C:\Windows\Fonts\YuMincho.ttc",
        r"C:\Windows\Fonts\meiryo.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_size(text: str, font) -> tuple[int, int]:
    img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    box = ImageDraw.Draw(img).textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def cover_crop(img: Image.Image, size: tuple[int, int], bias_x: float = 0.0, bias_y: float = 0.0) -> Image.Image:
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    max_left = resized.width - tw
    max_top = resized.height - th
    left = round(max_left * (0.5 + bias_x / 2))
    top = round(max_top * (0.5 + bias_y / 2))
    left = max(0, min(max_left, left))
    top = max(0, min(max_top, top))
    return resized.crop((left, top, left + tw, top + th))


def glow_box(size: tuple[int, int], alpha: int = 105) -> Image.Image:
    w, h = size
    pad = 34
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=26, fill=(255, 255, 255, alpha))
    return layer.filter(ImageFilter.GaussianBlur(18))


def draw_lines(
    img: Image.Image,
    lines: list[str],
    x: int,
    y: int,
    sizes: list[int],
    gaps: list[int],
    fill=(42, 36, 34),
) -> None:
    frame = img.convert("RGBA")
    draw = ImageDraw.Draw(frame)
    current_y = y
    for i, line in enumerate(lines):
        font = mincho(sizes[min(i, len(sizes) - 1)], i == 0)
        w, h = text_size(line, font)
        glow = glow_box((w + 70, h + 34))
        frame.alpha_composite(glow, (x - 35 - 34, current_y - 25 - 34))
        draw.text((x, current_y), line, font=font, fill=(*fill, 255))
        current_y += gaps[min(i, len(gaps) - 1)]
    img.paste(frame.convert("RGB"))


def draw_center(img: Image.Image, lines: list[str], y: int, sizes: list[int], gap: int = 72) -> None:
    frame = img.convert("RGBA")
    draw = ImageDraw.Draw(frame)
    current_y = y
    for i, line in enumerate(lines):
        font = mincho(sizes[min(i, len(sizes) - 1)], i == 0)
        w, h = text_size(line, font)
        x = (img.width - w) // 2
        glow = glow_box((w + 70, h + 34))
        frame.alpha_composite(glow, (x - 35 - 34, current_y - 25 - 34))
        draw.text((x, current_y), line, font=font, fill=(42, 36, 34, 255))
        current_y += gap
    img.paste(frame.convert("RGB"))


def make_banner(
    source: str,
    output: str,
    lines: list[str],
    x: int,
    y: int,
    sizes: list[int],
    gaps: list[int],
    bias_x: float = -0.25,
    bias_y: float = 0.0,
) -> None:
    bg_src = Image.open(IMAGES / source).convert("RGB")
    bg = cover_crop(bg_src, (1600, 520), bias_x, bias_y)
    draw_lines(bg, lines, x, y, sizes, gaps)
    bg.save(IMAGES / output, quality=94)


def make_title() -> None:
    bg = Image.open(IMAGES / "006_title_bg.png").convert("RGB")
    title = cover_crop(bg, (1600, 900), -0.28, 0.0)
    draw_lines(title, ["シャツの前が浮く問題", "バストラインと下着選びの現実"], 120, 310, [76, 44], [104, 70])
    title.save(IMAGES / "006_title.jpg", quality=94)

    thumb = cover_crop(bg, (1600, 900), -0.28, 0.0)
    draw_lines(thumb, ["シャツの前が浮く問題", "バストラインと下着選びの現実"], 120, 310, [76, 44], [104, 70])
    thumb.save(IMAGES / "006_thumbnail.jpg", quality=94)


def make_points() -> None:
    bg = cover_crop(Image.open(IMAGES / "006_points_bg.png").convert("RGB"), (1600, 520), -0.25, 0.0)
    draw_lines(
        bg,
        ["このコラムのポイント", "› 浮く原因はサイズだけではない", "› 前中心の厚みで印象が変わる", "› 服を主役にする下着選び"],
        112,
        92,
        [48, 34, 34, 34],
        [76, 56, 56, 56],
    )
    bg.save(IMAGES / "006_points.jpg", quality=94)


def make_scene_backgrounds() -> None:
    SCENES.mkdir(parents=True, exist_ok=True)
    mapping = {
        "006_scene01.jpg": "006_title_bg.png",
        "006_scene02.jpg": "006_placket_bg.png",
        "006_scene03.jpg": "006_points_bg.png",
        "006_scene04.jpg": "006_choice_bg.png",
        "006_scene05.jpg": "006_outfit_bg.png",
        "006_scene06.jpg": "006_closing_bg.png",
    }
    for out_name, src_name in mapping.items():
        src = Image.open(IMAGES / src_name).convert("RGB").resize((1200, 1200), Image.Resampling.LANCZOS)
        src.save(SCENES / out_name, quality=94)


def make_bgm() -> None:
    VIDEO.mkdir(parents=True, exist_ok=True)
    path = VIDEO / "bgm_shirt_column_006.wav"
    sr = 44100
    duration = 31.0
    total = int(sr * duration)
    chords = [
        (261.63, 329.63, 392.00),
        (293.66, 349.23, 440.00),
        (246.94, 329.63, 392.00),
        (220.00, 277.18, 369.99),
    ]
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for n in range(total):
            t = n / sr
            chord = chords[int(t / 4.0) % len(chords)]
            env = min(1.0, t / 1.8, (duration - t) / 2.0)
            sample = 0.0
            for freq in chord:
                sample += math.sin(2 * math.pi * freq * t) * 0.045
                sample += math.sin(2 * math.pi * freq * 2.0 * t) * 0.005
            sample += math.sin(2 * math.pi * 587.33 * t) * 0.008 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.11 * t))
            sample *= env * 0.55
            val = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(val.to_bytes(2, "little", signed=True))
        wf.writeframes(frames)


def make_contact_sheet() -> None:
    files = ["006_title.jpg", "006_points.jpg", "006_placket.jpg", "006_choice.jpg", "006_outfit.jpg", "006_closing.jpg"]
    sheet = Image.new("RGB", (1200, 800), "white")
    for i, name in enumerate(files):
        img = Image.open(IMAGES / name).convert("RGB")
        img.thumbnail((400, 260), Image.Resampling.LANCZOS)
        x = (i % 3) * 400 + (400 - img.width) // 2
        y = (i // 3) * 400 + 40
        sheet.paste(img, (x, y))
    sheet.save(IMAGES / "006_banner_contact_sheet.jpg", quality=92)


def main() -> None:
    make_title()
    make_points()
    make_banner("006_placket_bg.png", "006_placket.jpg", ["ボタンは留まるのに", "前だけ落ち着かない"], 96, 148, [48, 48], [68, 68])
    make_banner("006_choice_bg.png", "006_choice.jpg", ["体を変える話ではなく", "服との接点を整える"], 86, 142, [46, 46], [66, 66])
    make_banner("006_outfit_bg.png", "006_outfit.jpg", ["シャツの日は", "前中心と脇の収まりを見る"], 88, 144, [50, 40], [72, 64])
    make_banner("006_closing_bg.png", "006_closing.jpg", ["好きなシャツを", "もう少し気楽に"], 92, 148, [52, 52], [74, 74])
    make_scene_backgrounds()
    make_bgm()
    make_contact_sheet()


if __name__ == "__main__":
    main()
