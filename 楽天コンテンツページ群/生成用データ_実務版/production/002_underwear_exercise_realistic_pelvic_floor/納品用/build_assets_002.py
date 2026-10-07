import csv
import math
import pathlib
import shutil
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import imageio_ffmpeg


BASE = pathlib.Path(__file__).resolve().parent
DATA = BASE / "data"
IMAGES = BASE / "images"
VIDEO = BASE / "video"
SCENES = VIDEO / "scene_backgrounds"
FRAMES = VIDEO / "frames"

GENERATED = pathlib.Path(r"C:\Users\i58400am\.codex\generated_images\01a03bd9-3f16-70d1-81ca-80d9bbc91430")
SOURCE_MAP = {
    "002_title.jpg": "call_owr1sFHyJKTPPD1QxVwwz6WG.png",
    "002_reality.jpg": "call_KwsrUPqtP9gaiiXc28vyfW0T.png",
    "002_underwear.jpg": "call_V6Co5oVSYXtjzNEqlG7sve82.png",
    "002_exercise.jpg": "call_hdIdY8LMC9XhnLBHnWGV81Vh.png",
    "002_balance.jpg": "call_tQnKq3FZKElDAmViica2NeTO.png",
    "002_continue.jpg": "call_2LwO8seeok1XIzpPkd4lCmRE.png",
    "002_closing.jpg": "call_4U97h8NKeWct16m2KUMxl3cA.png",
    "002_thumbnail_bg.jpg": "call_KmB9UjVHAWSEae4vI7MrnDSt.png",
    "002_scene01_bg.jpg": "call_62K0UCeqpJVZgs1jomPgMHsv.png",
    "002_knowledge.jpg": "call_9uy9rMR9Y911gLo9REvglWQz.png",
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
    draw = ImageDraw.Draw(scratch)
    return draw.textbbox((0, 0), text, font=font)


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
        ("002_scene01.jpg", "002_scene01_bg.jpg", -0.18, 0.0),
        ("002_scene02.jpg", "002_reality.jpg", -0.14, 0.0),
        ("002_scene03.jpg", "002_balance.jpg", -0.20, 0.0),
        ("002_scene04.jpg", "002_underwear.jpg", -0.16, 0.0),
        ("002_scene05.jpg", "002_exercise.jpg", -0.14, 0.0),
        ("002_scene06.jpg", "002_closing.jpg", -0.18, 0.0),
    ]
    for scene_name, src_name, bx, by in scene_order:
        cover_crop(Image.open(IMAGES / src_name).convert("RGB"), (1080, 1080), bx, by).save(SCENES / scene_name, quality=94)


def make_banners():
    for row in csv.DictReader((DATA / "banner_plan.csv").open(encoding="utf-8-sig")):
        path = IMAGES / row["file_name"]
        img = cover_crop(Image.open(path).convert("RGB"), (1600, 520), -0.10, 0).convert("RGBA")
        title_font = fit_font_one_line(row["overlay_title"], 58, 1220, True)
        body_font = gothic(30)
        x, y = 82, 116
        fill = fill_for_bg(img, (x, y, 1220, 210))
        draw_soft_glow_text(img, (x, y), row["overlay_title"], title_font, fill, 0.60)
        y += 86
        for line in wrap_text(row["overlay_body"], body_font, 900, 2):
            draw_soft_glow_text(img, (x, y), line, body_font, fill, 0.50)
            y += 43
        img.convert("RGB").save(path, quality=94)


def make_thumbnail():
    bg = cover_crop(Image.open(IMAGES / "002_thumbnail_bg.jpg").convert("RGB"), (1600, 900), -0.18, 0).convert("RGBA")
    fill = (43, 38, 36, 252)
    x = 92
    y = 226
    main_lines = ["下着でできること、", "運動でできること。"]
    sub_line = "骨盤底筋ケアの現実的な話"
    main_font = fit_font_one_line(max(main_lines, key=len), 94, 810, True, 58)
    sub_font = fit_font_one_line(sub_line, 48, 840, False, 34)
    for i, line in enumerate(main_lines):
        draw_soft_glow_text(bg, (x, y + i * 116), line, main_font, fill, 0.64)
    draw_soft_glow_text(bg, (x + 4, y + 270), sub_line, sub_font, fill, 0.54)
    bg.convert("RGB").save(IMAGES / "002_thumbnail.jpg", quality=94)


def video_style_for_scene(scene_idx):
    # Scene-level fixed style: no mid-scene color changes during pan/crossfade.
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
        full_w, _ = text_size(line, font)
        gx = x - 26
        gy = y + i * line_gap - 16
        gw = gw_text + 52
        gh = gh + 32
        glow = glow_box((gw, gh), glow_rgb, 88 if gw_text > 300 else 78)
        if alpha < 255:
            glow = glow.copy()
            glow.putalpha(glow.getchannel("A").point(lambda v: int(v * alpha / 255)))
        items.append((line, full_w, gx, gy, glow, i))
    for _, _, gx, gy, glow, _ in items:
        frame.alpha_composite(glow, (gx - 24, gy - 24))
    for line, _, _, _, _, i in items:
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
    x, y = 48, 250
    draw_text_with_glowbox(frame, (x, y), "このコラムのポイント", title_font, 1.0, 88, style)
    points = ["› 下着は支える道具", "› 運動は動かす習慣", "› 続け方で選ぶ"]
    for i, line in enumerate(points):
        local = max(0.0, min(1.0, (progress - (0.20 + i * 0.21)) / 0.20))
        draw_text_with_glowbox(frame, (x + 8, y + 104 + i * 72), line, point_font, local, 72, style)


