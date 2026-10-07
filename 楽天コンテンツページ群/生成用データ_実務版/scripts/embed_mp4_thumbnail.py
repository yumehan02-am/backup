from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
from PIL import Image


def make_cover_jpeg(src: Path, dst: Path) -> None:
    image = Image.open(src).convert("RGB")
    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", image.size, (255, 255, 255))
    canvas.paste(image, (0, 0))
    canvas.save(dst, "JPEG", quality=92, optimize=True)


def embed_thumbnail(video: Path, thumbnail: Path, output: Path) -> None:
    if not video.exists():
        raise FileNotFoundError(f"Video not found: {video}")
    if not thumbnail.exists():
        raise FileNotFoundError(f"Thumbnail not found: {thumbnail}")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        cover_jpg = tmp_dir_path / "cover.jpg"
        tmp_output = tmp_dir_path / "with_cover.mp4"
        make_cover_jpeg(thumbnail, cover_jpg)

        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(video),
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
        ]
        subprocess.run(cmd, check=True)

        if output.resolve() == video.resolve():
            backup = video.with_name(f"{video.stem}_pre_cover{video.suffix}")
            if not backup.exists():
                shutil.copy2(video, backup)
        shutil.copy2(tmp_output, output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed a JPG cover image into an MP4 as an attached_pic stream."
    )
    parser.add_argument("video", type=Path, help="Target MP4 file.")
    parser.add_argument("thumbnail", type=Path, help="Cover image. JPG or PNG is accepted.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output MP4 path. If omitted, the input video is overwritten after backup.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    video = args.video.resolve()
    thumbnail = args.thumbnail.resolve()
    output = args.output.resolve() if args.output else video
    embed_thumbnail(video, thumbnail, output)
    print(f"Embedded thumbnail: {thumbnail}")
    print(f"Output video: {output}")


if __name__ == "__main__":
    main()
