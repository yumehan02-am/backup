from __future__ import annotations

import csv
import math
import shutil
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "production"

PAGES = {
    "010": {
        "slug": "010_wide_pants_restroom_small_prep",
        "title_lines": ["ワイドパンツの日", "トイレで慌てないための小さな準備"],
        "points": ["このコラムのポイント", "› 個室で慌てない", "› 裾を床につけない", "› 季節で生地を選ぶ"],
        "banners": [
            ("010_restroom_prep_bg.png", "010_restroom_prep.jpg", ["好きな服ほど", "個室で忙しい"], "empathy"),
            ("010_clean_bg.png", "010_clean.jpg", ["裾を守るのは", "清潔感の話"], "knowledge"),
            ("010_season_bg.png", "010_season.jpg", ["夏は軽く", "冬はあたたかく"], "season"),
            ("010_closing_bg.png", "010_closing.jpg", ["服の内側で", "慌てない準備を"], "closing"),
        ],
        "scene_map": {
            "010_scene01.jpg": "010_title_bg.png",
            "010_scene02.jpg": "010_restroom_prep_bg.png",
            "010_scene03.jpg": "010_clean_bg.png",
            "010_scene04.jpg": "010_season_bg.png",
            "010_scene05.jpg": "010_closing_bg.png",
            "010_scene06.jpg": "010_title_bg.png",
        },
        "chords": [(293.66, 369.99, 440.00), (329.63, 392.00, 493.88), (261.63, 329.63, 440.00), (246.94, 329.63, 392.00)],
        "melody": 659.25,
    },
    "011": {
        "slug": "011_floor_not_touch_pettipants",
        "title_lines": ["床につけたくない", "その一瞬のために", "ペチパンツという裏方"],
        "points": ["このコラムのポイント", "› 裾を気持ちよく扱う", "› 裏方で服を支える", "› 季節で一枚を替える"],
        "banners": [
            ("011_clean_bg.png", "011_clean.jpg", ["清潔感は", "見えない所作に出る"], "knowledge"),
            ("011_hands_bg.png", "011_hands.jpg", ["裾をまとめるだけで", "手は忙しい"], "empathy"),
            ("011_support_bg.png", "011_support.jpg", ["主役は服", "裏方はインナー"], "concept"),
            ("011_season_bg.png", "011_season.jpg", ["夏は軽さ", "冬はあたたかさ"], "season"),
            ("011_closing_bg.png", "011_closing.jpg", ["大げさではない", "小さな準備"], "closing"),
        ],
        "scene_map": {
            "011_scene01.jpg": "011_title_bg.png",
            "011_scene02.jpg": "011_clean_bg.png",
            "011_scene03.jpg": "011_hands_bg.png",
            "011_scene04.jpg": "011_support_bg.png",
            "011_scene05.jpg": "011_season_bg.png",
            "011_scene06.jpg": "011_closing_bg.png",
        },
        "chords": [(261.63, 329.63, 392.00), (246.94, 329.63, 415.30), (293.66, 369.99, 440.00), (220.00, 277.18, 369.99)],
        "melody": 587.33,
    },
    "012": {
        "slug": "012_wide_pants_restroom_strategy_illustrated",
        "title_lines": ["ワイドパンツの個室会議", "裾と私の静かな攻防"],
        "points": ["このコラムのポイント", "› 布の量と向き合う", "› 床につけたくない", "› 季節で作戦を変える"],
        "banners": [
            ("012_strategy_bg.png", "012_strategy.jpg", ["今日の敵は", "布の量"], "comic"),
            ("012_busy_bg.png", "012_busy.jpg", ["片手作戦は", "意外と忙しい"], "comic"),
            ("012_season_bg.png", "012_season.jpg", ["夏の会議", "冬の会議"], "season"),
            ("012_closing_bg.png", "012_closing.jpg", ["見えない作戦で", "好きな服を気楽に"], "closing"),
        ],
        "scene_map": {
            "012_scene01.jpg": "012_title_bg.png",
            "012_scene02.jpg": "012_strategy_bg.png",
            "012_scene03.jpg": "012_busy_bg.png",
            "012_scene04.jpg": "012_strategy_bg.png",
            "012_scene05.jpg": "012_season_bg.png",
            "012_scene06.jpg": "012_closing_bg.png",
        },
        "chords": [(329.63, 392.00, 493.88), (293.66, 369.99, 440.00), (349.23, 440.00, 523.25), (261.63, 329.63, 392.00)],
        "melody": 698.46,
    },
}


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


