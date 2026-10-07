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
    "title_banner.jpg": "call_FYIyfSknuiIYVJGBdRTkUg9M.png",
    "person_banner.jpg": "call_tivXu6BTf7IrOmD2Z9LHhtfg.png",
    "points_banner.jpg": "call_1mDdUTyeV1mu4uULQHyQjvgf.png",
    "comfort_banner.jpg": "call_pf0qN9h3PY0ziqh8YdbhD6tf.png",
    "choice_banner.jpg": "call_PkcXZKVuyUNgTvOWySmXQ5FF.png",
    "closing_banner.jpg": "call_KiHAHpkqpySCsLDu9It5XNBn.png",
}


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


def text_size(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def fix_orphan_punctuation(lines):
    orphans = set("。、・）」』】!?！？")
    fixed = []
    for line in lines:
        if fixed and line and all(ch in orphans for ch in line):
            fixed[-1] += line
        elif fixed and line and line[0] in orphans:
            fixed[-1] += line[0]
            if line[1:]:
                fixed.append(line[1:])
        else:
            fixed.append(line)
    return fixed


def wrap_text(draw, text, font, max_width, max_lines=2):
    preferred = ["、", "。", "｜", "と", "で", "に", "を"]
    lines = []
    line = ""
    for char in text:
        trial = line + char
        if text_size(draw, trial, font)[0] <= max_width or not line:
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


def fit_font_one_line(draw, text, start_size, max_width, bold=True):
    size = start_size
    while size >= 34:
        font = mincho(size, bold)
        if text_size(draw, text, font)[0] <= max_width:
            return font
        size -= 2
    return mincho(size, bold)


def sample_luminance(img, x, y, w, h):
    crop = img.convert("RGB").crop((x, y, min(img.width, x + w), min(img.height, y + h))).resize((1, 1))
    r, g, b = crop.getpixel((0, 0))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def palette_for_bg(img, area):
    lum = sample_luminance(img, *area)
    if lum > 150:
        return "bright", (43, 38, 36, 246)
    return "dark", (255, 252, 247, 248)


def draw_refined_text(draw, xy, text, font, fill, treatment):
    x, y = xy
    base_img = getattr(draw, "_image", None)
    if treatment == "shadow":
        shadow = (255, 255, 255, 98) if fill[0] < 120 else (28, 24, 22, 112)
        draw.text((x + 1, y + 2), text, font=font, fill=shadow)
    elif treatment == "outline":
        outline = (255, 255, 255, 108) if fill[0] < 120 else (35, 30, 28, 116)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((x + dx, y + dy), text, font=font, fill=outline)
    elif treatment == "glow":
        glow_alpha = 38 if fill[0] < 120 else 30
        if base_img is not None:
            glow_layer = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
            glow_draw = ImageDraw.Draw(glow_layer)
            glow_draw.text((x, y), text, font=font, fill=(255, 255, 255, glow_alpha))
            base_img.alpha_composite(glow_layer.filter(ImageFilter.GaussianBlur(7)))
        else:
            draw.text((x + 3, y + 3), text, font=font, fill=(255, 255, 255, glow_alpha))
    elif treatment == "soft_white_glow":
        if base_img is not None:
            bbox = draw.textbbox((x, y), text, font=font)
            pad = 64
            glow_w = max(1, bbox[2] - bbox[0] + pad * 2)
            glow_h = max(1, bbox[3] - bbox[1] + pad * 2)
            local_x = pad + x - bbox[0]
            local_y = pad + y - bbox[1]

            mask = Image.new("L", (glow_w, glow_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.text((local_x, local_y), text, font=font, fill=255)

            wide_alpha = mask.filter(ImageFilter.MaxFilter(19)).filter(ImageFilter.GaussianBlur(14))
            wide_alpha = wide_alpha.point(lambda v: min(160, int(v * 0.72)))
            wide_glow = Image.new("RGBA", (glow_w, glow_h), (255, 255, 255, 0))
            wide_glow.putalpha(wide_alpha)
            base_img.alpha_composite(wide_glow, (bbox[0] - pad, bbox[1] - pad))

            soft_alpha = mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(7))
            soft_alpha = soft_alpha.point(lambda v: min(110, int(v * 0.55)))
            soft_glow = Image.new("RGBA", (glow_w, glow_h), (255, 255, 255, 0))
            soft_glow.putalpha(soft_alpha)
            base_img.alpha_composite(soft_glow, (bbox[0] - pad, bbox[1] - pad))
        else:
            draw.text((x + 4, y + 4), text, font=font, fill=(255, 255, 255, 38))
    draw.text((x, y), text, font=font, fill=fill)


def choose_treatment(img, area):
    lum = sample_luminance(img, *area)
    if lum > 105:
        return "soft_white_glow"
    if lum > 85:
        return "outline"
    return "shadow"


def prepare_images():
    IMAGES.mkdir(parents=True, exist_ok=True)
    SCENES.mkdir(parents=True, exist_ok=True)
    for out_name, source_name in SOURCE_MAP.items():
        src = GENERATED / source_name
        if not src.exists():
            raise FileNotFoundError(src)
        Image.open(src).convert("RGB").save(IMAGES / out_name, quality=95)

    scene_order = [
        ("01_title.jpg", "title_banner.jpg", -0.05, 0),
        ("02_person.jpg", "person_banner.jpg", 0.06, 0),
        ("03_points.jpg", "points_banner.jpg", 0, 0),
        ("04_comfort.jpg", "comfort_banner.jpg", -0.08, 0),
        ("05_choice.jpg", "choice_banner.jpg", 0, 0),
        ("06_closing.jpg", "closing_banner.jpg", 0.08, 0),
    ]
    for scene_name, src_name, bx, by in scene_order:
        img = Image.open(IMAGES / src_name).convert("RGB")
        cover_crop(img, (1080, 1080), bx, by).save(SCENES / scene_name, quality=94)


def draw_banner_copy(img, title, body):
    img = img.convert("RGBA")
    draw = ImageDraw.Draw(img)
    x, y = 82, 118
    max_width = 1210
    title_font = fit_font_one_line(draw, title, 58, max_width, True)
    _, fill = palette_for_bg(img, (x, y, max_width, 100))
    treatment = choose_treatment(img, (x, y, max_width, 100))
    draw_refined_text(draw, (x, y), title, title_font, fill, treatment)

    body_font = gothic(30)
    y += 86
    for line in wrap_text(draw, body, body_font, 870, 2):
        draw_refined_text(draw, (x, y), line, body_font, fill, treatment)
        y += 43
    return img


def make_banners():
    rows = list(csv.DictReader((BASE / "data" / "banner_plan.csv").open(encoding="utf-8-sig")))
    for row in rows:
        path = IMAGES / row["file_name"]
        img = cover_crop(Image.open(path).convert("RGB"), (1600, 520), -0.05, 0)
        img = draw_banner_copy(img, row["overlay_title"], row["overlay_body"])
        img.convert("RGB").save(path, quality=94)


def make_bgm(duration):
    VIDEO.mkdir(parents=True, exist_ok=True)
    out = VIDEO / "bgm_fashion_column_003.wav"
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
            chord = chords[int(t / 1.8) % len(chords)]
            beat = 0.75 + 0.25 * math.sin(2 * math.pi * 0.55 * t)
            sample = 0.0
            for n, freq in enumerate(chord):
                sample += math.sin(2 * math.pi * freq * t) * (0.025 / (n + 1))
                sample += math.sin(2 * math.pi * freq * 2.01 * t) * 0.004
            sample += math.sin(2 * math.pi * 880.0 * t) * 0.006 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.25 * t))
            sample *= beat
            frames += int(max(-1, min(1, sample)) * 32767).to_bytes(2, "little", signed=True)
        wf.writeframes(frames)
    return out


