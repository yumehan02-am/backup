import pathlib
import shutil
import subprocess

from PIL import Image
import imageio_ffmpeg


ROOT = pathlib.Path(__file__).resolve().parents[1]
LOGO = ROOT.parent / "ゆめはんオリジナル商品マークB.png"
PRODUCTION = ROOT / "production"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

VIDEO_JOBS = [
    (
        PRODUCTION / "000_absorbent_shorts_preparation" / "納品用" / "video" / "opening_cm_000.mp4",
        None,
    ),
    (
        PRODUCTION / "001_pelvic_floor_femcare_habit" / "納品用" / "video" / "opening_cm_001.mp4",
        PRODUCTION / "001_pelvic_floor_femcare_habit" / "納品用" / "video" / "opening_cm_001_bgm2x.mp4",
    ),
    (
        PRODUCTION / "002_underwear_exercise_realistic_pelvic_floor" / "納品用" / "video" / "opening_cm_002.mp4",
        None,
    ),
    (
        PRODUCTION / "003_pelvic_floor_training_illustrated" / "納品用" / "video" / "opening_cm_003.mp4",
        None,
    ),
]


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")


def duration_seconds(path):
    result = run([FFMPEG, "-hide_banner", "-i", str(path), "-f", "null", "-"])
    duration = None
    for line in result.stderr.splitlines():
        if "Duration:" not in line:
            continue
        token = line.split("Duration:", 1)[1].split(",", 1)[0].strip()
        h, m, s = token.split(":")
        duration = int(h) * 3600 + int(m) * 60 + float(s)
        break
    if duration is None:
        raise RuntimeError(f"Could not read duration: {path}")
    return duration


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


def source_for(output_path, preferred_source):
    backup = output_path.parent / f"{output_path.stem}_pre_logo.mp4"
    if preferred_source and preferred_source.exists():
        return preferred_source
    if backup.exists():
        return backup
    return output_path


def add_outro(output_path, preferred_source=None):
    if not output_path.exists():
        raise FileNotFoundError(output_path)

    video_dir = output_path.parent
    backup = video_dir / f"{output_path.stem}_pre_logo.mp4"
    tmp = video_dir / f"{output_path.stem}_with_logo_tmp.mp4"
    logo_frame = video_dir / "outro_logo_frame.jpg"
    input_path = source_for(output_path, preferred_source)

    if not backup.exists():
        shutil.copy2(input_path, backup)

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
            str(tmp),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    tmp.replace(output_path)
    return output_path


def main():
    for output_path, preferred_source in VIDEO_JOBS:
        print(add_outro(output_path, preferred_source))


if __name__ == "__main__":
    main()
