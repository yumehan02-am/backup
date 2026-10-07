import math
import pathlib
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import imageio_ffmpeg


BASE = pathlib.Path(__file__).resolve().parent
IMAGES = BASE / "images"
VIDEO = BASE / "video"
SCENES = VIDEO / "scene_backgrounds"
FRAMES = VIDEO / "frames_vertical_test"
LOGO = BASE.parents[2].parent / "ゆめはんオリジナル商品マークB.png"

W, H = 720, 960
FPS = 30
SAFE_X0, SAFE_X1 = 110, 610
TEXT_CENTER_X = W // 2
GLOW_TRIM_CHARS = "。、，．！？!?・：:；;）)」』】》"
GLOW_CACHE = {}


def ease(t):
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


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


def text_size(text, font):
    img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    box = ImageDraw.Draw(img).textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def text_for_glow(line):
    stripped = line.rstrip(GLOW_TRIM_CHARS)
    return stripped or line


def cover_crop(img, size, bias_x=0.0, bias_y=0.0):
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


def glow_box(size, glow_rgb=(255, 255, 255), alpha=92):
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


def draw_centered_lines(frame, lines, font, y, alpha=1.0, gap=76, fill=(43, 38, 36), glow=(255, 255, 255)):
    draw = ImageDraw.Draw(frame)
    a = int(255 * max(0.0, min(1.0, alpha)))
    if a <= 0:
        return
    items = []
    for i, line in enumerate(lines):
        w, h = text_size(line, font)
        x = TEXT_CENTER_X - w // 2
        line_y = y + i * gap
        glow_w = text_size(text_for_glow(line), font)[0] + 50
        glow_h = h + 32
        g = glow_box((glow_w, glow_h), glow, 88)
        if a < 255:
            g = g.copy()
            g.putalpha(g.getchannel("A").point(lambda v: int(v * a / 255)))
        items.append((line, x, line_y, g, glow_w))
    for _, x, line_y, g, glow_w in items:
        gx = TEXT_CENTER_X - glow_w // 2
        frame.alpha_composite(g, (gx - 22, line_y - 38))
    for line, x, line_y, _, _ in items:
        draw.text((x, line_y), line, font=font, fill=(*fill, a))


def draw_left_lines(frame, lines, font, x, y, alpha=1.0, gap=62, fill=(43, 38, 36), glow=(255, 255, 255)):
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


def reveal_lines(source_lines, progress):
    delay = 0.14
    hold = 0.24
    if progress <= delay:
        return []
    p = min(1.0, (progress - delay) / (1.0 - delay - hold))
    total = sum(len(line) for line in source_lines)
    visible = math.floor(total * p)
    if visible <= 1:
        return []
    out = []
    remaining = visible
    for line in source_lines:
        if remaining <= 0:
            break
        take = min(len(line), remaining)
        if take == 1 and remaining < total:
            break
        out.append(line[:take])
        remaining -= take
    return out


def render_bg(bg, scene_idx, progress):
    p = ease(progress)
    motions = [
        (1.05, 1.11, 0, 0),
        (1.08, 1.08, 60, 0),
        (1.04, 1.08, -40, 0),
        (1.08, 1.08, 54, -34),
        (1.07, 1.07, -62, 0),
        (1.10, 1.04, 0, 0),
    ]
    start_z, end_z, mx, my = motions[scene_idx]
    zoom = start_z + (end_z - start_z) * p
    resized = bg.resize((round(W * zoom), round(H * zoom)), Image.Resampling.LANCZOS)
    max_left = resized.width - W
    max_top = resized.height - H
    left = max_left / 2 + mx * (p - 0.5)
    top = max_top / 2 + my * (p - 0.5)
    left = round(max(0, min(max_left, left)))
    top = round(max(0, min(max_top, top)))
    return resized.crop((left, top, left + W, top + H)).convert("RGBA")


def draw_points(frame, progress):
    draw_centered_lines(frame, ["このコラムのポイント"], mincho(40, True), 270, 1.0, 64)
    points = ["› 日常向けの吸水量", "› パッドとの使い分け", "› 外出前の安心"]
    point_x = 178
    for i, point in enumerate(points):
        local = max(0.0, min(1.0, (progress - (0.20 + i * 0.20)) / 0.20))
        draw_left_lines(frame, [point], mincho(36), point_x, 350 + i * 62, local, 62)


def draw_sentence(frame, lines, progress, mode):
    p = ease(min(1.0, progress * 1.6))
    y = 386
    if mode == "rise":
        y += round((1 - p) * 34)
    elif mode == "drop":
        y -= round((1 - p) * 28)
    draw_centered_lines(frame, lines, mincho(50, True), y, min(1.0, progress * 2.0), 72)


