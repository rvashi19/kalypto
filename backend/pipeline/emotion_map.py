import numpy as np

def _norm(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return float(np.clip((value - low) / (high - low), 0.0, 1.0))


def map_features_to_emotion(features: dict) -> tuple:
    """
    Map acoustic features into a continuous Valence-Arousal space.
    The mapping is still heuristic, but it now considers a fuller MIR profile.
    """
    stats = features.get("stats", {})

    rms_mean = stats.get("rms_mean", float(np.mean(features["rms"])))
    zcr_mean = stats.get("zcr_mean", float(np.mean(features["zcr"])))
    centroid_mean = stats.get("spectral_centroid_mean", float(np.mean(features["spectral_centroid"])))
    spectral_flux_mean = stats.get("spectral_flux_mean", 0.0)
    onset_density = stats.get("onset_density", 0.0)
    syllabic_rate = stats.get("syllabic_rate", onset_density)
    pitch_std = stats.get("pitch_std_hz", 0.0)
    jitter = stats.get("jitter_local", 0.0)
    shimmer = stats.get("shimmer_local", 0.0)
    harmonicity = stats.get("harmonicity", 0.0)

    arousal = float(np.clip(np.average([
        _norm(rms_mean, 0.01, 0.18),
        _norm(zcr_mean, 0.02, 0.18),
        _norm(spectral_flux_mean, 0.0, 150.0),
        _norm(onset_density, 0.5, 6.0),
        _norm(syllabic_rate, 0.5, 6.0),
        _norm(pitch_std, 5.0, 90.0),
    ], weights=[0.24, 0.12, 0.18, 0.18, 0.14, 0.14]), 0.0, 1.0))

    valence = float(np.clip(np.average([
        _norm(centroid_mean, 700.0, 3200.0),
        harmonicity,
        1.0 - _norm(jitter, 0.0, 0.08),
        1.0 - _norm(shimmer, 0.0, 0.25),
    ], weights=[0.28, 0.32, 0.2, 0.2]), 0.0, 1.0))

    print(f"[EMOTION_MAP] Valence: {valence:.3f}, Arousal: {arousal:.3f}")
    return valence, arousal