def typewriter_multiline(draw, xy, text, font, progress, fill, treatment, line_gap=92):
    delay = 0.08
    hold = 0.23
    if progress <= delay:
        return
    p = min(1.0, (progress - delay) / max(0.01, 1.0 - delay - hold))
    visible = math.floor(len(text) * p)
    current = text[:visible]
    x, y = xy
    for i, line in enumerate(current.split("\n")[:3]):
        if line:
            draw_refined_text(draw, (x, y + i * line_gap), line, font, fill, treatment)


def draw_points_scene(draw, frame, progress):
    title_font = mincho(60, True)
    point_font = mincho(54, False)
    x, y = 78, 258
    _, fill = palette_for_bg(frame, (x, y, 830, 300))
    treatment = choose_treatment(frame, (x, y, 830, 300))
    draw_refined_text(draw, (x, y), "このコラムのポイント", title_font, fill, treatment)
    points = ["できること", "できないこと", "続けやすい選び方"]
    for i, text in enumerate(points):
        start = 0.20 + i * 0.21
        local = max(0.0, min(1.0, (progress - start) / 0.20))
        if local == 0:
            continue
        alpha_fill = (fill[0], fill[1], fill[2], int(255 * local))
        yy = y + 100 + i * 70
        draw_refined_text(draw, (x + 10, yy), text, point_font, alpha_fill, treatment)