def render_scene(bg, scene_idx, progress):
    frame = render_bg(bg, scene_idx, progress)
    if scene_idx == 0:
        lines = reveal_lines(["尿もれ対策を", "ふつうの", "準備に。"], progress)
        draw_centered_lines(frame, lines, mincho(54, True), 310, 1.0, 76)
    elif scene_idx == 1:
        draw_sentence(frame, ["こっそり悩む朝に、", "選択肢を。"], progress, "rise")
    elif scene_idx == 2:
        draw_points(frame, progress)
    elif scene_idx == 3:
        draw_sentence(frame, ["20cc・30ccは、", "日常の念のために。"], progress, "drop")
    elif scene_idx == 4:
        draw_sentence(frame, ["パッドだけが正解、", "ではありません。"], progress, "rise")
    else:
        draw_sentence(frame, ["いつもの私で、", "出かけられる。"], progress, "drop")
    return frame


def make_frames():
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)
    scene_files = ["000_scene01.jpg", "000_scene02.jpg", "000_scene03.jpg", "000_scene04.jpg", "000_scene05.jpg", "000_scene06.jpg"]
    fallbacks = ["01_title.jpg", "02_morning.jpg", "03_points.jpg", "04_capacity.jpg", "05_choice.jpg", "06_closing.jpg"]
    durations = [5.8, 3.8, 4.5, 3.8, 3.7, 4.0]
    bgs = []
    for primary, fallback in zip(scene_files, fallbacks):
        src = SCENES / primary
        if not src.exists():
            src = SCENES / fallback
        bgs.append(cover_crop(Image.open(src).convert("RGB"), (W, H)))

    idx = 0
    previous_bg = None
    transition = 12
    for scene_idx, (bg, duration) in enumerate(zip(bgs, durations)):
        total = int(duration * FPS)
        for frame_no in range(total):
            progress = frame_no / max(1, total - 1)
            frame = render_scene(bg, scene_idx, progress)
            if previous_bg is not None and frame_no < transition:
                frame = Image.blend(previous_bg, frame, frame_no / transition)
            frame.convert("RGB").save(FRAMES / f"frame_{idx:04d}.jpg", quality=92)
            previous_bg = render_bg(bg, scene_idx, progress)
            idx += 1
    make_preview(idx)
    return sum(durations)


def make_preview(total_frames):
    picks = [min(total_frames - 1, int(sec * FPS)) for sec in [4.7, 8.0, 13.3, 16.4, 20.0, 23.4]]
    sheet = Image.new("RGB", (720, 640), "white")
    for i, idx in enumerate(picks):
        img = Image.open(FRAMES / f"frame_{idx:04d}.jpg").resize((240, 320), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 3) * 240, (i // 3) * 320))
    sheet.save(VIDEO / "preview_vertical_test_000.jpg", quality=92)


def add_logo_outro(input_path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    output_path = VIDEO / "opening_cm_000_vertical_test_no_cover.mp4"
    logo_frame = VIDEO / "outro_logo_frame_vertical_test.jpg"
    canvas = Image.new("RGB", (W, H), (255, 253, 249))
    logo = Image.open(LOGO).convert("RGBA")
    target_w = 270
    target_h = round(logo.height * target_w / logo.width)
    logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
    canvas.paste(logo, ((W - target_w) // 2, (H - target_h) // 2), logo)
    canvas.save(logo_frame, quality=95)

    duration = 25.6
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
            ffmpeg,
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
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return output_path


def embed_thumbnail(video_path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out = VIDEO / "opening_cm_000_vertical_test.mp4"
    cover_src = IMAGES / "000_thumbnail.jpg"
    with tempfile.TemporaryDirectory() as tmp:
        cover = pathlib.Path(tmp) / "cover.jpg"
        img = Image.open(cover_src).convert("RGB")
        img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        img.save(cover, quality=92, optimize=True)
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(video_path),
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
                str(out),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return out


def encode_video(duration):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    src_audio = VIDEO / "bgm_apparel_soft_000.wav"
    no_logo = VIDEO / "opening_cm_000_vertical_test_pre_logo.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            str(FRAMES / "frame_%04d.jpg"),
            "-i",
            str(src_audio),
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
    shutil.rmtree(FRAMES)
    return embed_thumbnail(add_logo_outro(no_logo))


def main():
    duration = make_frames()
    print(encode_video(duration))


if __name__ == "__main__":
    main()
