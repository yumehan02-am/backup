from __future__ import annotations

import csv
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "production" / "013_pad_user_shorts_fit" / "納品用"
IMAGES = BASE / "images"
VIDEO = BASE / "video"
DATA = BASE / "data"
IMAGE_BASE_URL = "https://image.rakuten.co.jp/u-b-yumehan/cabinet/contents/"


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
    scratch = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    box = ImageDraw.Draw(scratch).textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


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


def glow_box(size: tuple[int, int], alpha: int = 82) -> Image.Image:
    w, h = size
    pad = 64
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=28, fill=(255, 255, 255, alpha))
    return layer.filter(ImageFilter.GaussianBlur(30))


def draw_lines(
    img: Image.Image,
    lines: list[str],
    x: int,
    y: int,
    sizes: list[int],
    gaps: list[int],
    fill=(45, 39, 37),
) -> None:
    frame = img.convert("RGBA")
    draw = ImageDraw.Draw(frame)
    current_y = y
    for idx, line in enumerate(lines):
        font = mincho(sizes[min(idx, len(sizes) - 1)], idx == 0)
        w, h = text_size(line, font)
        frame.alpha_composite(glow_box((w + 84, h + 42)), (x - 104, current_y - 76))
        draw.text((x, current_y), line, font=font, fill=(*fill, 255))
        current_y += gaps[min(idx, len(gaps) - 1)]
    img.paste(frame.convert("RGB"))


def make_title() -> None:
    img = Image.open(IMAGES / "013_title_bg.png").convert("RGB")
    crop = cover_crop(img, (1600, 900), -0.18, 0.0)
    draw_lines(
        crop,
        ["パッド派のためのショーツ選び", "ずれにくさと普通のはき心地の話"],
        112,
        310,
        [70, 46],
        [104, 72],
    )
    crop.save(IMAGES / "013_title.jpg", quality=94)
    crop.save(IMAGES / "013_thumbnail.jpg", quality=94)


def make_points() -> None:
    crop = cover_crop(Image.open(IMAGES / "013_empathy_bg.png").convert("RGB"), (1600, 520), -0.26, 0.0)
    draw_lines(
        crop,
        ["このコラムのポイント", "› パッド派の小さな不安", "› 下着側でできる準備", "› 普通っぽさの続けやすさ"],
        105,
        74,
        [48, 34, 34, 34],
        [76, 56, 56, 56],
    )
    crop.save(IMAGES / "013_points.jpg", quality=94)


def make_banner(src: str, out: str, lines: list[str], bias_x: float = -0.28) -> None:
    crop = cover_crop(Image.open(IMAGES / src).convert("RGB"), (1600, 520), bias_x, 0.0)
    draw_lines(crop, lines, 96, 147, [52, 52], [76, 70])
    crop.save(IMAGES / out, quality=94)


def make_accent(src: str, out: str, bias_x: float = 0.0) -> None:
    img = cover_crop(Image.open(IMAGES / src).convert("RGB"), (1200, 1200), bias_x, 0.0)
    img.save(IMAGES / out, quality=94)


def make_scene_backgrounds() -> None:
    scenes = VIDEO / "scene_backgrounds"
    if scenes.exists():
        shutil.rmtree(scenes)
    scenes.mkdir(parents=True, exist_ok=True)
    mapping = {
        "013_scene01.jpg": "013_title_bg.png",
        "013_scene02.jpg": "013_closing_bg.png",
        "013_scene03.jpg": "013_empathy_bg.png",
        "013_scene04.jpg": "013_knowledge_bg.png",
        "013_scene05.jpg": "013_lifestyle_bg.png",
        "013_scene06.jpg": "013_closing_bg.png",
    }
    for out_name, src_name in mapping.items():
        square = cover_crop(Image.open(IMAGES / src_name).convert("RGB"), (1200, 1200), 0.0, 0.0)
        square.save(scenes / out_name, quality=94)


def make_bgm() -> None:
    VIDEO.mkdir(parents=True, exist_ok=True)
    path = VIDEO / "bgm_apparel_soft_013.wav"
    sr = 44100
    duration = 28.8
    chords = [(261.63, 329.63, 392.00), (293.66, 369.99, 440.00), (246.94, 329.63, 415.30), (329.63, 392.00, 493.88)]
    total = int(sr * duration)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for n in range(total):
            t = n / sr
            env = min(1.0, t / 1.6, (duration - t) / 2.0)
            chord = chords[int(t / 4.0) % len(chords)]
            sample = 0.0
            for freq in chord:
                sample += math.sin(2 * math.pi * freq * t) * 0.052
                sample += math.sin(2 * math.pi * freq * 2.0 * t) * 0.004
            sample += math.sin(2 * math.pi * 659.25 * t) * 0.006 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.09 * t))
            sample *= env * 0.58
            val = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(val.to_bytes(2, "little", signed=True))
        wf.writeframes(frames)


