from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "production" / "017_pool_before_weight_loss_illustrated" / "納品用"
VIDEO = BASE / "video"
SCENES = VIDEO / "scene_backgrounds"
WORK = BASE / "images" / "work"
LOGO = ROOT.parent / "ゆめはんオリジナル商品マークB.png"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

W, H = 720, 960
FPS = 30


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


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


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
    return resized.crop((left, top, left + target_w, top + target_h)).convert("RGBA")


def draw_soft_text(frame: Image.Image, lines: list[str], y: int, alpha: float = 1.0, size: int = 52, gap: int = 72) -> None:
    if not lines:
        return
    draw = ImageDraw.Draw(frame)
    font = mincho(size, True)
    a = int(255 * max(0.0, min(1.0, alpha)))
    if a <= 0:
        return
    dims = [text_size(line, font) for line in lines]
    box_w = max(w for w, _ in dims) + 82
    box_h = len(lines) * gap - (gap - max(h for _, h in dims)) + 54
    x0 = (W - box_w) // 2
    y0 = y - 28
    glow = Image.new("RGBA", (box_w + 72, box_h + 72), (255, 255, 255, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.rounded_rectangle((36, 36, 36 + box_w, 36 + box_h), radius=24, fill=(255, 255, 255, 86))
    glow = glow.filter(ImageFilter.GaussianBlur(17))
    glow.putalpha(glow.getchannel("A").point(lambda v: int(v * a / 255)))
    frame.alpha_composite(glow, (x0 - 36, y0 - 36))
    for i, line in enumerate(lines):
        w, _ = dims[i]
        draw.text(((W - w) // 2, y + i * gap), line, font=font, fill=(39, 35, 32, a))


def reveal(lines: list[str], progress: float) -> list[str]:
    p = max(0.0, min(1.0, (progress - 0.10) / 0.72))
    total = sum(len(line) for line in lines)
    count = int(total * p)
    if count <= 1:
        return []
    out = []
    for line in lines:
        take = min(len(line), count)
        if take:
            out.append(line[:take])
        count -= take
        if count <= 0:
            break
    return out


def render_panel(bg: Image.Image, progress: float, idx: int) -> Image.Image:
    p = ease(progress)
    zooms = [(1.03, 1.11), (1.08, 1.03), (1.04, 1.10), (1.10, 1.05), (1.03, 1.08), (1.08, 1.08)]
    start, end = zooms[idx]
    zoom = start + (end - start) * p
    resized = bg.resize((round(W * zoom), round(H * zoom)), Image.Resampling.LANCZOS)
    max_left = resized.width - W
    max_top = resized.height - H
    x_shift = [0, -26, 22, 34, -20, 0][idx] * (p - 0.5)
    y_shift = [0, 10, -14, 0, 12, -8][idx] * (p - 0.5)
    left = round(max(0, min(max_left, max_left / 2 + x_shift)))
    top = round(max(0, min(max_top, max_top / 2 + y_shift)))
    frame = resized.crop((left, top, left + W, top + H)).convert("RGBA")
    return frame


def draw_page_turn(frame: Image.Image, progress: float) -> None:
    if progress >= 0.20:
        return
    a = int(90 * (1 - progress / 0.20))
    overlay = Image.new("RGBA", (W, H), (255, 255, 255, a))
    frame.alpha_composite(overlay)
    draw = ImageDraw.Draw(frame)
    draw.line((42, 50, 42, H - 50), fill=(255, 255, 255, int(a * 0.7)), width=3)


def make_cover() -> Path:
    bg = cover_crop(Image.open(SCENES / "017_scene01.jpg").convert("RGB"), (W, H), 0.0, 0.0)
    veil = Image.new("RGBA", (W, H), (255, 255, 255, 72))
    bg.alpha_composite(veil)
    draw_soft_text(bg, ["痩せる前に", "プールへ行く作戦"], 378, 1.0, 48, 70)
    path = WORK / "017_story_video_cover.jpg"
    bg.convert("RGB").save(path, quality=94)
    return path


def render_frames() -> tuple[Path, int, float]:
    frames = VIDEO / "frames_story_017"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True, exist_ok=True)
    story = [
        ("017_scene01.jpg", 4.8, ["痩せたいから", "プールへ行きたい"], "type"),
        ("017_scene02.jpg", 4.1, ["でもその前に", "水着が無理"], "rise"),
        ("017_scene03.jpg", 4.2, ["そこで", "止まるの？"], "rise"),
        ("017_scene04.jpg", 4.1, ["プールは", "発表会じゃない"], "slide"),
        ("017_scene05.jpg", 4.1, ["カバーは", "始めるための工夫"], "rise"),
        ("017_scene06.jpg", 4.6, ["今の自分で", "まず一回"], "slide"),
    ]
    bgs = [cover_crop(Image.open(SCENES / bg).convert("RGB"), (W, H), 0, 0) for bg, *_ in story]
    idx = 0
    prev = None
    for scene_idx, ((_, duration, lines, mode), bg) in enumerate(zip(story, bgs)):
        total = int(duration * FPS)
        for frame_no in range(total):
            progress = frame_no / max(1, total - 1)
            frame = render_panel(bg, progress, scene_idx)
            draw_page_turn(frame, progress)
            if mode == "type":
                shown = reveal(lines, progress)
                draw_soft_text(frame, shown, 348, 1.0, 52, 72)
            else:
                p = ease(min(1.0, progress * 1.35))
                y = 372 + round((1 - p) * (28 if mode == "rise" else -20))
                draw_soft_text(frame, lines, y, min(1.0, progress * 1.8), 50, 70)
            if prev is not None and frame_no < 10:
                frame = Image.blend(prev, frame, frame_no / 10)
            frame.convert("RGB").save(frames / f"frame_{idx:04d}.jpg", quality=92)
            prev = render_panel(bg, progress, scene_idx)
            idx += 1
    return frames, idx, sum(item[1] for item in story)


def add_logo_outro(input_path: Path, duration: float) -> Path:
    logo_frame = VIDEO / "outro_logo_frame_vertical_017_story.jpg"
    canvas = Image.new("RGB", (W, H), (255, 253, 249))
    logo = Image.open(LOGO).convert("RGBA")
    target_w = 270
    target_h = round(logo.height * target_w / logo.width)
    logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
    canvas.paste(logo, ((W - target_w) // 2, (H - target_h) // 2), logo)
    canvas.save(logo_frame, quality=95)
    output = VIDEO / "opening_cm_017_vertical_story_no_cover.mp4"
    fade_start = max(0.0, duration - 1.1)
    filter_complex = (
        f"[0:v]fade=t=out:st={fade_start:.3f}:d=1.1:color=white,format=yuv420p[v0];"
        f"[0:a]afade=t=out:st={max(0.0, duration - 1.3):.3f}:d=1.3[a0];"
        "[1:v]loop=loop=57:size=1:start=0,trim=duration=1.9,"
        "fade=t=in:st=0:d=0.45,fade=t=out:st=1.55:d=0.35,format=yuv420p[v1];"
        "anullsrc=channel_layout=mono:sample_rate=44100,atrim=duration=1.9[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
    )
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(input_path),
            "-loop",
            "1",
            "-i",
            str(logo_frame),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "112k",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return output


def embed_cover(video_path: Path, cover: Path) -> Path:
    output = VIDEO / "opening_cm_017_vertical_story.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        cover_jpg = Path(tmp) / "cover.jpg"
        Image.open(cover).convert("RGB").save(cover_jpg, quality=92)
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i",
                str(video_path),
                "-i",
                str(cover_jpg),
                "-map",
                "0",
                "-map",
                "1",
                "-c",
                "copy",
                "-c:v:1",
                "mjpeg",
                "-disposition:v:1",
                "attached_pic",
                "-metadata:s:v:1",
                "title=Cover",
                "-metadata:s:v:1",
                "comment=Cover (front)",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return output


def make_preview(frames: Path, total_frames: int) -> None:
    picks = [min(total_frames - 1, int(sec * FPS)) for sec in [3.5, 6.0, 10.0, 14.2, 18.3, 22.0]]
    sheet = Image.new("RGB", (720, 640), "white")
    safe = Image.new("RGB", (600, 640), "white")
    for i, idx in enumerate(picks):
        img = Image.open(frames / f"frame_{idx:04d}.jpg").resize((240, 320), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 3) * 240, (i // 3) * 320))
        tile = img.crop((20, 0, 220, 320)).resize((200, 320), Image.Resampling.LANCZOS)
        safe.paste(tile, ((i % 3) * 200, (i // 3) * 320))
    sheet.save(VIDEO / "preview_vertical_017_story.jpg", quality=92)
    safe.save(VIDEO / "preview_vertical_017_story_safe600.jpg", quality=92)


def main() -> None:
    frames, total_frames, duration = render_frames()
    raw = VIDEO / "opening_cm_017_vertical_story_pre_logo.mp4"
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            str(frames / "frame_%04d.jpg"),
            "-i",
            str(VIDEO / "bgm_swimwear_017.wav"),
            "-af",
            "loudnorm=I=-33:LRA=7:TP=-9",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "112k",
            str(raw),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    make_preview(frames, total_frames)
    no_cover = add_logo_outro(raw, duration)
    cover = make_cover()
    output = embed_cover(no_cover, cover)
    shutil.rmtree(frames)
    print(output)
    print(cover)


if __name__ == "__main__":
    main()
