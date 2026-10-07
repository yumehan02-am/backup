from __future__ import annotations

import csv
import math
import pathlib
import shutil
import subprocess
import tempfile
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import imageio_ffmpeg


ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
PRODUCTION = ROOT / "production"
LOGO = PROJECT_ROOT / "ゆめはんオリジナル商品マークB.png"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

W, H = 720, 960
FPS = 30
GLOW_TRIM_CHARS = "。、，．！？!?・：:；;）)」』】》"
VIDEO_PUNCTUATION = "。、"
GLOW_CACHE = {}

JOBS = {
    "000": PRODUCTION / "000_absorbent_shorts_preparation" / "納品用",
    "001": PRODUCTION / "001_pelvic_floor_femcare_habit" / "納品用",
    "002": PRODUCTION / "002_underwear_exercise_realistic_pelvic_floor" / "納品用",
    "003": PRODUCTION / "003_pelvic_floor_training_illustrated" / "納品用",
    "004": PRODUCTION / "004_flat_innerwear_outfit" / "納品用",
    "005": PRODUCTION / "005_clean_clothes_not_weight_loss" / "納品用",
    "006": PRODUCTION / "006_shirt_front_float_bustline" / "納品用",
    "007": PRODUCTION / "007_posture_remember_intro" / "納品用",
    "008": PRODUCTION / "008_correction_belt_continuation" / "納品用",
    "009": PRODUCTION / "009_morning_rounded_back_innerwear" / "納品用",
    "010": PRODUCTION / "010_wide_pants_restroom_small_prep" / "納品用",
    "011": PRODUCTION / "011_floor_not_touch_pettipants" / "納品用",
    "012": PRODUCTION / "012_wide_pants_restroom_strategy_illustrated" / "納品用",
    "013": PRODUCTION / "013_pad_user_shorts_fit" / "納品用",
    "014": PRODUCTION / "014_large_pad_shorts_fit_check" / "納品用",
    "015": PRODUCTION / "015_pool_restart_swimwear" / "納品用",
    "016": PRODUCTION / "016_swimwear_shop_freeze_illustrated" / "納品用",
    "017": PRODUCTION / "017_pool_before_weight_loss_illustrated" / "納品用",
    "018": PRODUCTION / "018_pool_walking_swimwear" / "納品用",
    "019": PRODUCTION / "019_water_buoyancy_body_burden" / "納品用",
    "020": PRODUCTION / "020_water_walking_exercise_time" / "納品用",
    "021": PRODUCTION / "021_pool_day_sleep_rhythm" / "納品用",
    "022": PRODUCTION / "022_swimsuit_tag_still_attached" / "納品用",
    "023": PRODUCTION / "023_gym_pool_nobody_watching" / "納品用",
    "024": PRODUCTION / "024_cover_swimwear_preparation" / "納品用",
    "025": PRODUCTION / "025_slim_look_cover_swimwear" / "納品用",
    "026": PRODUCTION / "026_soft_hide_cover_swimwear" / "納品用",
    "027": PRODUCTION / "027_before_weight_loss_swimwear" / "納品用",
    "028": PRODUCTION / "028_belly_self_conscious_swimwear" / "納品用",
    "029": PRODUCTION / "029_poolside_set_preparation" / "納品用",
    "030": PRODUCTION / "030_family_waterplay_cover_swimwear" / "納品用",
    "031": PRODUCTION / "031_slim_or_soft_cover_swimwear" / "納品用",
}


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def mincho(size: int, bold: bool = False):
    candidates = [
        r"C:\Windows\Fonts\yumindb.ttf" if bold else r"C:\Windows\Fonts\yumin.ttf",
        r"C:\Windows\Fonts\YuMincho.ttc",
        r"C:\Windows\Fonts\meiryo.ttc",
    ]
    for path in candidates:
        if pathlib.Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_size(text: str, font) -> tuple[int, int]:
    scratch = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    box = ImageDraw.Draw(scratch).textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def sanitize_video_copy(text: str) -> str:
    text = text.replace("\\n", "\n")
    return "".join(ch for ch in text if ch not in VIDEO_PUNCTUATION)


