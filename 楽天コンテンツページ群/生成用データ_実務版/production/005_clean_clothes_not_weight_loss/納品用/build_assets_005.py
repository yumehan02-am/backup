import csv
import math
import pathlib
import shutil
import subprocess
import tempfile
import wave

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import imageio_ffmpeg


BASE = pathlib.Path(__file__).resolve().parent
DATA = BASE / "data"
IMAGES = BASE / "images"
VIDEO = BASE / "video"
SCENES = VIDEO / "scene_backgrounds"
FRAMES = VIDEO / "frames"
LOGO = BASE.parents[2].parent / "ゆめはんオリジナル商品マークB.png"

GENERATED = pathlib.Path(r"C:\Users\i58400am\.codex\generated_images\01a03bd9-3f16-70d1-81ca-80d9bbc91430")
SOURCE_MAP = {
    "005_title.jpg": "call_44JdJYU700UpoDIhvp0IDrAF.png",
    "005_silhouette.jpg": "call_TAyzHapIid91tMZ6ilUJk1ap.png",
    "005_focus.jpg": "call_qUQy4sZAGhp8wqmCnDPKHuQT.png",
    "005_drape.jpg": "call_hJFQUDS1QcoOpVLADp0l5VyR.png",
    "005_choice.jpg": "call_zZx2Rgzp3woD03Hb1teqGVCG.png",
    "005_closing.jpg": "call_qmn7daWiUCkZRd0EAT08EZI3.png",
    "005_thumbnail_bg.jpg": "call_44JdJYU700UpoDIhvp0IDrAF.png",
}

GLOW_TRIM_CHARS = "。、，．！？!?・：:；;）)」』】》"
GLOW_CACHE = {}


def ease_in_out(t):
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


