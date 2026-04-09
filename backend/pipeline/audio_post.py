from __future__ import annotations

import os
import subprocess

import librosa
import numpy as np
import soundfile as sf


def _build_dialogue_filter(mastering_profile: str, target_lang: str) -> str:
    filters = ["highpass=f=65"]

    if mastering_profile == "guide":
        filters.extend(
            [
                "equalizer=f=260:t=q:w=1.1:g=-1.0",
                "equalizer=f=3000:t=q:w=1.2:g=1.6",
                "alimiter=limit=0.95",
            ]
        )
        return ",".join(filters)

    filters.extend(
        [
            "equalizer=f=220:t=q:w=1.1:g=-1.2",
            "equalizer=f=1800:t=q:w=1.0:g=0.7" if (target_lang or "").strip().lower() == "english" else "volume=1.0",
            "equalizer=f=3000:t=q:w=1.2:g=2.2",
            "equalizer=f=4700:t=q:w=1.2:g=1.1",
            "acompressor=threshold=0.11:ratio=2.1:attack=8:release=75:makeup=1.35",
            "alimiter=limit=0.92",
        ]
    )
    return ",".join(filters)


def _apply_smart_edge_trim(y: np.ndarray, sample_rate: int) -> np.ndarray:
    if not y.size:
        return y

    intervals = librosa.effects.split(y, top_db=38, frame_length=1024, hop_length=256)
    if intervals.size == 0:
        return y

    first_start = int(intervals[0][0])
    last_end = int(intervals[-1][1])
    keep_pad = int(sample_rate * 0.02)
    leading_silence = first_start
    trailing_silence = len(y) - last_end

    if leading_silence >= int(sample_rate * 0.08):
        y = y[max(0, first_start - keep_pad):]
        last_end -= max(0, first_start - keep_pad)
        trailing_silence = len(y) - last_end

    if trailing_silence >= int(sample_rate * 0.1):
        y = y[:min(len(y), last_end + keep_pad)]

    return y


def _apply_dialogue_mastering(path: str, sample_rate: int, mastering_profile: str, target_lang: str) -> None:
    temp_path = path.replace(".wav", "_mastered.wav")
    filter_chain = _build_dialogue_filter(mastering_profile, target_lang)

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            os.path.abspath(path),
            "-af",
            filter_chain,
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-acodec",
            "pcm_s16le",
            os.path.abspath(temp_path),
        ],
        capture_output=True,
        check=True,
    )
    os.replace(temp_path, path)


def finalize_audio(
    path: str,
    sample_rate: int,
    *,
    trim_edges: bool = True,
    smart_trim: bool = False,
    mastering_profile: str = "none",
    target_lang: str = "English",
) -> None:
    y, _ = librosa.load(path, sr=sample_rate, mono=True)
    if not y.size:
        sf.write(path, y.astype(np.float32), sample_rate)
        return

    if smart_trim:
        y = _apply_smart_edge_trim(y, sample_rate)

    if trim_edges:
        trimmed, _ = librosa.effects.trim(y, top_db=40, frame_length=1024, hop_length=256)
        if trimmed.size >= max(int(sample_rate * 0.2), 1):
            y = trimmed

    fade_samples = min(int(sample_rate * 0.02), max(len(y) // 8, 1))
    if fade_samples > 1:
        fade_in = np.linspace(0.0, 1.0, fade_samples)
        fade_out = np.linspace(1.0, 0.0, fade_samples)
        y[:fade_samples] *= fade_in
        y[-fade_samples:] *= fade_out

    peak = float(np.max(np.abs(y)))
    if peak > 0.95:
        y = y / peak * 0.92

    sf.write(path, y.astype(np.float32), sample_rate)

    if mastering_profile != "none":
        try:
            _apply_dialogue_mastering(path, sample_rate, mastering_profile, target_lang)
        except Exception as exc:
            print(f"         Dialogue mastering skipped: {exc}")