def draw_sentence(draw, frame, text, progress, mode, base_xy=(74, 360)):
    lines = text.split("\n")
    font = mincho(72, True)
    x, y = base_xy
    if mode == "slide_left":
        x -= int((1 - min(1, progress * 1.7)) * 46)
    elif mode == "slide_right":
        x += int((1 - min(1, progress * 1.7)) * 46)
    elif mode == "rise":
        y += int((1 - min(1, progress * 1.8)) * 34)
    _, fill = palette_for_bg(frame, (x, y, 900, 220))
    treatment = choose_treatment(frame, (x, y, 900, 220))
    alpha = min(255, int(255 * min(1, progress * 2.1)))
    fill = (fill[0], fill[1], fill[2], alpha)
    for i, line in enumerate(lines):
        draw_refined_text(draw, (x, y + i * 88), line, font, fill, treatment)


def render_scene(bg, scene_idx, progress):
    zoom_amounts = [0.018, 0.014, 0.010, 0.016, 0.012, 0.018]
    pan_dirs = [-1, 1, -0.4, 1, -1, 0.6]
    zoom = 1.018 + zoom_amounts[scene_idx] * progress
    resized = bg.resize((int(1080 * zoom), int(1080 * zoom)), Image.Resampling.LANCZOS)
    pan = int(pan_dirs[scene_idx] * 18 * progress)
    left = max(0, min(resized.width - 1080, (resized.width - 1080) // 2 + pan))
    top = (resized.height - 1080) // 2
    frame = resized.crop((left, top, left + 1080, top + 1080)).convert("RGBA")
    draw = ImageDraw.Draw(frame)

    if scene_idx == 0:
        _, fill = palette_for_bg(frame, (72, 350, 900, 230))
        treatment = choose_treatment(frame, (72, 350, 900, 230))
        typewriter_multiline(
            draw,
            (74, 360),
            "着るだけで痩せる？\nそれ、ありえません。",
            mincho(76, True),
            progress,
            fill,
            treatment,
            96,
        )
    elif scene_idx == 1:
        draw_sentence(draw, frame, "でも、服の見え方は\n整えられる。", progress, "rise")
    elif scene_idx == 2:
        draw_points_scene(draw, frame, progress)
    elif scene_idx == 3:
        draw_sentence(draw, frame, "苦しい補正は\n続きません。", progress, "slide_left", (560, 372))
    elif scene_idx == 4:
        draw_sentence(draw, frame, "服に合わせて\n選び方を変える。", progress, "slide_right", (360, 390))
    else:
        draw_sentence(draw, frame, "期待しすぎず、\n納得して選ぶ。", progress, "rise")
    return frame


def make_preview(total_frames):
    seconds = [4.6, 7.2, 11.0, 14.7, 18.1, 21.6]
    picks = [min(total_frames - 1, int(sec * 30)) for sec in seconds]
    sheet = Image.new("RGB", (810, 540), "white")
    for i, idx in enumerate(picks):
        path = FRAMES / f"frame_{idx:04d}.jpg"
        img = Image.open(path).resize((270, 270), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 3) * 270, (i // 3) * 270))
    sheet.save(VIDEO / "preview_contact_sheet_003.jpg", quality=92)


def make_frames():
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)
    scene_files = ["01_title.jpg", "02_person.jpg", "03_points.jpg", "04_comfort.jpg", "05_choice.jpg", "06_closing.jpg"]
    durations = [5.6, 3.4, 4.0, 3.4, 3.4, 3.6]
    fps = 30
    transition_frames = 12
    bgs = [Image.open(SCENES / name).convert("RGB") for name in scene_files]
    idx = 0
    previous = None
    for sidx, (bg, duration) in enumerate(zip(bgs, durations)):
        total = int(duration * fps)
        for frame_no in range(total):
            progress = frame_no / max(1, total - 1)
            frame = render_scene(bg, sidx, progress)
            if previous is not None and frame_no < transition_frames:
                alpha = frame_no / transition_frames
                frame = Image.blend(previous, frame, alpha)
            frame.convert("RGB").save(FRAMES / f"frame_{idx:04d}.jpg", quality=92)
            previous = frame
            idx += 1
    make_preview(idx)
    return sum(durations)


def encode_video(bgm):
    out = VIDEO / "opening_cm_003.mp4"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
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
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
