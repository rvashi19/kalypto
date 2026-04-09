import os
import json
import subprocess
import soundfile as sf
import librosa
import numpy as np


def _probe_media(input_path: str) -> dict:
    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                os.path.abspath(input_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(completed.stdout or "{}")
    except Exception:
        return {"available": False, "has_audio": None, "has_video": None}

    streams = payload.get("streams") or []
    has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
    has_video = any(stream.get("codec_type") == "video" for stream in streams)
    duration = 0.0
    try:
        duration = float((payload.get("format") or {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0

    return {
        "available": True,
        "has_audio": has_audio,
        "has_video": has_video,
        "duration": duration,
    }

def extract_audio(input_path: str, output_dir: str, sample_rate: int = 16000) -> str:
    """Extract audio from video/audio file -> mono WAV."""
    output_path = os.path.join(output_dir, "source_audio.wav")
    abs_input = os.path.abspath(input_path)
    abs_output = os.path.abspath(output_path)
    
    ext = os.path.splitext(input_path)[1].lower()
    is_audio_only = ext in (".wav", ".mp3", ".aac", ".flac", ".ogg", ".m4a")
    print(f"[INGEST] Processing {'audio' if is_audio_only else 'video'} from: {input_path}")

    try:
        media_probe = _probe_media(abs_input)
        if not is_audio_only and media_probe.get("available") and not media_probe.get("has_audio"):
            raise RuntimeError(
                "Unable to extract audio. The uploaded file does not contain an audio stream."
            )

        cmd = [
            "ffmpeg", "-y", "-i", abs_input,
            "-vn", "-ac", "1", "-ar", str(sample_rate),
            "-acodec", "pcm_s16le", abs_output
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"         Extracted via FFmpeg -> {output_path}")
        _validate_speech(output_path)
        return output_path
    except RuntimeError:
        raise
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        stderr = ""
        if isinstance(e, subprocess.CalledProcessError):
            stderr = (e.stderr or "").strip()
        print(f"         FFmpeg failed ({e}), falling back to librosa...")
        # Fallback
        try:
            y, sr = librosa.load(input_path, sr=sample_rate, mono=True)
            sf.write(output_path, y, sample_rate)
            print(f"         Extracted via librosa -> {output_path}")
            _validate_speech(output_path)
            return output_path
        except Exception as ex:
            details = stderr or str(ex)
            print(f"\n[FATAL ERROR] Could not read audio from {input_path}.")
            print(f"              Format unrecognized, file corrupt, or video has no audio stream. ({details})")
            print(f"              Please provide a valid .wav or a video file containing audible speech.")
            raise RuntimeError(
                "Unable to extract audio. The uploaded file may be corrupted, unsupported, or may not contain an audio stream."
            ) from ex
    
    _validate_speech(output_path)
    return output_path

def _validate_speech(audio_path: str):
    """Checks if audio contains valid speech or is just a beep/silence."""
    y, sr = librosa.load(audio_path, sr=None)
    
    # Check for silence
    rms = librosa.feature.rms(y=y)[0]
    if np.mean(rms) < 0.001:
        print("         [WARNING] Input audio is almost complete silence.")
        return

    # Check for flat tone (beep)
    f0, _, _ = librosa.pyin(y, fmin=50, fmax=500)
    voiced_f0 = f0[~np.isnan(f0)]
    if len(voiced_f0) > 10:
        f0_std = np.std(voiced_f0)
        if f0_std < 5.0:
            print(f"         [WARNING] Input audio has extremely low pitch variance (std = {f0_std:.2f} Hz).")
            print("         This is likely a test tone or beep, not real speech. Evaluation metrics will be weak.")
    else:
        print("         [WARNING] Very few voiced frames detected. Audio may not contain speech.")