def glow_box(size: tuple[int, int], alpha: int = 88) -> Image.Image:
    w, h = size
    pad = 56
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=30, fill=(255, 255, 255, alpha))
    return layer.filter(ImageFilter.GaussianBlur(28))


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
    for idx, line in enumerate(lines):
        font = mincho(sizes[min(idx, len(sizes) - 1)], idx == 0)
        w, h = text_size(line, font)
        frame.alpha_composite(glow_box((w + 72, h + 36)), (x - 92, current_y - 72))
        draw.text((x, current_y), line, font=font, fill=(*fill, 255))
        current_y += gaps[min(idx, len(gaps) - 1)]
    img.paste(frame.convert("RGB"))


def make_title(no: str, base: Path, cfg: dict) -> None:
    img = Image.open(base / "images" / f"{no}_title_bg.png").convert("RGB")
    crop = cover_crop(img, (1600, 900), -0.18, 0.0)
    draw_lines(crop, cfg["title_lines"], 118, 305, [76, 46], [106, 72])
    crop.save(base / "images" / f"{no}_title.jpg", quality=94)
    crop.save(base / "images" / f"{no}_thumbnail.jpg", quality=94)


def make_points(no: str, base: Path, cfg: dict) -> None:
    src_name = cfg["banners"][0][0]
    crop = cover_crop(Image.open(base / "images" / src_name).convert("RGB"), (1600, 520), -0.28, 0.0)
    draw_lines(crop, cfg["points"], 110, 82, [48, 34, 34, 34], [76, 56, 56, 56])
    crop.save(base / "images" / f"{no}_points.jpg", quality=94)


def make_banner(base: Path, src_name: str, out_name: str, lines: list[str]) -> None:
    crop = cover_crop(Image.open(base / "images" / src_name).convert("RGB"), (1600, 520), -0.28, 0.0)
    draw_lines(crop, lines, 96, 146, [52, 52], [74, 70])
    crop.save(base / "images" / out_name, quality=94)


def make_scene_backgrounds(no: str, base: Path, cfg: dict) -> None:
    scenes = base / "video" / "scene_backgrounds"
    if scenes.exists():
        shutil.rmtree(scenes)
    scenes.mkdir(parents=True, exist_ok=True)
    for out_name, src_name in cfg["scene_map"].items():
        src = Image.open(base / "images" / src_name).convert("RGB")
        square = cover_crop(src, (1200, 1200), 0.0, 0.0)
        square.save(scenes / out_name, quality=94)


def make_bgm(no: str, base: Path, cfg: dict) -> None:
    video = base / "video"
    video.mkdir(parents=True, exist_ok=True)
    path = video / f"bgm_pettipants_{no}.wav"
    sr = 44100
    duration = 33.0
    total = int(sr * duration)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for n in range(total):
            t = n / sr
            chord = cfg["chords"][int(t / 4.0) % len(cfg["chords"])]
            env = min(1.0, t / 1.8, (duration - t) / 2.2)
            sample = 0.0
            for freq in chord:
                sample += math.sin(2 * math.pi * freq * t) * 0.043
                sample += math.sin(2 * math.pi * freq * 2.0 * t) * 0.004
            sample += math.sin(2 * math.pi * cfg["melody"] * t) * 0.007 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.10 * t))
            sample *= env * 0.58
            val = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(val.to_bytes(2, "little", signed=True))
        wf.writeframes(frames)


def make_contact_sheet(no: str, base: Path, cfg: dict) -> None:
    files = [f"{no}_title.jpg", f"{no}_points.jpg"] + [out for _, out, _, _ in cfg["banners"]]
    sheet = Image.new("RGB", (1200, 800), "white")
    for i, name in enumerate(files):
        img = Image.open(base / "images" / name).convert("RGB")
        img.thumbnail((400, 260), Image.Resampling.LANCZOS)
        x = (i % 3) * 400 + (400 - img.width) // 2
        y = (i // 3) * 400 + 40
        sheet.paste(img, (x, y))
    sheet.save(base / "images" / f"{no}_banner_contact_sheet.jpg", quality=92)


def build_page(no: str) -> None:
    cfg = PAGES[no]
    base = PRODUCTION / cfg["slug"] / "納品用"
    make_title(no, base, cfg)
    make_points(no, base, cfg)
    for src, out, lines, _kind in cfg["banners"]:
        make_banner(base, src, out, lines)
    make_scene_backgrounds(no, base, cfg)
    make_bgm(no, base, cfg)
    make_contact_sheet(no, base, cfg)


def main() -> None:
    targets = sys.argv[1:] or ["010", "011", "012"]
    for no in targets:
        build_page(no)


if __name__ == "__main__":
    main()
