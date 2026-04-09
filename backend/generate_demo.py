import os
import json
import subprocess
import tempfile
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pipeline.demo_script import CURATED_DEMO_SEGMENTS


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BACKEND_DIR / "outputs" / "presentation_demo_assets"
SCENE_DIR = OUTPUT_DIR / "scenes"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SCENE_DIR.mkdir(parents=True, exist_ok=True)

DEMO_VIDEO = PROJECT_ROOT / "demo_video.mp4"
SOURCE_AUDIO = OUTPUT_DIR / "presentation_hi.wav"
SUBTITLE_FILE = OUTPUT_DIR / "presentation_hi.srt"
SEGMENT_FILE = OUTPUT_DIR / "presentation_segments.json"
SAMPLE_RATE = 24000
TARGET_DURATION_S = 20.0
BASE_GAP_S = 0.35
FPS = 25


def _load_font(size: int, bold: bool = False):
    font_name = "arialbd.ttf" if bold else "arial.ttf"
    try:
        return ImageFont.truetype(str(Path(r"C:\Windows\Fonts") / font_name), size=size)
    except Exception:
        return ImageFont.load_default()


def _gradient(size: tuple[int, int], top_color: tuple[int, int, int], bottom_color: tuple[int, int, int]) -> Image.Image:
    width, height = size
    img = Image.new("RGB", size, top_color)
    pixels = img.load()
    for y in range(height):
        blend = y / max(height - 1, 1)
        color = tuple(int(top_color[i] * (1 - blend) + bottom_color[i] * blend) for i in range(3))
        for x in range(width):
            pixels[x, y] = color
    return img


def _draw_city(draw: ImageDraw.ImageDraw, width: int, height: int, base_y: int, tint: tuple[int, int, int], seed: int) -> None:
    rng = np.random.default_rng(seed)
    cursor = 0
    while cursor < width:
        building_w = int(rng.integers(55, 130))
        building_h = int(rng.integers(120, 320))
        x0 = cursor
        x1 = min(width, cursor + building_w)
        y0 = base_y - building_h
        draw.rectangle([x0, y0, x1, base_y], fill=tint)

        for row in range(y0 + 18, base_y - 12, 26):
            for col in range(x0 + 12, x1 - 12, 20):
                if rng.random() > 0.42:
                    draw.rectangle([col, row, col + 7, row + 10], fill=(255, 213, 121, 180))

        cursor += building_w + int(rng.integers(8, 20))


def _draw_silhouette(draw: ImageDraw.ImageDraw, x: int, ground_y: int, scale: float, color=(9, 13, 26)) -> None:
    head_r = int(20 * scale)
    body_h = int(120 * scale)
    shoulder_w = int(55 * scale)
    draw.ellipse([x - head_r, ground_y - body_h - 2 * head_r, x + head_r, ground_y - body_h], fill=color)
    draw.rounded_rectangle(
        [x - shoulder_w, ground_y - body_h, x + shoulder_w, ground_y],
        radius=int(12 * scale),
        fill=color,
    )
    draw.rectangle([x - int(18 * scale), ground_y, x - int(2 * scale), ground_y + int(70 * scale)], fill=color)
    draw.rectangle([x + int(2 * scale), ground_y, x + int(18 * scale), ground_y + int(70 * scale)], fill=color)


