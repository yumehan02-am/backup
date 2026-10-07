from __future__ import annotations

import csv
import math
import shutil
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
IMAGE_BASE_URL = "https://image.rakuten.co.jp/u-b-yumehan/cabinet/contents/"


PAGES = {
    "015": ROOT / "production" / "015_pool_restart_swimwear" / "納品用",
    "016": ROOT / "production" / "016_swimwear_shop_freeze_illustrated" / "納品用",
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


def load_backgrounds(work: Path, names: list[str]) -> dict[str, Image.Image]:
    missing = [name for name in names if not (work / name).exists()]
    if missing:
        raise FileNotFoundError(
            "納品画像・動画背景は個別生成が必須です。素材シートからの切り出しは禁止です。"
            f"不足背景: {', '.join(missing)}"
        )
    return {name: Image.open(work / name).convert("RGB") for name in names}


def glow_box(size: tuple[int, int], alpha: int = 82) -> Image.Image:
    w, h = size
    pad = 72
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=28, fill=(255, 255, 255, alpha))
    return layer.filter(ImageFilter.GaussianBlur(32))


def draw_lines(img: Image.Image, lines: list[str], x: int, y: int, sizes: list[int], gaps: list[int], fill=(42, 38, 35)) -> None:
    frame = img.convert("RGBA")
    draw = ImageDraw.Draw(frame)
    current_y = y
    for idx, line in enumerate(lines):
        font = mincho(sizes[min(idx, len(sizes) - 1)], idx == 0)
        w, h = text_size(line, font)
        frame.alpha_composite(glow_box((w + 96, h + 48)), (x - 116, current_y - 82))
        draw.text((x, current_y), line, font=font, fill=(*fill, 255))
        current_y += gaps[min(idx, len(gaps) - 1)]
    img.paste(frame.convert("RGB"))


def make_bgm(base: Path, content_no: str, mood: str) -> None:
    video = base / "video"
    video.mkdir(parents=True, exist_ok=True)
    path = video / f"bgm_swimwear_{content_no}.wav"
    sr = 44100
    duration = 30.0
    if mood == "comic":
        chords = [(392.00, 493.88, 587.33), (349.23, 440.00, 523.25), (329.63, 415.30, 493.88), (392.00, 523.25, 659.25)]
        pulse = 0.014
    else:
        chords = [(261.63, 329.63, 392.00), (293.66, 369.99, 440.00), (246.94, 329.63, 415.30), (329.63, 392.00, 493.88)]
        pulse = 0.008
    total = int(sr * duration)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for n in range(total):
            t = n / sr
            env = min(1.0, t / 1.4, (duration - t) / 2.0)
            chord = chords[int(t / 4.0) % len(chords)]
            sample = 0.0
            for freq in chord:
                sample += math.sin(2 * math.pi * freq * t) * 0.048
                sample += math.sin(2 * math.pi * freq * 2.0 * t) * 0.004
            sample += math.sin(2 * math.pi * 783.99 * t) * pulse * (0.5 + 0.5 * math.sin(2 * math.pi * 0.13 * t))
            sample *= env * 0.62
            val = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(val.to_bytes(2, "little", signed=True))
        wf.writeframes(frames)


def make_page_015() -> None:
    base = PAGES["015"]
    images = base / "images"
    delivery = images / "delivery"
    work = images / "work"
    delivery.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    bg_map = load_backgrounds(
        work,
        [
            "015_title_bg.png",
            "015_points_bg.png",
            "015_start_bg.png",
            "015_walk_bg.png",
            "015_view_bg.png",
            "015_prep_bg.png",
            "015_choice_bg.png",
            "015_accent_01_bg.png",
            "015_accent_02_bg.png",
        ],
    )
    title = cover_crop(bg_map["015_title_bg.png"], (1600, 900), -0.10, 0.0)
    draw_lines(title, ["プールに行きたい気持ちを", "止めない"], 98, 292, [68, 86], [98, 108])
    title.save(delivery / "015_title.jpg", quality=94)
    title.save(delivery / "015_thumbnail.jpg", quality=94)
    points = cover_crop(bg_map["015_points_bg.png"], (1600, 520), -0.16, 0.0)
    draw_lines(points, ["このコラムのポイント", "› 始める前のハードル", "› 泳がなくてもいい", "› 続けやすい準備"], 100, 70, [46, 34, 34, 34], [74, 56, 56, 56])
    points.save(work / "015_points.jpg", quality=94)
    banners = [
        ("015_start_bg.png", "015_start.jpg", ["最初の壁は", "水着かも"]),
        ("015_walk_bg.png", "015_walk.jpg", ["泳がなくても", "いい"]),
        ("015_view_bg.png", "015_view.jpg", ["見られる不安を", "ほどく"]),
        ("015_prep_bg.png", "015_prep.jpg", ["準備が少ないと", "続く"]),
        ("015_choice_bg.png", "015_choice.jpg", ["大人の", "水着選び"]),
    ]
    for src, out, lines in banners:
        img = cover_crop(bg_map[src], (1600, 520), -0.18, 0.0)
        draw_lines(img, lines, 92, 148, [54, 54], [78, 72])
        img.save(delivery / out, quality=94)
    cover_crop(bg_map["015_accent_01_bg.png"], (1200, 1200), 0, 0).save(delivery / "015_accent_01.jpg", quality=94)
    cover_crop(bg_map["015_accent_02_bg.png"], (1200, 1200), 0, 0).save(delivery / "015_accent_02.jpg", quality=94)
    make_scenes(base, "015", ["015_title_bg.png", "015_start_bg.png", "015_points_bg.png", "015_walk_bg.png", "015_view_bg.png", "015_prep_bg.png"])
    make_bgm(base, "015", "calm")
    make_contact_sheet(base, "015", ["015_title.jpg", "015_points.jpg", "015_start.jpg", "015_walk.jpg", "015_view.jpg", "015_prep.jpg", "015_choice.jpg", "015_accent_01.jpg", "015_accent_02.jpg"])


