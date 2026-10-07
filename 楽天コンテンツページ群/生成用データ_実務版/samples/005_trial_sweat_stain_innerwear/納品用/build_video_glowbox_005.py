import math
import pathlib
import shutil
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg


BASE = pathlib.Path(__file__).resolve().parent
VIDEO = BASE / "video"
SCENES = VIDEO / "scene_backgrounds"
FRAMES = VIDEO / "frames_glowbox"


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


def text_bbox(text, font):
    scratch = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    draw = ImageDraw.Draw(scratch)
    return draw.textbbox((0, 0), text, font=font)


def text_size(text, font):
    box = text_bbox(text, font)
    return box[2] - box[0], box[3] - box[1]


def sample_luminance(img, x, y, w, h):
    crop = img.convert("RGB").crop((x, y, min(img.width, x + w), min(img.height, y + h))).resize((1, 1))
    r, g, b = crop.getpixel((0, 0))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def text_fill_for_bg(img, area):
    return (42, 37, 35, 250) if sample_luminance(img, *area) > 115 else (255, 252, 247, 250)


GLOW_CACHE = {}


def glow_box(size, alpha=112):
    w, h = size
    key = (w, h, alpha)
    if key in GLOW_CACHE:
        return GLOW_CACHE[key]
    pad = 28
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    rect = (pad, pad, pad + w, pad + h)
    draw.rounded_rectangle(rect, radius=max(24, h // 2), fill=(255, 255, 255, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(16))
    GLOW_CACHE[key] = layer
    return layer


def draw_text_with_glowbox(frame, xy, text, font, progress=1.0, line_gap=88):
    draw = ImageDraw.Draw(frame)
    x, y = xy
    alpha = int(255 * max(0, min(1, progress)))
    if alpha <= 0:
        return
    line_items = []
    for i, line in enumerate(text.split("\n")):
        if not line:
            continue
        tw, th = text_size(line, font)
        gx = x - 42
        gy = y + i * line_gap - 22
        gw = tw + 84
        gh = th + 44
        glow = glow_box((gw, gh), 118 if tw > 300 else 102)
        if alpha < 255:
            glow = glow.copy()
            glow.putalpha(glow.getchannel("A").point(lambda v: int(v * alpha / 255)))
        line_items.append((line, tw, th, gx, gy, glow, i))

    # Place all glow layers first, then all glyphs. This prevents a later line's
    # glow from washing over text that has already appeared.
    for _, _, _, gx, gy, glow, _ in line_items:
        frame.alpha_composite(glow, (gx - 28, gy - 28))

    for line, tw, th, _, _, _, i in line_items:
        fill = text_fill_for_bg(frame, (x, y + i * line_gap, tw + 60, th + 40))
        fill = (fill[0], fill[1], fill[2], alpha)
        draw.text((x, y + i * line_gap), line, font=font, fill=fill)


def typewriter(draw_frame, xy, text, font, progress):
    delay = 0.08
    hold = 0.23
    if progress <= delay:
        return
    p = min(1.0, (progress - delay) / max(0.01, 1.0 - delay - hold))
    current = text[: math.floor(len(text) * p)]
    draw_text_with_glowbox(draw_frame, xy, current, font, 1.0, 96)


def draw_points(frame, progress):
    title_font = mincho(60, True)
    point_font = mincho(52, False)
    x, y = 78, 258
    draw_text_with_glowbox(frame, (x, y), "このコラムのポイント", title_font, 1.0, 88)
    points = ["› 色の見え方", "› 素材の選び方", "› 出かける前の仕込み"]
    for i, line in enumerate(points):
        start = 0.20 + i * 0.21
        local = max(0.0, min(1.0, (progress - start) / 0.20))
        draw_text_with_glowbox(frame, (x + 10, y + 100 + i * 70), line, point_font, local, 70)


def draw_sentence(frame, text, progress, mode):
    x, y = 74, 360
    if mode == "slide_left":
        x -= int((1 - min(1, progress * 1.7)) * 46)
    elif mode == "slide_right":
        x += int((1 - min(1, progress * 1.7)) * 46)
    elif mode == "rise":
        y += int((1 - min(1, progress * 1.8)) * 34)
    alpha = min(1.0, progress * 2.1)
    draw_text_with_glowbox(frame, (x, y), text, mincho(72, True), alpha, 88)


def render_scene(bg, scene_idx, progress):
    zoom_amounts = [0.018, 0.014, 0.010, 0.016, 0.012, 0.018]
    pan_dirs = [-1, 1, -0.4, 1, -1, 0.6]
    zoom = 1.018 + zoom_amounts[scene_idx] * progress
    resized = bg.resize((int(1080 * zoom), int(1080 * zoom)), Image.Resampling.LANCZOS)
    pan = int(pan_dirs[scene_idx] * 18 * progress)
    left = max(0, min(resized.width - 1080, (resized.width - 1080) // 2 + pan))
    top = (resized.height - 1080) // 2
    frame = resized.crop((left, top, left + 1080, top + 1080)).convert("RGBA")

    if scene_idx == 0:
        typewriter(frame, (74, 360), "白シャツの日、\n汗ジミが気になる。", mincho(76, True), progress)
    elif scene_idx == 1:
        draw_sentence(frame, "見え方は、\n色で変わります。", progress, "rise")
    elif scene_idx == 2:
        draw_points(frame, progress)
    elif scene_idx == 3:
        draw_sentence(frame, "白より安心、\nとは限りません。", progress, "slide_left")
    elif scene_idx == 4:
        draw_sentence(frame, "汗を受ける。\n響かせない。", progress, "slide_right")
    else:
        draw_sentence(frame, "汗ばむ日も、\n服をあきらめない。", progress, "rise")
    return frame


def make_bgm(duration):
    out = VIDEO / "bgm_clean_beauty_005.wav"
    if out.exists():
        return out
    rate = 44100
    chords = [(261.63, 329.63, 392.00), (293.66, 369.99, 440.00), (246.94, 329.63, 392.00)]
    with wave.open(str(out), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(int(duration * rate)):
            t = i / rate
            sample = sum(math.sin(2 * math.pi * f * t) * 0.018 for f in chords[int(t / 1.8) % len(chords)])
            frames += int(max(-1, min(1, sample)) * 32767).to_bytes(2, "little", signed=True)
        wf.writeframes(frames)
    return out


def make_preview(total_frames):
    seconds = [4.6, 7.2, 11.0, 14.7, 18.1, 21.6]
    picks = [min(total_frames - 1, int(sec * 30)) for sec in seconds]
    sheet = Image.new("RGB", (810, 540), "white")
    for i, idx in enumerate(picks):
        path = FRAMES / f"frame_{idx:04d}.jpg"
        img = Image.open(path).resize((270, 270), Image.Resampling.LANCZOS)
        sheet.paste(img, ((i % 3) * 270, (i // 3) * 270))
    sheet.save(VIDEO / "preview_contact_sheet_005_glowbox.jpg", quality=92)


def make_frames():
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)
    scene_files = ["01_title.jpg", "02_person.jpg", "03_points.jpg", "04_color.jpg", "05_material.jpg", "06_closing.jpg"]
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
                frame = Image.blend(previous, frame, frame_no / transition_frames)
            frame.convert("RGB").save(FRAMES / f"frame_{idx:04d}.jpg", quality=92)
            previous = frame
            idx += 1
    make_preview(idx)
    return sum(durations)


def encode_video(bgm):
    out = VIDEO / "opening_cm_005_glowbox_test.mp4"
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
    duration = make_frames()
    bgm = make_bgm(duration)
    print(encode_video(bgm))


if __name__ == "__main__":
    main()
