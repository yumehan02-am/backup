import csv
import math
import pathlib
import shutil
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import imageio_ffmpeg


BASE = pathlib.Path(__file__).resolve().parent
IMAGES = BASE / "images"
VIDEO = BASE / "video"
SCENES = VIDEO / "scene_backgrounds"
FRAMES = VIDEO / "frames"

GENERATED = pathlib.Path(r"C:\Users\i58400am\.codex\generated_images\01a03bd9-3f16-70d1-81ca-80d9bbc91430")
SOURCE_MAP = {
    "title_banner.jpg": "call_ZfIFyLvVQCD1fGM71Ii4wkuP.png",
    "family_banner.jpg": "call_kTRP512UlEYqP5Z66iWhSaSX.png",
    "capacity_banner.jpg": "call_UbMkxufV8CzxihePOwXRQ4rY.png",
    "night_banner.jpg": "call_Td5oBK3S969iHj6VeO2G173H.png",
    "laundry_banner.jpg": "call_YXkJlkTIaindQLi4w6nTR5fH.png",
    "words_banner.jpg": "call_dxelWD8jBlRkBC0ZJ7Dg72Z5.png",
    "closing_banner.jpg": "call_SUF0ibVus074gDsRj2uvBYu4.png",
}

GLOW_TRIM_CHARS = "。、，．！？!?、・：:；;）)」』】》"
GLOW_CACHE = {}


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
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    max_left = img.width - target_w
    max_top = img.height - target_h
    left = int(max_left * (0.5 + bias_x / 2))
    top = int(max_top * (0.5 + bias_y / 2))
    left = max(0, min(max_left, left))
    top = max(0, min(max_top, top))
    return img.crop((left, top, left + target_w, top + target_h))


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
    preferred = ["、", "。", "｜", "と", "で", "に", "を", "も"]
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


def fit_font_one_line(text, start_size, max_width, bold=True):
    size = start_size
    while size >= 34:
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
    return (43, 38, 36, alpha) if sample_luminance(img, area) > 120 else (255, 252, 247, alpha)


def video_style_for_scene(scene_idx):
    # Keep text color fixed within each scene. Scene 4 is an evening image, so
    # it uses light text with a dark diffused glow instead of white-on-white glow.
    if scene_idx == 3:
        return (255, 252, 247), (30, 27, 25)
    return (43, 38, 36), (255, 255, 255)


def draw_text_glow(img, xy, text, font, fill):
    draw = ImageDraw.Draw(img)
    x, y = xy
    bbox = draw.textbbox((x, y), text, font=font)
    pad = 70
    w = max(1, bbox[2] - bbox[0] + pad * 2)
    h = max(1, bbox[3] - bbox[1] + pad * 2)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.text((pad + x - bbox[0], pad + y - bbox[1]), text, font=font, fill=255)
    wide = mask.filter(ImageFilter.MaxFilter(19)).filter(ImageFilter.GaussianBlur(14))
    wide = wide.point(lambda v: min(150, int(v * 0.68)))
    glow = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    glow.putalpha(wide)
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
        ("01_title.jpg", "title_banner.jpg", -0.12, 0),
        ("02_family.jpg", "family_banner.jpg", -0.18, 0),
        ("03_points.jpg", "capacity_banner.jpg", -0.12, 0),
        ("04_capacity.jpg", "night_banner.jpg", -0.20, 0),
        ("05_laundry.jpg", "laundry_banner.jpg", -0.16, 0),
        ("06_closing.jpg", "closing_banner.jpg", -0.18, 0),
    ]
    for scene_name, src_name, bx, by in scene_order:
        cover_crop(Image.open(IMAGES / src_name).convert("RGB"), (1080, 1080), bx, by).save(SCENES / scene_name, quality=94)


def make_banners():
    for row in csv.DictReader((BASE / "data" / "banner_plan.csv").open(encoding="utf-8-sig")):
        path = IMAGES / row["file_name"]
        img = cover_crop(Image.open(path).convert("RGB"), (1600, 520), -0.10, 0).convert("RGBA")
        title_font = fit_font_one_line(row["overlay_title"], 58, 1220, True)
        body_font = gothic(30)
        x, y = 82, 116
        fill = fill_for_bg(img, (x, y, 1220, 190))
        draw_text_glow(img, (x, y), row["overlay_title"], title_font, fill)
        y += 86
        for line in wrap_text(row["overlay_body"], body_font, 900, 2):
            draw_text_glow(img, (x, y), line, body_font, fill)
            y += 43
        img.convert("RGB").save(path, quality=94)


def text_for_glow(line):
    stripped = line.rstrip(GLOW_TRIM_CHARS)
    return stripped or line


