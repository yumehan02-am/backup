from __future__ import annotations

import math
import shutil
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "production" / "017_pool_before_weight_loss_illustrated" / "納品用"
IMAGES = BASE / "images"
DELIVERY = IMAGES / "delivery"
WORK = IMAGES / "work"
VIDEO = BASE / "video"


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


def load_backgrounds(names: list[str]) -> dict[str, Image.Image]:
    missing = [name for name in names if not (WORK / name).exists()]
    if missing:
        raise FileNotFoundError(
            "納品画像・動画背景は個別生成が必須です。素材シートからの切り出しは禁止です。"
            f"不足背景: {', '.join(missing)}"
        )
    return {name: Image.open(WORK / name).convert("RGB") for name in names}


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


def make_bgm() -> None:
    VIDEO.mkdir(parents=True, exist_ok=True)
    path = VIDEO / "bgm_swimwear_017.wav"
    sr = 44100
    duration = 30.0
    chords = [(392.00, 493.88, 587.33), (349.23, 440.00, 523.25), (329.63, 415.30, 493.88), (392.00, 523.25, 659.25)]
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
                sample += math.sin(2 * math.pi * freq * t) * 0.046
                sample += math.sin(2 * math.pi * freq * 2.0 * t) * 0.004
            sample += math.sin(2 * math.pi * 783.99 * t) * 0.012 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.12 * t))
            sample *= env * 0.62
            val = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(val.to_bytes(2, "little", signed=True))
        wf.writeframes(frames)


def make_scenes(files: list[str]) -> None:
    scenes = VIDEO / "scene_backgrounds"
    if scenes.exists():
        shutil.rmtree(scenes)
    scenes.mkdir(parents=True, exist_ok=True)
    for idx, name in enumerate(files, 1):
        cover_crop(Image.open(WORK / name).convert("RGB"), (1200, 1200), 0, 0).save(scenes / f"017_scene{idx:02d}.jpg", quality=94)


def make_contact_sheet(files: list[str]) -> None:
    sheet = Image.new("RGB", (1200, 1200), "white")
    for i, name in enumerate(files):
        path = DELIVERY / name
        if not path.exists():
            path = WORK / name
        img = Image.open(path).convert("RGB")
        img.thumbnail((390, 260), Image.Resampling.LANCZOS)
        x = (i % 3) * 400 + (400 - img.width) // 2
        y = (i // 3) * 380 + 24
        sheet.paste(img, (x, y))
    sheet.save(WORK / "017_contact_sheet.jpg", quality=92)


def build() -> None:
    DELIVERY.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    bg_map = load_backgrounds(
        [
            "017_title_bg.png",
            "017_dilemma_bg.png",
            "017_assumption_bg.png",
            "017_not_stage_bg.png",
            "017_cover_bg.png",
            "017_strategy_bg.png",
            "017_points_bg.png",
            "017_accent_01_bg.png",
            "017_accent_02_bg.png",
        ]
    )

    title = cover_crop(bg_map["017_title_bg.png"], (1600, 900), -0.05, 0.0)
    draw_lines(title, ["痩せてからプールに行くつもりが", "まだ水着を買えていない話"], 84, 278, [60, 60], [90, 86])
    title.save(DELIVERY / "017_title.jpg", quality=94)
    title.save(DELIVERY / "017_thumbnail.jpg", quality=94)

    points = cover_crop(bg_map["017_points_bg.png"], (1600, 520), -0.16, 0.0)
    draw_lines(points, ["このコラムのポイント", "› 先に痩せたい問題", "› 水着の思い込み", "› 今の自分で行く作戦"], 100, 70, [46, 34, 34, 34], [74, 56, 56, 56])
    points.save(WORK / "017_points.jpg", quality=94)

    banners = [
        ("017_dilemma_bg.png", "017_dilemma.jpg", ["先に痩せたい", "問題"]),
        ("017_assumption_bg.png", "017_assumption.jpg", ["ぴったりだけが", "水着じゃない"]),
        ("017_not_stage_bg.png", "017_not_stage.jpg", ["プールは", "発表会ではない"]),
        ("017_cover_bg.png", "017_cover.jpg", ["カバーは", "始めるための準備"]),
        ("017_strategy_bg.png", "017_strategy.jpg", ["今の自分で", "行く作戦"]),
    ]
    for src, out, lines in banners:
        img = cover_crop(bg_map[src], (1600, 520), -0.12, 0.0)
        draw_lines(img, lines, 92, 148, [54, 54], [78, 72])
        img.save(DELIVERY / out, quality=94)

    cover_crop(bg_map["017_accent_01_bg.png"], (1200, 1200), 0, 0).save(DELIVERY / "017_accent_01.jpg", quality=94)
    cover_crop(bg_map["017_accent_02_bg.png"], (1200, 1200), 0, 0).save(DELIVERY / "017_accent_02.jpg", quality=94)
    make_scenes(["017_title_bg.png", "017_dilemma_bg.png", "017_points_bg.png", "017_not_stage_bg.png", "017_cover_bg.png", "017_strategy_bg.png"])
    make_bgm()
    make_contact_sheet(["017_title.jpg", "017_points.jpg", "017_dilemma.jpg", "017_assumption.jpg", "017_not_stage.jpg", "017_cover.jpg", "017_strategy.jpg", "017_accent_01.jpg", "017_accent_02.jpg"])


if __name__ == "__main__":
    build()