def make_contact_sheet() -> None:
    files = [
        "013_title.jpg",
        "013_points.jpg",
        "013_empathy.jpg",
        "013_knowledge.jpg",
        "013_lifestyle.jpg",
        "013_season.jpg",
        "013_closing.jpg",
        "013_accent_01.jpg",
        "013_accent_02.jpg",
    ]
    sheet = Image.new("RGB", (1200, 1200), "white")
    for i, name in enumerate(files):
        img = Image.open(IMAGES / name).convert("RGB")
        img.thumbnail((400, 360), Image.Resampling.LANCZOS)
        x = (i % 3) * 400 + (400 - img.width) // 2
        y = (i // 3) * 400 + 20
        sheet.paste(img, (x, y))
    sheet.save(IMAGES / "013_banner_contact_sheet.jpg", quality=92)


def export_tsv() -> None:
    page_title = "パッド派のためのショーツ選び｜ずれにくさと普通のはき心地の話"
    md_lines = (BASE / "page_copy.md").read_text(encoding="utf-8").splitlines()
    lead: list[str] = []
    sections: list[dict[str, list[str] | str]] = []
    current: dict[str, list[str] | str] | None = None
    for raw in md_lines:
        line = raw.strip()
        if not line or line.startswith("# "):
            continue
        if line.startswith("## "):
            if current:
                sections.append(current)
            current = {"title": line[3:].strip(), "body": []}
            continue
        if current:
            current["body"].append(line)
        else:
            lead.append(line)
    if current:
        sections.append(current)

    banners = {
        1: ["013_empathy.jpg"],
        2: ["013_knowledge.jpg"],
        3: ["013_lifestyle.jpg"],
        4: ["013_season.jpg"],
        5: ["013_closing.jpg"],
    }
    accents = {2: ["013_accent_01.jpg"], 4: ["013_accent_02.jpg"]}
    rows: list[list[str]] = []

    def add(kind: str, content: str, source: str = "", warning: str = "") -> None:
        rows.append([str(len(rows) + 1), kind, content, source, str(len(content)) if kind in {"メインタイトル", "小タイトル", "本文", "動画下本文"} else "", warning])

    def image_url(name: str) -> str:
        return IMAGE_BASE_URL + name

    add("画像", image_url("013_title.jpg"), "images/013_title.jpg", "タイトル画像")
    add("メインタイトル", page_title if len(page_title) <= 40 else "パッド派のためのショーツ選び", page_title)
    add("動画", "video/opening_cm_013_vertical.mp4", "video/opening_cm_013_vertical.mp4")
    add("動画下本文", "\n" + "\n\n".join(lead), "page_copy.md#lead", "本文先頭に改行")

    for idx, section in enumerate(sections, 1):
        title = str(section["title"])
        if title == "まとめ":
            small = "まとめ"
        else:
            small = title[:20]
        add("小タイトル", small, title)
        for banner in banners.get(idx, []):
            add("画像", image_url(banner), f"images/{banner}")
        body = "\n\n".join(section["body"])  # type: ignore[arg-type]
        add("本文", "\n" + body, f"page_copy.md#{idx}", "本文先頭に改行")
        for accent in accents.get(idx, []):
            add("画像", image_url(accent), f"images/{accent}", "文字なし正方形アクセント")

    add("関連商品", "kprcs00", "product_ids.csv", "関連商品パーツ用ID")
    with (BASE / "page_paste_blocks.tsv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, dialect="excel-tab")
        writer.writerow(["順番", "ブロック種別", "貼り付け内容", "元データ", "文字数", "警告"])
        writer.writerows(rows)


def build() -> None:
    make_title()
    make_points()
    make_banner("013_empathy_bg.png", "013_empathy.jpg", ["気になるのは", "ほんの小さな違和感"])
    make_banner("013_knowledge_bg.png", "013_knowledge.jpg", ["安心感は", "吸水量だけではない"])
    make_banner("013_lifestyle_bg.png", "013_lifestyle.jpg", ["普通っぽさが", "続けやすさになる"])
    make_banner("013_season_bg.png", "013_season.jpg", ["外出時間で", "準備は変わる"])
    make_banner("013_closing_bg.png", "013_closing.jpg", ["念のためを", "自然な準備に"])
    make_accent("013_season_bg.png", "013_accent_01.jpg")
    make_accent("013_lifestyle_bg.png", "013_accent_02.jpg")
    make_scene_backgrounds()
    make_bgm()
    make_contact_sheet()
    export_tsv()


if __name__ == "__main__":
    build()