def draw_sentence(frame, text, progress, mode, style):
    x, y = 72, 354
    eased = ease_in_out(min(1.0, progress * 1.5))
    if mode == "slide_left":
        x -= round((1 - eased) * 58)
    elif mode == "slide_right":
        x += round((1 - eased) * 58)
    elif mode == "rise":
        y += round((1 - eased) * 38)
    elif mode == "soft_drop":
        y -= round((1 - eased) * 32)
    draw_text_with_glowbox(frame, (x, y), text, mincho(72, True), min(1.0, progress * 2.1), 90, style)


def render_background(bg, scene_idx, progress):
    p = ease_in_out(progress)
    motion = [
        {"start_zoom": 1.035, "end_zoom": 1.092, "x": 0, "y": 0},
        {"start_zoom": 1.062, "end_zoom": 1.062, "x": 82, "y": 0},
        {"start_zoom": 1.036, "end_zoom": 1.076, "x": -62, "y": 0},
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
        typewriter(frame, (72, 350), "下着でできること、\n運動でできること。", mincho(76, True), progress, style)
    elif scene_idx == 1:
        draw_sentence(frame, "着るだけで、\n体は変わりません。", progress, "rise", style)
    elif scene_idx == 2:
        draw_points(frame, progress, style)
    elif scene_idx == 3:
        draw_sentence(frame, "下着は、\n意識を助けるもの。", progress, "slide_left", style)
    elif scene_idx == 4:
        draw_sentence(frame, "運動は、\n筋肉と向き合う時間。", progress, "slide_right", style)
    else:
        draw_sentence(frame, "どちらも、\n無理なく日常へ。", progress, "soft_drop", style)
    return frame


def make_bgm(duration):
    out = VIDEO / "bgm_urban_column_002.wav"
    rate = 44100
    chords = [
        (261.63, 329.63, 392.00),
        (293.66, 369.99, 440.00),
        (246.94, 329.63, 392.00),
        (220.00, 277.18, 369.99),
    ]
    with wave.open(str(out), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(int(duration * rate)):
            t = i / rate
            chord = chords[int(t / 2.0) % len(chords)]
            pulse = 0.80 + 0.20 * math.sin(2 * math.pi * 0.42 * t)
            sample = 0.0
            for n, freq in enumerate(chord):
                sample += math.sin(2 * math.pi * freq * t) * (0.018 / (n + 1))
                sample += math.sin(2 * math.pi * freq * 2.01 * t) * 0.003
            sample += math.sin(2 * math.pi * 783.99 * t) * 0.0038 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.17 * t))
            sample *= pulse
            frames += int(max(-1, min(1, sample)) * 32767).to_bytes(2, "little", signed=True)
        wf.writeframes(frames)
    return out


def make_preview(total_frames):
    seconds = [4.7, 8.0, 12.3, 16.3, 20.0, 23.6]
    picks = [min(total_frames - 1, int(sec * 30)) for sec in seconds]
    sheet = Image.new("RGB", (810, 540), "white")
    for i, idx in enumerate(picks):
        path = FRAMES / f"frame_{idx:04d}.jpg"
        img = Image.open(path).resize((270, 270), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 3) * 270, (i // 3) * 270))
    sheet.save(VIDEO / "preview_contact_sheet_002.jpg", quality=92)


def make_motion_check(total_frames):
    seconds = [0.8, 2.9, 5.5, 9.6, 14.2, 18.0, 22.5, 25.0]
    picks = [min(total_frames - 1, int(sec * 30)) for sec in seconds]
    sheet = Image.new("RGB", (1080, 540), "white")
    for i, idx in enumerate(picks):
        path = FRAMES / f"frame_{idx:04d}.jpg"
        img = Image.open(path).resize((270, 270), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 4) * 270, (i // 4) * 270))
    sheet.save(VIDEO / "motion_check_sheet_002.jpg", quality=92)


def make_frames():
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)
    scene_files = ["002_scene01.jpg", "002_scene02.jpg", "002_scene03.jpg", "002_scene04.jpg", "002_scene05.jpg", "002_scene06.jpg"]
    durations = [5.8, 3.8, 4.5, 3.8, 3.7, 4.0]
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
    out = VIDEO / "opening_cm_002.mp4"
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


def main():
    prepare_images()
    make_banners()
    make_thumbnail()
    duration = make_frames()
    bgm = make_bgm(duration)
    print(encode_video(bgm))


if __name__ == "__main__":
    main()