def _apply_grain(image: Image.Image, amount: float = 14.0) -> Image.Image:
    arr = np.asarray(image).astype(np.float32)
    rng = np.random.default_rng(7)
    noise = rng.normal(0.0, amount, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _create_scene(index: int, segment: dict) -> Path:
    width, height = 1600, 900
    title_font = _load_font(28, bold=True)

    if index == 0:
        img = _gradient((width, height), (11, 18, 40), (46, 19, 68))
        draw = ImageDraw.Draw(img, "RGBA")
        draw.ellipse([110, 90, 250, 230], fill=(241, 196, 15, 90))
        _draw_city(draw, width, height, 710, (18, 25, 44), seed=11)
        draw.rectangle([0, 710, width, height], fill=(6, 10, 22))
        _draw_silhouette(draw, 280, 690, 1.15)
    elif index == 1:
        img = _gradient((width, height), (8, 29, 44), (63, 16, 66))
        draw = ImageDraw.Draw(img, "RGBA")
        for x in range(150, width, 260):
            draw.rounded_rectangle([x, 160, x + 60, 590], radius=12, fill=(39, 173, 255, 60))
        draw.polygon([(0, 760), (width, 760), (width, height), (0, height)], fill=(10, 12, 20))
        for y in range(120, 800, 26):
            draw.line([(0, y), (width, y + 90)], fill=(210, 230, 255, 22), width=2)
        _draw_silhouette(draw, 420, 680, 1.05)
        _draw_silhouette(draw, 1140, 700, 0.92, color=(12, 18, 28))
    elif index == 2:
        img = _gradient((width, height), (58, 18, 18), (124, 49, 17))
        draw = ImageDraw.Draw(img, "RGBA")
        draw.polygon([(0, 740), (420, 520), (1180, 520), (width, 740), (width, height), (0, height)], fill=(24, 18, 24))
        for offset in range(0, 7):
            alpha = max(28 - offset * 4, 6)
            draw.line([(790 - offset * 36, 740), (820 - offset * 90, 900)], fill=(255, 190, 130, alpha), width=6)
            draw.line([(810 + offset * 36, 740), (780 + offset * 90, 900)], fill=(255, 190, 130, alpha), width=6)
        draw.ellipse([690, 610, 730, 650], fill=(255, 242, 180, 180))
        draw.ellipse([870, 610, 910, 650], fill=(255, 242, 180, 180))
        _draw_city(draw, width, height, 480, (33, 16, 20), seed=17)
    else:
        img = _gradient((width, height), (48, 13, 24), (188, 80, 32))
        draw = ImageDraw.Draw(img, "RGBA")
        draw.ellipse([620, 160, 980, 520], fill=(255, 188, 80, 96))
        draw.rectangle([0, 700, width, height], fill=(18, 12, 18))
        _draw_city(draw, width, height, 700, (32, 18, 22), seed=25)
        _draw_silhouette(draw, 780, 670, 1.2)
        _draw_silhouette(draw, 640, 700, 0.88, color=(20, 14, 18))
        _draw_silhouette(draw, 930, 705, 0.88, color=(20, 14, 18))

    img = _apply_grain(img, amount=10.0)
    draw = ImageDraw.Draw(img, "RGBA")
    chip_left = 90
    chip_top = 182
    draw.rounded_rectangle([chip_left, chip_top, chip_left + 320, chip_top + 46], radius=18, fill=(8, 12, 22, 185))
    draw.text((chip_left + 24, chip_top + 10), segment["scene_title"], font=title_font, fill=(245, 224, 161))

    scene_path = SCENE_DIR / f"scene_{index + 1}.png"
    img.save(scene_path)
    return scene_path


def _synthesize_openai(line: str, output_path: Path, instructions: str) -> bool:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=line,
            instructions=instructions,
            response_format="wav",
        ) as response:
            response.stream_to_file(str(output_path))
        return True
    except Exception:
        return False