def glow_box(size, glow_rgb=(255, 255, 255), alpha=112):
    w, h = size
    key = (w, h, glow_rgb, alpha)
    if key in GLOW_CACHE:
        return GLOW_CACHE[key]
    pad = 26
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (*glow_rgb, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((pad, pad, pad + w, pad + h), radius=max(22, h // 2), fill=(*glow_rgb, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(14))
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
        full_w, full_h = text_size(line, font)
        gx = x - 32
        gy = y + i * line_gap - 18
        gw = gw_text + 64
        gh = gh + 36
        glow = glow_box((gw, gh), glow_rgb, 112 if gw_text > 300 else 96)
        if alpha < 255:
            glow = glow.copy()
            glow.putalpha(glow.getchannel("A").point(lambda v: int(v * alpha / 255)))
        items.append((line, full_w, full_h, gx, gy, glow, i))
    for _, _, _, gx, gy, glow, _ in items:
        frame.alpha_composite(glow, (gx - 26, gy - 26))
    for line, full_w, full_h, _, _, _, i in items:
        draw.text((x, y + i * line_gap), line, font=font, fill=(*text_rgb, alpha))


def typewriter(frame, xy, text, font, progress, style):
    delay = 0.10
    hold = 0.20
    if progress <= delay:
        return
    p = min(1.0, (progress - delay) / max(0.01, 1.0 - delay - hold))
    visible = max(0, math.floor(len(text) * p))
    if visible <= 1:
        return
    draw_text_with_glowbox(frame, xy, text[:visible], font, 1.0, 96, style)


def draw_points(frame, progress, style):
    title_font = mincho(60, True)
    point_font = mincho(52)
    x, y = 74, 250
    draw_text_with_glowbox(frame, (x, y), "このコラムのポイント", title_font, 1.0, 88, style)
    points = ["› 気持ちへの配慮", "› 150cc以上の目安", "› 洗い替えとすすめ方"]
    for i, line in enumerate(points):
        local = max(0.0, min(1.0, (progress - (0.20 + i * 0.21)) / 0.20))
        draw_text_with_glowbox(frame, (x + 8, y + 104 + i * 72), line, point_font, local, 72, style)


def draw_sentence(frame, text, progress, mode, style):
    x, y = 72, 354
    if mode == "slide_left":
        x -= int((1 - min(1, progress * 1.7)) * 46)
    elif mode == "slide_right":
        x += int((1 - min(1, progress * 1.7)) * 46)
    elif mode == "rise":
        y += int((1 - min(1, progress * 1.8)) * 34)
    draw_text_with_glowbox(frame, (x, y), text, mincho(72, True), min(1.0, progress * 2.1), 90, style)


def render_background(bg, scene_idx, progress):
    zoom_amounts = [0.018, 0.012, 0.010, 0.014, 0.016, 0.018]
    pan_dirs = [-0.8, 0.8, -0.4, 0.7, -0.9, 0.6]
    zoom = 1.018 + zoom_amounts[scene_idx] * progress
    resized = bg.resize((int(1080 * zoom), int(1080 * zoom)), Image.Resampling.LANCZOS)
    pan = int(pan_dirs[scene_idx] * 18 * progress)
    left = max(0, min(resized.width - 1080, (resized.width - 1080) // 2 + pan))
    top = (resized.height - 1080) // 2
    return resized.crop((left, top, left + 1080, top + 1080)).convert("RGBA")


def render_scene(bg, scene_idx, progress):
    frame = render_background(bg, scene_idx, progress)
    style = video_style_for_scene(scene_idx)
    if scene_idx == 0:
        typewriter(frame, (72, 350), "使う人の気持ちから、\n選びたい。", mincho(76, True), progress, style)
    elif scene_idx == 1:
        draw_sentence(frame, "吸水量だけでは、\n決めきれない。", progress, "rise", style)
    elif scene_idx == 2:
        draw_points(frame, progress, style)
    elif scene_idx == 3:
        draw_sentence(frame, "夜間や長時間に、\n備えるという選択。", progress, "slide_left", style)
    elif scene_idx == 4:
        draw_sentence(frame, "枚数は、\n家族の余裕にもなる。", progress, "slide_right", style)
    else:
        draw_sentence(frame, "毎日を少し、\n穏やかにする準備。", progress, "rise", style)
    return frame


def make_bgm(duration):
    out = VIDEO / "bgm_senior_care_004.wav"
    rate = 44100
    chords = [(220.00, 277.18, 329.63), (196.00, 246.94, 293.66), (233.08, 293.66, 349.23)]
    with wave.open(str(out), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(int(duration * rate)):
            t = i / rate
            chord = chords[int(t / 2.4) % len(chords)]
            envelope = 0.72 + 0.28 * math.sin(2 * math.pi * 0.22 * t)
            sample = 0.0
            for n, freq in enumerate(chord):
                sample += math.sin(2 * math.pi * freq * t) * (0.023 / (n + 1))
                sample += math.sin(2 * math.pi * freq * 2.0 * t) * 0.003
            sample += math.sin(2 * math.pi * 523.25 * t) * 0.004 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.16 * t))
            sample *= envelope
            frames += int(max(-1, min(1, sample)) * 32767).to_bytes(2, "little", signed=True)
        wf.writeframes(frames)
    return out


def make_preview(total_frames):
    seconds = [4.8, 7.7, 11.9, 15.8, 19.4, 22.8]
    picks = [min(total_frames - 1, int(sec * 30)) for sec in seconds]
    sheet = Image.new("RGB", (810, 540), "white")
    for i, idx in enumerate(picks):
        path = FRAMES / f"frame_{idx:04d}.jpg"
        img = Image.open(path).resize((270, 270), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 3) * 270, (i // 3) * 270))
    sheet.save(VIDEO / "preview_contact_sheet_004.jpg", quality=92)


def make_frames():
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)
    scene_files = ["01_title.jpg", "02_family.jpg", "03_points.jpg", "04_capacity.jpg", "05_laundry.jpg", "06_closing.jpg"]
    durations = [5.8, 3.6, 4.5, 3.7, 3.6, 3.8]
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
    return sum(durations)


def encode_video(bgm):
    out = VIDEO / "opening_cm_004.mp4"
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
    duration = make_frames()
    bgm = make_bgm(duration)
    print(encode_video(bgm))


if __name__ == "__main__":
    main()
