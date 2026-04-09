import json
import os
import tempfile
import subprocess

import librosa
import numpy as np
import soundfile as sf


def _write_audio(path: str, y: np.ndarray, sample_rate: int) -> None:
    if y.size:
        fade_samples = min(int(sample_rate * 0.015), max(len(y) // 8, 1))
        if fade_samples > 1:
            fade_in = np.linspace(0.0, 1.0, fade_samples)
            fade_out = np.linspace(1.0, 0.0, fade_samples)
            y = y.copy()
            y[:fade_samples] *= fade_in
            y[-fade_samples:] *= fade_out
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 0.99:
        y = y / peak * 0.95
    sf.write(path, y.astype(np.float32), sample_rate)


def _build_atempo_filters(rate: float) -> str:
    remaining = float(rate)
    factors = []

    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5

    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0

    factors.append(remaining)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def _ffmpeg_time_stretch(audio_path: str, output_path: str, rate: float, sample_rate: int) -> bool:
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                os.path.abspath(audio_path),
                "-filter:a",
                _build_atempo_filters(rate),
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                os.path.abspath(output_path),
            ],
            capture_output=True,
            check=True,
        )
        return True
    except Exception:
        return False


def stretch_to_duration(
    audio_path: str,
    target_duration_s: float,
    output_path: str,
    sample_rate: int = 16000,
) -> dict:
    """
    Match a synthesized chunk to a target segment duration before assembly.
    """
    y, sr = librosa.load(audio_path, sr=sample_rate, mono=True)
    current_duration_s = len(y) / sr if sr else 0.0

    if current_duration_s <= 0 or target_duration_s <= 0:
        _write_audio(output_path, y, sr)
        return {
            "status": "skipped",
            "source_duration_s": round(current_duration_s, 3),
            "target_duration_s": round(target_duration_s, 3),
            "stretch_rate": 1.0,
        }

    stretch_rate = max(current_duration_s / target_duration_s, 1e-3)
    duration_error = abs(current_duration_s - target_duration_s) / max(target_duration_s, 1e-6)
    quality_warning = None
    if stretch_rate > 1.18:
        quality_warning = "Dub line is too long for the source timing and required aggressive compression."
    elif stretch_rate < 0.88:
        quality_warning = "Dub line is much shorter than the source timing and required aggressive expansion."

    if duration_error <= 0.06:
        stretched = y.copy()
    else:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_output = temp_file.name
        try:
            if _ffmpeg_time_stretch(audio_path, temp_output, stretch_rate, sr):
                stretched, _ = librosa.load(temp_output, sr=sample_rate, mono=True)
            else:
                stretched = librosa.effects.time_stretch(y, rate=stretch_rate)
        finally:
            if os.path.exists(temp_output):
                os.remove(temp_output)

    target_samples = max(1, int(round(target_duration_s * sr)))
    if len(stretched) > target_samples:
        stretched = stretched[:target_samples]
    elif len(stretched) < target_samples:
        stretched = np.pad(stretched, (0, target_samples - len(stretched)))

    _write_audio(output_path, stretched, sr)
    return {
        "status": "success" if not quality_warning else "warning",
        "source_duration_s": round(current_duration_s, 3),
        "target_duration_s": round(target_duration_s, 3),
        "stretch_rate": round(stretch_rate, 4),
        "output_duration_s": round(len(stretched) / sr, 3),
        "quality_warning": quality_warning,
    }


def align_prosody(
    source_audio: str,
    dubbed_audio: str,
    output_path: str | None = None,
    sample_rate: int = 16000,
) -> dict:
    """
    Apply DTW-guided time warping so the dubbed track follows the source timeline.
    """
    print("[ALIGN] Applying DTW-guided prosody alignment...")

    try:
        hop_length = 256
        y_src, sr = librosa.load(source_audio, sr=sample_rate, mono=True)
        y_dub, _ = librosa.load(dubbed_audio, sr=sample_rate, mono=True)

        if len(y_src) < 512 or len(y_dub) < 512:
            if output_path:
                _write_audio(output_path, y_dub, sr)
            return {"status": "skipped", "reason": "Audio too short for alignment."}

        mfcc_src = librosa.feature.mfcc(y=y_src, sr=sr, n_mfcc=13, hop_length=hop_length)
        mfcc_dub = librosa.feature.mfcc(y=y_dub, sr=sr, n_mfcc=13, hop_length=hop_length)
        D, wp = librosa.sequence.dtw(X=mfcc_src, Y=mfcc_dub, metric="euclidean")
        wp = wp[::-1]

        src_frames = wp[:, 0]
        dub_frames = wp[:, 1].astype(float)
        unique_src, inverse = np.unique(src_frames, return_inverse=True)

        averaged_dub_frames = np.zeros(unique_src.shape[0], dtype=float)
        counts = np.zeros(unique_src.shape[0], dtype=float)
        np.add.at(averaged_dub_frames, inverse, dub_frames)
        np.add.at(counts, inverse, 1.0)
        averaged_dub_frames /= np.maximum(counts, 1.0)

        source_times = librosa.frames_to_time(unique_src, sr=sr, hop_length=hop_length)
        dubbed_times = librosa.frames_to_time(averaged_dub_frames, sr=sr, hop_length=hop_length)

        source_duration_s = len(y_src) / sr
        dubbed_duration_s = len(y_dub) / sr

        if source_times.size == 0:
            source_times = np.array([0.0, source_duration_s])
            dubbed_times = np.array([0.0, dubbed_duration_s])
        else:
            if source_times[0] > 0.0:
                source_times = np.insert(source_times, 0, 0.0)
                dubbed_times = np.insert(dubbed_times, 0, 0.0)
            source_times = np.append(source_times, source_duration_s)
            dubbed_times = np.append(dubbed_times, dubbed_duration_s)

        dubbed_times = np.maximum.accumulate(np.clip(dubbed_times, 0.0, dubbed_duration_s))
        target_times = np.arange(len(y_src)) / sr
        mapped_dubbed_times = np.interp(target_times, source_times, dubbed_times)
        dubbed_sample_times = np.arange(len(y_dub)) / sr
        aligned_audio = np.interp(mapped_dubbed_times, dubbed_sample_times, y_dub)

        if output_path:
            _write_audio(output_path, aligned_audio, sr)

        normalized_distance = float(D[-1, -1] / max(wp.shape[0], 1))
        alignment_info = {
            "status": "success",
            "dtw_normalized_cost": round(normalized_distance, 4),
            "source_frames": int(mfcc_src.shape[1]),
            "dubbed_frames": int(mfcc_dub.shape[1]),
            "aligned_duration_s": round(len(aligned_audio) / sr, 3),
            "aligned_audio_path": output_path,
            "notes": "Dubbed audio was resampled onto the source timeline using the DTW path.",
        }

        out_path = os.path.join(os.path.dirname(output_path or dubbed_audio), "alignment.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(alignment_info, f, indent=2)

        print(f"         DTW alignment complete (Normalized cost: {normalized_distance:.2f})")
        return alignment_info
    except Exception as exc:
        print(f"         [WARNING] DTW Alignment failed: {exc}")
        return {"status": "failed", "error": str(exc)}