def _synthesize_hindi_line(line: str, index: int) -> tuple[np.ndarray, float]:
    line_path = OUTPUT_DIR / f"line_{index + 1}.wav"
    instructions = (
        "Speak in natural Hindi with strong cinematic intensity, emotional conviction, brisk pacing, and crisp dramatic pauses."
    )

    if not _synthesize_openai(line, line_path, instructions):
        from gtts import gTTS

        mp3_path = OUTPUT_DIR / f"line_{index + 1}.mp3"
        gTTS(text=line, lang="hi").save(str(mp3_path))
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(mp3_path),
                "-ac",
                "1",
                "-ar",
                str(SAMPLE_RATE),
                "-acodec",
                "pcm_s16le",
                str(line_path),
            ],
            capture_output=True,
            check=True,
        )
        mp3_path.unlink(missing_ok=True)

    y, _ = librosa.load(str(line_path), sr=SAMPLE_RATE, mono=True)
    if y.size:
        fade_samples = min(int(SAMPLE_RATE * 0.02), max(len(y) // 8, 1))
        if fade_samples > 1:
            y[:fade_samples] *= np.linspace(0.0, 1.0, fade_samples)
            y[-fade_samples:] *= np.linspace(1.0, 0.0, fade_samples)

    sf.write(str(line_path), y.astype(np.float32), SAMPLE_RATE)
    return y, len(y) / SAMPLE_RATE


def _format_srt_time(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    secs = (total_ms % 60000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _write_srt(timings: list[tuple[float, float, str]]) -> None:
    chunks = []
    for i, (start_s, end_s, text) in enumerate(timings, start=1):
        chunks.append(
            "\n".join(
                [
                    str(i),
                    f"{_format_srt_time(start_s)} --> {_format_srt_time(end_s)}",
                    text,
                    "",
                ]
            )
        )
    SUBTITLE_FILE.write_text("\n".join(chunks), encoding="utf-8")


def _escape_subtitle_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _build_atempo_filter(rate: float) -> str:
    remaining = float(rate)
    filters = []
    while remaining > 2.0:
        filters.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        filters.append(0.5)
        remaining /= 0.5
    filters.append(remaining)
    return ",".join(f"atempo={value:.6f}" for value in filters)


def _time_scale_audio(y: np.ndarray, rate: float) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as raw_file:
        raw_path = Path(raw_file.name)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as scaled_file:
        scaled_path = Path(scaled_file.name)

    try:
        sf.write(str(raw_path), y.astype(np.float32), SAMPLE_RATE)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(raw_path),
                "-filter:a",
                _build_atempo_filter(rate),
                "-ac",
                "1",
                "-ar",
                str(SAMPLE_RATE),
                str(scaled_path),
            ],
            capture_output=True,
            check=True,
        )
        scaled_audio, _ = librosa.load(str(scaled_path), sr=SAMPLE_RATE, mono=True)
        return scaled_audio
    finally:
        raw_path.unlink(missing_ok=True)
        scaled_path.unlink(missing_ok=True)


def _build_demo_audio() -> tuple[list[float], list[tuple[float, float, str]]]:
    line_audio = []
    scene_durations = []
    subtitle_entries = []
    cursor = 0.0

    for index, segment in enumerate(CURATED_DEMO_SEGMENTS):
        y, duration_s = _synthesize_hindi_line(segment["hindi"], index)
        subtitle_entries.append((cursor + 0.1, cursor + duration_s - 0.05, segment["romanized"]))
        line_audio.append(y)
        scene_duration = duration_s + (BASE_GAP_S if index < len(CURATED_DEMO_SEGMENTS) - 1 else 0.0)
        scene_durations.append(scene_duration)
        cursor += scene_duration

    total_duration = sum(scene_durations)
    if total_duration < TARGET_DURATION_S:
        scene_durations[-1] += TARGET_DURATION_S - total_duration

    assembled = []
    for index, y in enumerate(line_audio):
        assembled.append(y)
        gap_s = scene_durations[index] - (len(y) / SAMPLE_RATE)
        if gap_s > 0:
            assembled.append(np.zeros(int(round(gap_s * SAMPLE_RATE)), dtype=np.float32))

    full_audio = np.concatenate(assembled) if assembled else np.zeros(int(TARGET_DURATION_S * SAMPLE_RATE), dtype=np.float32)
    total_duration = len(full_audio) / SAMPLE_RATE if full_audio.size else 0.0

    if total_duration > TARGET_DURATION_S * 1.01:
        speed_factor = total_duration / TARGET_DURATION_S
        full_audio = _time_scale_audio(full_audio, speed_factor)
        scene_durations = [duration / speed_factor for duration in scene_durations]
        subtitle_entries = [
            (start_s / speed_factor, end_s / speed_factor, text)
            for start_s, end_s, text in subtitle_entries
        ]
    elif total_duration < TARGET_DURATION_S:
        pad_s = TARGET_DURATION_S - total_duration
        full_audio = np.pad(full_audio, (0, int(round(pad_s * SAMPLE_RATE))))
        scene_durations[-1] += pad_s

    peak = float(np.max(np.abs(full_audio))) if full_audio.size else 0.0
    if peak > 0.95:
        full_audio = full_audio / peak * 0.92
    sf.write(str(SOURCE_AUDIO), full_audio.astype(np.float32), SAMPLE_RATE)
    _write_srt(subtitle_entries)

    segment_cursor = 0.0
    segment_manifest = {"segments": []}
    for scene_duration, segment in zip(scene_durations, CURATED_DEMO_SEGMENTS):
        segment_manifest["segments"].append(
            {
                "start_s": round(segment_cursor, 3),
                "end_s": round(segment_cursor + scene_duration, 3),
                "duration": round(scene_duration, 3),
                "romanized": segment["romanized"],
                "english": segment["english"],
            }
        )
        segment_cursor += scene_duration
    SEGMENT_FILE.write_text(json.dumps(segment_manifest, indent=2), encoding="utf-8")
    return scene_durations, subtitle_entries


def _render_video(scene_paths: list[Path], scene_durations: list[float]) -> None:
    inputs = []
    filter_parts = []
    concat_inputs = []

    for index, (scene_path, duration_s) in enumerate(zip(scene_paths, scene_durations)):
        frames = max(int(round(duration_s * FPS)), 1)
        inputs.extend(["-loop", "1", "-t", f"{duration_s:.3f}", "-i", str(scene_path)])
        filter_parts.append(
            (
                f"[{index}:v]scale=1600:900,"
                f"zoompan=z='min(zoom+0.0009,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={frames}:s=1280x720:fps={FPS},trim=duration={duration_s:.3f},setpts=PTS-STARTPTS[v{index}]"
            )
        )
        concat_inputs.append(f"[v{index}]")

    inputs.extend(["-i", str(SOURCE_AUDIO)])
    subtitle_path = _escape_subtitle_path(SUBTITLE_FILE)
    force_style = (
        "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H0011182C,"
        "BackColour=&H80000000,BorderStyle=3,Outline=1,Shadow=0,Alignment=2,MarginV=30"
    )
    filter_parts.append(f"{''.join(concat_inputs)}concat=n={len(scene_paths)}:v=1:a=0[base]")
    filter_parts.append(
        "[4:a]showwaves=s=980x118:mode=cline:colors=0x60A5FA|0xF59E0B:rate=25,format=rgba[wave]"
    )
    filter_parts.append(
        "[base]drawbox=x=0:y=540:w=1280:h=180:color=0x040811AA:t=fill[stage]"
    )
    filter_parts.append("[stage][wave]overlay=(W-w)/2:560[composite]")
    filter_parts.append(
        (
            "[composite]drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':"
            "text='TrueDub Bollywood-Style Demo':fontcolor=white:fontsize=34:x=60:y=52,"
            "drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
            "text='Original Hindi dramatic source clip for the dubbing MVP':"
            "fontcolor=0xA5C8FF:fontsize=22:x=60:y=98,"
            f"subtitles='{subtitle_path}':force_style='{force_style}'[vout]"
        )
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[vout]",
            "-map",
            "4:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(DEMO_VIDEO),
        ],
        check=True,
    )


def main() -> None:
    load_dotenv(BACKEND_DIR / ".env")
    print("Generating 20-second Bollywood-style showcase demo...")
    scene_paths = [_create_scene(index, segment) for index, segment in enumerate(CURATED_DEMO_SEGMENTS)]
    scene_durations, _ = _build_demo_audio()
    _render_video(scene_paths, scene_durations)
    print(f"Presentation demo saved to: {DEMO_VIDEO}")


if __name__ == "__main__":
    main()
