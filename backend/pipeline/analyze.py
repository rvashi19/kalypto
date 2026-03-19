import numpy as np
import librosa

def extract_acoustic_features(audio_path: str, sample_rate: int = 16000) -> dict:
    """
    Extract MIR / speech features:
      - Pitch (F0) contour via pYIN
      - RMS energy
      - MFCCs (13 coefficients)
      - Spectral centroid
      - Zero-crossing rate
    """
    print("[ANALYZE] Extracting MIR features...")

    y, sr = librosa.load(audio_path, sr=sample_rate, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    print(f"         Duration: {duration:.2f}s  |  Sample rate: {sr} Hz")

    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7')
    )
    rms = librosa.feature.rms(y=y)[0]
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)

    features = {
        'f0': f0,
        'rms': rms,
        'mfccs': mfccs,
        'spectral_centroid': spectral_centroid,
        'zcr': zcr,
        'onset_env': onset_env,
        'y': y,
        'sr': sr,
        'duration': duration,
    }

    voiced_f0 = f0[~np.isnan(f0)] if f0 is not None else np.array([])
    print(f"         Pitch: mean={np.mean(voiced_f0):.1f} Hz")
    print(f"         RMS energy: mean={np.mean(rms):.4f}")
    return features
