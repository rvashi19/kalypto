import numpy as np
import librosa

def _safe_mean(values) -> float:
    arr = np.asarray(values)
    arr = arr[np.isfinite(arr)]
    return float(np.mean(arr)) if arr.size else 0.0


def _safe_std(values) -> float:
    arr = np.asarray(values)
    arr = arr[np.isfinite(arr)]
    return float(np.std(arr)) if arr.size else 0.0


def _estimate_jitter(voiced_f0: np.ndarray) -> float:
    if voiced_f0.size < 3:
        return 0.0
    ratios = np.abs(np.diff(voiced_f0)) / np.maximum(voiced_f0[:-1], 1e-6)
    return float(np.mean(ratios))


def _estimate_shimmer(rms: np.ndarray) -> float:
    if rms.size < 3:
        return 0.0
    diffs = np.abs(np.diff(rms))
    return float(np.mean(diffs / np.maximum(rms[:-1], 1e-6)))


def _estimate_harmonicity(y: np.ndarray) -> float:
    harmonic, percussive = librosa.effects.hpss(y)
    harmonic_energy = np.sum(np.abs(harmonic))
    percussive_energy = np.sum(np.abs(percussive))
    total = harmonic_energy + percussive_energy
    return float(harmonic_energy / total) if total > 0 else 0.0


def extract_acoustic_features(audio_path: str, sample_rate: int = 16000) -> dict:
    """
    Extract a broader acoustic fingerprint from speech audio.
    """
    print("[ANALYZE] Extracting MIR features...")

    y, sr = librosa.load(audio_path, sr=sample_rate, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    hop_length = 256
    print(f"         Duration: {duration:.2f}s  |  Sample rate: {sr} Hz")

    f0, voiced_flag, voiced_probs = librosa.pyin(
        y,
        fmin=librosa.note_to_hz('C2'),
        fmax=librosa.note_to_hz('C7'),
        frame_length=1024,
        hop_length=hop_length,
    )
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=hop_length)[0]
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop_length)
    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
    zcr = librosa.feature.zero_crossing_rate(y, frame_length=1024, hop_length=hop_length)[0]
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop_length)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)

    spectrum = np.abs(librosa.stft(y, n_fft=1024, hop_length=hop_length))
    spectral_flux = np.sqrt(np.sum(np.diff(spectrum, axis=1, prepend=spectrum[:, :1]) ** 2, axis=0))

    features = {
        'f0': f0,
        'rms': rms,
        'mfccs': mfccs,
        'spectral_centroid': spectral_centroid,
        'zcr': zcr,
        'onset_env': onset_env,
        'onset_times': onset_times,
        'spectral_flux': spectral_flux,
        'y': y,
        'sr': sr,
        'duration': duration,
    }

    voiced_f0 = f0[~np.isnan(f0)] if f0 is not None else np.array([])
    jitter = _estimate_jitter(voiced_f0)
    shimmer = _estimate_shimmer(rms)
    harmonicity = _estimate_harmonicity(y)
    onset_density = float(len(onset_times) / max(duration, 1e-6))
    syllabic_rate = onset_density

    features['stats'] = {
        'pitch_mean_hz': _safe_mean(voiced_f0),
        'pitch_std_hz': _safe_std(voiced_f0),
        'rms_mean': _safe_mean(rms),
        'rms_std': _safe_std(rms),
        'spectral_centroid_mean': _safe_mean(spectral_centroid),
        'zcr_mean': _safe_mean(zcr),
        'spectral_flux_mean': _safe_mean(spectral_flux),
        'onset_density': onset_density,
        'syllabic_rate': syllabic_rate,
        'jitter_local': jitter,
        'shimmer_local': shimmer,
        'harmonicity': harmonicity,
    }

    print(f"         Pitch: mean={features['stats']['pitch_mean_hz']:.1f} Hz")
    print(f"         RMS energy: mean={features['stats']['rms_mean']:.4f}")
    print(f"         Onset density: {onset_density:.2f} /s")
    return features