def text_for_glow(line: str) -> str:
    stripped = line.rstrip(GLOW_TRIM_CHARS)
    return stripped or line


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


def glow_box(size: tuple[int, int], glow_rgb=(255, 255, 255), alpha=88) -> Image.Image:
    key = (size, glow_rgb, alpha)
    if key in GLOW_CACHE:
        return GLOW_CACHE[key]
    w, h = size
    pad = 22
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (*glow_rgb, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=20, fill=(*glow_rgb, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(13))
    GLOW_CACHE[key] = layer
    return layer


def draw_centered_lines(
    frame: Image.Image,
    lines: list[str],
    font,
    y: int,
    alpha: float = 1.0,
    gap: int = 76,
    fill=(43, 38, 36),
    glow=(255, 255, 255),
    center_x: int = W // 2,
) -> None:
    draw = ImageDraw.Draw(frame)
    a = int(255 * max(0.0, min(1.0, alpha)))
    if a <= 0:
        return
    items = []
    for i, line in enumerate(lines):
        w, h = text_size(line, font)
        x = center_x - w // 2
        line_y = y + i * gap
        glow_w = text_size(text_for_glow(line), font)[0] + 50
        glow_h = h + 32
        g = glow_box((glow_w, glow_h), glow, 88)
        if a < 255:
            g = g.copy()
            g.putalpha(g.getchannel("A").point(lambda v: int(v * a / 255)))
        items.append((line, x, line_y, g, glow_w))
    for _, _, line_y, g, glow_w in items:
        gx = center_x - glow_w // 2
        frame.alpha_composite(g, (gx - 22, line_y - 38))
    for line, x, line_y, _, _ in items:
        draw.text((x, line_y), line, font=font, fill=(*fill, a))


def draw_left_lines(
    frame: Image.Image,
    lines: list[str],
    font,
    x: int,
    y: int,
    alpha: float = 1.0,
    gap: int = 62,
    fill=(43, 38, 36),
    glow=(255, 255, 255),
) -> None:
    draw = ImageDraw.Draw(frame)
    a = int(255 * max(0.0, min(1.0, alpha)))
    if a <= 0:
        return
    items = []
    for i, line in enumerate(lines):
        _, h = text_size(line, font)
        line_y = y + i * gap
        glow_w = text_size(text_for_glow(line), font)[0] + 48
        glow_h = h + 30
        g = glow_box((glow_w, glow_h), glow, 86)
        if a < 255:
            g = g.copy()
            g.putalpha(g.getchannel("A").point(lambda v: int(v * a / 255)))
        items.append((line, line_y, g))
    for _, line_y, g in items:
        frame.alpha_composite(g, (x - 24, line_y - 38))
    for line, line_y, _ in items:
        draw.text((x, line_y), line, font=font, fill=(*fill, a))


def reveal_lines(lines: list[str], progress: float) -> list[str]:
    delay = 0.14
    hold = 0.24
    if progress <= delay:
        return []
    p = min(1.0, (progress - delay) / max(0.01, 1.0 - delay - hold))
    total = sum(len(line) for line in lines)
    visible = math.floor(total * p)
    if visible <= 1:
        return []
    out = []
    remaining = visible
    for line in lines:
        if remaining <= 0:
            break
        take = min(len(line), remaining)
        if take == 1 and remaining < total:
            break
        out.append(line[:take])
        remaining -= take
    return out


def render_bg(bg: Image.Image, scene_idx: int, progress: float) -> Image.Image:
    p = ease(progress)
    motions = [
        (1.05, 1.11, 0, 0),
        (1.08, 1.08, 60, 0),
        (1.04, 1.08, -40, 0),
        (1.08, 1.08, 54, -34),
        (1.07, 1.07, -62, 0),
        (1.10, 1.04, 0, 0),
    ]
    start_z, end_z, mx, my = motions[min(scene_idx, len(motions) - 1)]
    zoom = start_z + (end_z - start_z) * p
    resized = bg.resize((round(W * zoom), round(H * zoom)), Image.Resampling.LANCZOS)
    max_left = resized.width - W
    max_top = resized.height - H
    left = round(max(0, min(max_left, max_left / 2 + mx * (p - 0.5))))
    top = round(max(0, min(max_top, max_top / 2 + my * (p - 0.5))))
    return resized.crop((left, top, left + W, top + H)).convert("RGBA")


def draw_points(frame: Image.Image, lines: list[str], progress: float, row: dict[str, str]) -> None:
    title = lines[0] if lines else "このコラムのポイント"
    points = lines[1:4]
    title_font = mincho(40, True)
    point_font = mincho(36)
    center_x = int(float(row.get("text_center_x") or W // 2))
    draw_centered_lines(frame, [title], title_font, 270, 1.0, 64, center_x=center_x)
    max_w = max((text_size(point, point_font)[0] for point in points), default=360)
    point_x = int(float(row.get("point_x") or max(108, min(178, (W - max_w) // 2))))
    for i, point in enumerate(points):
        local = max(0.0, min(1.0, (progress - (0.20 + i * 0.20)) / 0.20))
        draw_left_lines(frame, [point], point_font, point_x, 350 + i * 62, local, 62)


def draw_sentence(frame: Image.Image, lines: list[str], progress: float, mode: str) -> None:
    p = ease(min(1.0, progress * 1.6))
    y = 386
    if mode in {"rise_fade", "rise"}:
        y += round((1 - p) * 34)
    elif mode in {"slide_left", "diagonal_pan"}:
        y += round((1 - p) * 18)
    elif mode in {"slide_right", "pan_left"}:
        y -= round((1 - p) * 18)
    else:
        y -= round((1 - p) * 28)
    draw_centered_lines(frame, lines, mincho(50, True), y, min(1.0, progress * 2.0), 72)


def render_scene(bg: Image.Image, row: dict[str, str], scene_idx: int, progress: float) -> Image.Image:
    frame = render_bg(bg, scene_idx, progress)
    lines = sanitize_video_copy(row.get("display_copy") or row.get("copy") or "").splitlines()
    animation = row.get("text_animation") or row.get("animation") or ""
    if scene_idx == 0:
        visible = reveal_lines(lines, progress)
        draw_centered_lines(frame, visible, mincho(54, True), 310, 1.0, 76)
    elif "points" in animation or (lines and lines[0] == "このコラムのポイント"):
        draw_points(frame, lines, progress, row)
    else:
        draw_sentence(frame, lines, progress, animation or row.get("motion", "rise"))
    return frame


def read_storyboard(base: pathlib.Path) -> list[dict[str, str]]:
    path = base / "data" / "video_storyboard.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def scene_path(base: pathlib.Path, background_file: str) -> pathlib.Path:
    scenes = base / "video" / "scene_backgrounds"
    path = scenes / background_file
    if path.exists():
        return path
    fallback = background_file.replace("scene", "").replace("__", "_")
    for root in [base / "images" / "work", base / "images" / "delivery", base / "images"]:
        candidate = root / fallback
        if candidate.exists():
            return candidate
    return base / "images" / fallback


def make_preview(frames: pathlib.Path, video: pathlib.Path, content_no: str, total_frames: int) -> None:
    picks = [min(total_frames - 1, int(sec * FPS)) for sec in [4.7, 8.0, 13.3, 16.4, 20.0, 23.4]]
    sheet = Image.new("RGB", (720, 640), "white")
    safe = Image.new("RGB", (600, 640), "white")
    for i, idx in enumerate(picks):
        img = Image.open(frames / f"frame_{idx:04d}.jpg").resize((240, 320), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 3) * 240, (i // 3) * 320))
        tile = img.crop((20, 0, 220, 320)).resize((200, 320), Image.Resampling.LANCZOS)
        safe.paste(tile, ((i % 3) * 200, (i // 3) * 320))
    sheet.save(video / f"preview_vertical_{content_no}.jpg", quality=92)
    safe.save(video / f"preview_vertical_{content_no}_safe600.jpg", quality=92)


def encode_video(base: pathlib.Path, content_no: str, duration: float) -> pathlib.Path:
    video = base / "video"
    frames = video / "frames_vertical"
    bgm_files = sorted(video.glob("bgm*.wav"))
    if not bgm_files:
        raise FileNotFoundError(f"BGM wav not found: {video}")
    no_logo = video / f"opening_cm_{content_no}_vertical_pre_logo.mp4"
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            str(frames / "frame_%04d.jpg"),
            "-i",
            str(bgm_files[0]),
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
            str(no_logo),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return add_logo_outro(base, content_no, no_logo, duration)


def add_logo_outro(base: pathlib.Path, content_no: str, input_path: pathlib.Path, duration: float) -> pathlib.Path:
    video = base / "video"
    output = video / f"opening_cm_{content_no}_vertical_no_cover.mp4"
    logo_frame = video / f"outro_logo_frame_vertical_{content_no}.jpg"
    canvas = Image.new("RGB", (W, H), (255, 253, 249))
    logo = Image.open(LOGO).convert("RGBA")
    target_w = 270
    target_h = round(logo.height * target_w / logo.width)
    logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
    canvas.paste(logo, ((W - target_w) // 2, (H - target_h) // 2), logo)
    canvas.save(logo_frame, quality=95)
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
    return embed_thumbnail(base, content_no, output)


def embed_thumbnail(base: pathlib.Path, content_no: str, input_path: pathlib.Path) -> pathlib.Path:
    output = base / "video" / f"opening_cm_{content_no}_vertical.mp4"
    thumbnail_candidates = [
        base / "images" / "delivery" / f"{content_no}_thumbnail.jpg",
        base / "images" / f"{content_no}_thumbnail.jpg",
        base / "images" / "delivery" / "thumbnail.jpg",
        base / "images" / "thumbnail.jpg",
    ]
    thumbnail = next((path for path in thumbnail_candidates if path.exists()), thumbnail_candidates[0])
    with tempfile.TemporaryDirectory() as tmp:
        cover = pathlib.Path(tmp) / "cover.jpg"
        img = Image.open(thumbnail).convert("RGB")
        img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        img.save(cover, quality=92, optimize=True)
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i",
                str(input_path),
                "-i",
                str(cover),
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


def render_job(content_no: str, base: pathlib.Path) -> pathlib.Path:
    rows = read_storyboard(base)
    video = base / "video"
    frames = video / "frames_vertical"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True, exist_ok=True)
    bgs = [
        cover_crop(
            Image.open(scene_path(base, row.get("background_file") or row.get("background"))).convert("RGB"),
            (W, H),
            float(row.get("crop_x") or 0),
            float(row.get("crop_y") or 0),
        )
        for row in rows
    ]
    idx = 0
    previous_bg = None
    transition = 12
    duration_sum = 0.0
    for scene_idx, (row, bg) in enumerate(zip(rows, bgs)):
        duration = float(row.get("duration_sec") or row.get("duration"))
        duration_sum += duration
        total = int(duration * FPS)
        for frame_no in range(total):
            progress = frame_no / max(1, total - 1)
            frame = render_scene(bg, row, scene_idx, progress)
            if previous_bg is not None and frame_no < transition:
                frame = Image.blend(previous_bg, frame, frame_no / transition)
            frame.convert("RGB").save(frames / f"frame_{idx:04d}.jpg", quality=92)
            previous_bg = render_bg(bg, scene_idx, progress)
            idx += 1
    make_preview(frames, video, content_no, idx)
    output = encode_video(base, content_no, duration_sum)
    shutil.rmtree(frames)
    return output


def main() -> None:
    targets = sys.argv[1:] or list(JOBS)
    for content_no in targets:
        base = JOBS[content_no]
        print(render_job(content_no, base))


if __name__ == "__main__":
    main()