def gothic(size):
    candidates = [r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\meiryo.ttc"]
    for path in candidates:
        if pathlib.Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_bbox(text, font):
    scratch = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    return ImageDraw.Draw(scratch).textbbox((0, 0), text, font=font)


def text_size(text, font):
    box = text_bbox(text, font)
    return box[2] - box[0], box[3] - box[1]


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


def fix_orphan_punctuation(lines):
    fixed = []
    for line in lines:
        if fixed and line and all(ch in GLOW_TRIM_CHARS for ch in line):
            fixed[-1] += line
        elif fixed and line and line[0] in GLOW_TRIM_CHARS:
            fixed[-1] += line[0]
            if line[1:]:
                fixed.append(line[1:])
        else:
            fixed.append(line)
    return fixed


def wrap_text(text, font, max_width, max_lines=2):
    preferred = ["、", "。", "｜", "と", "で", "に", "を", "も", "へ"]
    lines = []
    line = ""
    for char in text:
        trial = line + char
        if text_size(trial, font)[0] <= max_width or not line:
            line = trial
            continue
        cut = -1
        for mark in preferred:
            pos = line.rfind(mark)
            if pos >= max(2, len(line) // 2):
                cut = pos + 1
                break
        if cut > 0:
            lines.append(line[:cut])
            line = line[cut:] + char
        else:
            lines.append(line)
            line = char
    if line:
        lines.append(line)
    return fix_orphan_punctuation(lines[:max_lines])


def fit_font_one_line(text, start_size, max_width, bold=True, min_size=34):
    size = start_size
    while size >= min_size:
        font = mincho(size, bold)
        if text_size(text, font)[0] <= max_width:
            return font
        size -= 2
    return mincho(size, bold)


def sample_luminance(img, area):
    x, y, w, h = area
    crop = img.convert("RGB").crop((x, y, min(img.width, x + w), min(img.height, y + h))).resize((1, 1))
    r, g, b = crop.getpixel((0, 0))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def fill_for_bg(img, area, alpha=248):
    return (43, 38, 36, alpha) if sample_luminance(img, area) > 124 else (255, 252, 247, alpha)


def glow_rgb_for_fill(fill):
    return (255, 255, 255) if fill[0] < 120 else (36, 32, 30)


def text_for_glow(line):
    stripped = line.rstrip(GLOW_TRIM_CHARS)
    return stripped or line


def draw_soft_glow_text(img, xy, text, font, fill, glow_strength=0.58):
    draw = ImageDraw.Draw(img)
    x, y = xy
    glow_text = text_for_glow(text)
    bbox = draw.textbbox((x, y), glow_text, font=font)
    pad = 86
    w = max(1, bbox[2] - bbox[0] + pad * 2)
    h = max(1, bbox[3] - bbox[1] + pad * 2)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.text((pad + x - bbox[0], pad + y - bbox[1]), glow_text, font=font, fill=255)
    alpha = mask.filter(ImageFilter.MaxFilter(21)).filter(ImageFilter.GaussianBlur(18))
    alpha = alpha.point(lambda v: min(150, int(v * glow_strength)))
    glow = Image.new("RGBA", (w, h), (*glow_rgb_for_fill(fill), 0))
    glow.putalpha(alpha)
    img.alpha_composite(glow, (bbox[0] - pad, bbox[1] - pad))
    draw.text((x, y), text, font=font, fill=fill)


def prepare_images():
    IMAGES.mkdir(parents=True, exist_ok=True)
    SCENES.mkdir(parents=True, exist_ok=True)
    for out_name, source_name in SOURCE_MAP.items():
        src = GENERATED / source_name
        if not src.exists():
            raise FileNotFoundError(src)
        Image.open(src).convert("RGB").save(IMAGES / out_name, quality=95)

    scene_order = [
        ("005_scene01.jpg", "005_title.jpg", -0.20, 0.0),
        ("005_scene02.jpg", "005_silhouette.jpg", -0.10, 0.0),
        ("005_scene03.jpg", "005_focus.jpg", -0.20, 0.0),
        ("005_scene04.jpg", "005_drape.jpg", -0.18, 0.0),
        ("005_scene05.jpg", "005_choice.jpg", -0.18, 0.0),
        ("005_scene06.jpg", "005_closing.jpg", -0.22, 0.0),
    ]
    for scene_name, src_name, bx, by in scene_order:
        cover_crop(Image.open(IMAGES / src_name).convert("RGB"), (1080, 1080), bx, by).save(SCENES / scene_name, quality=94)


def make_banners():
    for row in csv.DictReader((DATA / "banner_plan.csv").open(encoding="utf-8-sig")):
        path = IMAGES / row["file_name"]
        img = cover_crop(Image.open(path).convert("RGB"), (1600, 520), -0.12, 0).convert("RGBA")
        title_font = fit_font_one_line(row["overlay_title"], 58, 1220, True)
        body_font = gothic(30)
        x, y = 82, 112
        fill = fill_for_bg(img, (x, y, 1220, 230))
        draw_soft_glow_text(img, (x, y), row["overlay_title"], title_font, fill, 0.62)
        y += 86
        for line in wrap_text(row["overlay_body"], body_font, 900, 2):
            draw_soft_glow_text(img, (x, y), line, body_font, fill, 0.52)
            y += 43
        img.convert("RGB").save(path, quality=94)


def make_thumbnail():
    bg = cover_crop(Image.open(IMAGES / "005_thumbnail_bg.jpg").convert("RGB"), (1600, 900), -0.24, 0).convert("RGBA")
    fill = (43, 38, 36, 252)
    x = 82
    y = 164
    main_lines = ["「痩せた？」ではなく、", "服がすっきり見える。"]
    sub_line = "下着とシルエットの話"
    main_font = fit_font_one_line(max(main_lines, key=len), 84, 940, True, 56)
    sub_font = fit_font_one_line(sub_line, 46, 840, False, 34)
    for i, line in enumerate(main_lines):
        draw_soft_glow_text(bg, (x, y + i * 108), line, main_font, fill, 0.66)
    draw_soft_glow_text(bg, (x + 4, y + 250), sub_line, sub_font, fill, 0.56)
    bg.convert("RGB").save(IMAGES / "005_thumbnail.jpg", quality=94)


def make_banner_contact_sheet():
    names = [
        "005_title.jpg",
        "005_silhouette.jpg",
        "005_focus.jpg",
        "005_drape.jpg",
        "005_choice.jpg",
        "005_closing.jpg",
    ]
    sheet = Image.new("RGB", (800, 390), "white")
    for i, name in enumerate(names):
        img = Image.open(IMAGES / name).resize((400, 130), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 2) * 400, (i // 2) * 130))
    sheet.save(IMAGES / "005_banner_contact_sheet.jpg", quality=92)


def video_style_for_scene(scene_idx):
    return (43, 38, 36), (255, 255, 255)


def glow_box(size, glow_rgb=(255, 255, 255), alpha=94):
    w, h = size
    key = (w, h, glow_rgb, alpha)
    if key in GLOW_CACHE:
        return GLOW_CACHE[key]
    pad = 24
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (*glow_rgb, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=22, fill=(*glow_rgb, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(13))
    GLOW_CACHE[key] = layer
    return layer


def draw_text_with_glowbox(frame, xy, text, font, progress=1.0, line_gap=90, style=None):
    x, y = xy
    alpha = int(255 * max(0, min(1, progress)))
    if alpha <= 0:
        return
    draw = ImageDraw.Draw(frame)
    text_rgb, glow_rgb = style or ((43, 38, 36), (255, 255, 255))
    items = []
    for i, line in enumerate(text.split("\n")):
        if not line:
            continue
        glow_line = text_for_glow(line)
        gw_text, gh = text_size(glow_line, font)
        gx = x - 26
        gy = y + i * line_gap - 16
        gw = gw_text + 52
        gh = gh + 32
        glow = glow_box((gw, gh), glow_rgb, 88 if gw_text > 300 else 78)
        if alpha < 255:
            glow = glow.copy()
            glow.putalpha(glow.getchannel("A").point(lambda v: int(v * alpha / 255)))
        items.append((line, gx, gy, glow, i))
    for _, gx, gy, glow, _ in items:
        frame.alpha_composite(glow, (gx - 24, gy - 24))
    for line, _, _, _, i in items:
        draw.text((x, y + i * line_gap), line, font=font, fill=(*text_rgb, alpha))


def typewriter(frame, xy, text, font, progress, style):
    start_delay = 0.13
    end_hold = 0.25
    if progress <= start_delay:
        return
    p = min(1.0, (progress - start_delay) / max(0.01, 1.0 - start_delay - end_hold))
    source_lines = text.split("\n")
    total_chars = sum(len(line) for line in source_lines)
    visible = max(0, math.floor(total_chars * p))
    if visible <= 1:
        return
    rendered_lines = []
    remaining = visible
    for line in source_lines:
        if remaining <= 0:
            break
        take = min(len(line), remaining)
        if take == 1 and remaining < total_chars:
            break
        rendered_lines.append(line[:take])
        remaining -= take
    if rendered_lines:
        draw_text_with_glowbox(frame, xy, "\n".join(rendered_lines), font, 1.0, 96, style)


def draw_points(frame, progress, style):
    title_font = mincho(48, True)
    point_font = mincho(42)
    x, y = 58, 250
    draw_text_with_glowbox(frame, (x, y), "このコラムのポイント", title_font, 1.0, 88, style)
    points = ["› 布の張り", "› 視線の集まり方", "› 盛らない選択"]
    for i, line in enumerate(points):
        local = max(0.0, min(1.0, (progress - (0.20 + i * 0.21)) / 0.20))
        draw_text_with_glowbox(frame, (x + 8, y + 104 + i * 72), line, point_font, local, 72, style)


def draw_sentence(frame, text, progress, mode, style):
    x, y = 70, 354
    eased = ease_in_out(min(1.0, progress * 1.5))
    if mode == "slide_left":
        x -= round((1 - eased) * 58)
    elif mode == "slide_right":
        x += round((1 - eased) * 58)
    elif mode == "rise":
        y += round((1 - eased) * 38)
    elif mode == "soft_drop":
        y -= round((1 - eased) * 32)
    draw_text_with_glowbox(frame, (x, y), text, mincho(70, True), min(1.0, progress * 2.1), 90, style)


def render_background(bg, scene_idx, progress):
    p = ease_in_out(progress)
    motion = [
        {"start_zoom": 1.035, "end_zoom": 1.092, "x": 0, "y": 0},
        {"start_zoom": 1.062, "end_zoom": 1.062, "x": 82, "y": 0},
        {"start_zoom": 1.040, "end_zoom": 1.078, "x": -64, "y": 0},
        {"start_zoom": 1.068, "end_zoom": 1.068, "x": 72, "y": -42},
        {"start_zoom": 1.060, "end_zoom": 1.060, "x": -86, "y": 0},
        {"start_zoom": 1.090, "end_zoom": 1.036, "x": 0, "y": 0},
    ][scene_idx]
    zoom = motion["start_zoom"] + (motion["end_zoom"] - motion["start_zoom"]) * p
    resized = bg.resize((round(1080 * zoom), round(1080 * zoom)), Image.Resampling.LANCZOS)
    max_left = resized.width - 1080
    max_top = resized.height - 1080
    left = max_left / 2 + motion["x"] * (p - 0.5)
    top = max_top / 2 + motion["y"] * (p - 0.5)
    left = round(max(0, min(max_left, left)))
    top = round(max(0, min(max_top, top)))
    return resized.crop((left, top, left + 1080, top + 1080)).convert("RGBA")


def render_scene(bg, scene_idx, progress):
    frame = render_background(bg, scene_idx, progress)
    style = video_style_for_scene(scene_idx)
    if scene_idx == 0:
        typewriter(frame, (62, 318), "「痩せた？」ではなく、\n服がすっきり見える。", mincho(66, True), progress, style)
    elif scene_idx == 1:
        draw_sentence(frame, "なぜ上半身が\n重く見えるのか。", progress, "rise", style)
    elif scene_idx == 2:
        draw_points(frame, progress, style)
    elif scene_idx == 3:
        draw_sentence(frame, "体ではなく、\n服の線を見る。", progress, "slide_left", style)
    elif scene_idx == 4:
        draw_sentence(frame, "盛る日も、\n盛らない日も。", progress, "slide_right", style)
    else:
        draw_sentence(frame, "好きな服を、\nもう少し気楽に。", progress, "soft_drop", style)
    return frame


def make_bgm(duration):
    out = VIDEO / "bgm_illustrated_fashion_column_005.wav"
    rate = 44100
    chords = [
        (246.94, 311.13, 392.00),
        (277.18, 349.23, 440.00),
        (220.00, 293.66, 369.99),
        (261.63, 329.63, 415.30),
    ]
    with wave.open(str(out), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(int(duration * rate)):
            t = i / rate
            chord = chords[int(t / 2.4) % len(chords)]
            pulse = 0.82 + 0.18 * math.sin(2 * math.pi * 0.35 * t)
            sample = 0.0
            for n, freq in enumerate(chord):
                sample += math.sin(2 * math.pi * freq * t) * (0.018 / (n + 1))
                sample += math.sin(2 * math.pi * freq * 2.0 * t) * 0.0025
            sample += math.sin(2 * math.pi * 587.33 * t) * 0.003 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.13 * t))
            sample *= pulse
            frames += int(max(-1, min(1, sample)) * 32767).to_bytes(2, "little", signed=True)
        wf.writeframes(frames)
    return out


def make_preview(total_frames):
    seconds = [4.7, 8.0, 13.7, 16.2, 20.0, 23.6]
    picks = [min(total_frames - 1, int(sec * 30)) for sec in seconds]
    sheet = Image.new("RGB", (810, 540), "white")
    for i, idx in enumerate(picks):
        path = FRAMES / f"frame_{idx:04d}.jpg"
        img = Image.open(path).resize((270, 270), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 3) * 270, (i // 3) * 270))
    sheet.save(VIDEO / "preview_contact_sheet_005.jpg", quality=92)


def make_motion_check(total_frames):
    seconds = [0.8, 2.9, 5.5, 9.6, 14.2, 18.0, 22.5, 25.0]
    picks = [min(total_frames - 1, int(sec * 30)) for sec in seconds]
    sheet = Image.new("RGB", (1080, 540), "white")
    for i, idx in enumerate(picks):
        path = FRAMES / f"frame_{idx:04d}.jpg"
        img = Image.open(path).resize((270, 270), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 4) * 270, (i // 4) * 270))
    sheet.save(VIDEO / "motion_check_sheet_005.jpg", quality=92)


def make_frames():
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)
    scene_files = [
        "005_scene01.jpg",
        "005_scene02.jpg",
        "005_scene03.jpg",
        "005_scene04.jpg",
        "005_scene05.jpg",
        "005_scene06.jpg",
    ]
    durations = [5.8, 3.8, 4.8, 3.8, 3.8, 4.2]
    fps = 30
    transition_frames = 12
    bgs = [Image.open(SCENES / name).convert("RGB") for name in scene_files]
    idx = 0
    previous_background = None
    for sidx, (bg, duration) in enumerate(zip(bgs, durations)):
        total = int(duration * fps)
        for frame_no in range(total):
            progress = frame_no / max(1, total - 1)
            frame = render_scene(bg, sidx, progress)
            if previous_background is not None and frame_no < transition_frames:
                frame = Image.blend(previous_background, frame, frame_no / transition_frames)
            frame.convert("RGB").save(FRAMES / f"frame_{idx:04d}.jpg", quality=92)
            previous_background = render_background(bg, sidx, progress)
            idx += 1
    make_preview(idx)
    make_motion_check(idx)
    return sum(durations)


def encode_video(bgm):
    out = VIDEO / "opening_cm_005_pre_logo.mp4"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate",
            "30",
            "-i",
            str(FRAMES / "frame_%04d.jpg"),
            "-i",
            str(bgm),
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
            str(out),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    shutil.rmtree(FRAMES)
    return out


def make_logo_frame(out_path):
    canvas = Image.new("RGB", (1080, 1080), (255, 253, 249))
    logo = Image.open(LOGO).convert("RGBA")
    target_w = 390
    target_h = round(logo.height * target_w / logo.width)
    logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
    x = (canvas.width - target_w) // 2
    y = (canvas.height - target_h) // 2
    canvas.paste(logo, (x, y), logo)
    canvas.save(out_path, quality=95)


def duration_seconds(path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path), "-f", "null", "-"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in result.stderr.splitlines():
        if "Duration:" not in line:
            continue
        token = line.split("Duration:", 1)[1].split(",", 1)[0].strip()
        h, m, s = token.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"Could not read duration: {path}")


def add_logo_outro(input_path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    output_path = VIDEO / "opening_cm_005.mp4"
    tmp = VIDEO / "opening_cm_005_with_logo_tmp.mp4"
    logo_frame = VIDEO / "outro_logo_frame.jpg"
    make_logo_frame(logo_frame)
    duration = duration_seconds(input_path)
    video_fade_start = max(0.0, duration - 1.1)
    audio_fade_start = max(0.0, duration - 1.3)
    filter_complex = (
        f"[0:v]fade=t=out:st={video_fade_start:.3f}:d=1.1:color=white,format=yuv420p[v0];"
        f"[0:a]afade=t=out:st={audio_fade_start:.3f}:d=1.3[a0];"
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
            str(tmp),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    tmp.replace(output_path)
    return output_path


def make_cover_jpeg(src, dst):
    image = Image.open(src).convert("RGB")
    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    image.save(dst, "JPEG", quality=92, optimize=True)


def embed_thumbnail(video_path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    thumbnail_path = IMAGES / "005_thumbnail.jpg"
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = pathlib.Path(tmp_dir)
        cover_jpg = tmp_dir_path / "cover.jpg"
        tmp_output = tmp_dir_path / "opening_cm_005_cover.mp4"
        make_cover_jpeg(thumbnail_path, cover_jpg)
        subprocess.run(
            [
                ffmpeg,
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
                str(tmp_output),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        shutil.copy2(video_path, VIDEO / "opening_cm_005_pre_cover.mp4")
        shutil.copy2(tmp_output, video_path)


def main():
    prepare_images()
    make_banners()
    make_thumbnail()
    make_banner_contact_sheet()
    duration = make_frames()
    bgm = make_bgm(duration)
    pre_logo = encode_video(bgm)
    final_video = add_logo_outro(pre_logo)
    embed_thumbnail(final_video)
    print(final_video)


if __name__ == "__main__":
    main()