def make_page_016() -> None:
    base = PAGES["016"]
    images = base / "images"
    delivery = images / "delivery"
    work = images / "work"
    delivery.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    bg_map = load_backgrounds(
        work,
        [
            "016_title_bg.png",
            "016_meeting_bg.png",
            "016_calm_bg.png",
            "016_walk_bg.png",
            "016_prep_bg.png",
            "016_strategy_bg.png",
            "016_points_bg.png",
            "016_accent_01_bg.png",
            "016_accent_02_bg.png",
        ],
    )
    title = cover_crop(bg_map["016_title_bg.png"], (1600, 900), -0.10, 0.0)
    draw_lines(title, ["水着売り場で", "固まった私へ"], 94, 292, [82, 82], [108, 108])
    title.save(delivery / "016_title.jpg", quality=94)
    title.save(delivery / "016_thumbnail.jpg", quality=94)
    points = cover_crop(bg_map["016_points_bg.png"], (1600, 520), -0.16, 0.0)
    draw_lines(points, ["このコラムのポイント", "› 売り場で始まる会議", "› 似合うより落ち着く", "› 泳がなくてもいい"], 100, 70, [46, 34, 34, 34], [74, 56, 56, 56])
    points.save(work / "016_points.jpg", quality=94)
    banners = [
        ("016_meeting_bg.png", "016_meeting.jpg", ["売り場で始まる", "会議"]),
        ("016_calm_bg.png", "016_calm.jpg", ["似合うより", "落ち着く"]),
        ("016_walk_bg.png", "016_walk.jpg", ["泳げない問題", "歩いてもいい"]),
        ("016_prep_bg.png", "016_prep.jpg", ["更衣室の段取り", "忘れ物を減らす"]),
        ("016_strategy_bg.png", "016_strategy.jpg", ["私の", "小さな作戦"]),
    ]
    for src, out, lines in banners:
        img = cover_crop(bg_map[src], (1600, 520), -0.18, 0.0)
        draw_lines(img, lines, 92, 148, [54, 54], [78, 72])
        img.save(delivery / out, quality=94)
    cover_crop(bg_map["016_accent_01_bg.png"], (1200, 1200), 0, 0).save(delivery / "016_accent_01.jpg", quality=94)
    cover_crop(bg_map["016_accent_02_bg.png"], (1200, 1200), 0, 0).save(delivery / "016_accent_02.jpg", quality=94)
    make_scenes(base, "016", ["016_title_bg.png", "016_meeting_bg.png", "016_points_bg.png", "016_walk_bg.png", "016_prep_bg.png", "016_strategy_bg.png"])
    make_bgm(base, "016", "comic")
    make_contact_sheet(base, "016", ["016_title.jpg", "016_points.jpg", "016_meeting.jpg", "016_calm.jpg", "016_walk.jpg", "016_prep.jpg", "016_strategy.jpg", "016_accent_01.jpg", "016_accent_02.jpg"])


def make_scenes(base: Path, content_no: str, files: list[str]) -> None:
    scenes = base / "video" / "scene_backgrounds"
    if scenes.exists():
        shutil.rmtree(scenes)
    scenes.mkdir(parents=True, exist_ok=True)
    for idx, name in enumerate(files, 1):
        img = Image.open(base / "images" / "work" / name).convert("RGB")
        cover_crop(img, (1200, 1200), 0, 0).save(scenes / f"{content_no}_scene{idx:02d}.jpg", quality=94)


def make_contact_sheet(base: Path, content_no: str, files: list[str]) -> None:
    sheet = Image.new("RGB", (1200, 1200), "white")
    for i, name in enumerate(files):
        path = base / "images" / "delivery" / name
        if not path.exists():
            path = base / "images" / "work" / name
        img = Image.open(path).convert("RGB")
        img.thumbnail((390, 260), Image.Resampling.LANCZOS)
        x = (i % 3) * 400 + (400 - img.width) // 2
        y = (i // 3) * 380 + 24
        sheet.paste(img, (x, y))
    sheet.save(base / "images" / "work" / f"{content_no}_contact_sheet.jpg", quality=92)


def build() -> None:
    make_page_015()
    make_page_016()


if __name__ == "__main__":
    build()
