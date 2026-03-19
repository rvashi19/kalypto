import numpy as np

def map_features_to_emotion(features: dict) -> tuple:
    """
    Map acoustic features -> continuous Valence-Arousal coordinates.
    - Arousal <-- RMS energy + ZCR (energy & spectral activity)
    - Valence <-- Spectral centroid (brightness)
    """
    rms_mean = np.mean(features['rms'])
    zcr_mean = np.mean(features['zcr'])
    centroid_mean = np.mean(features['spectral_centroid'])

    arousal = float(np.clip((rms_mean * 10) + (zcr_mean * 2), 0.0, 1.0))
    valence = float(np.clip(centroid_mean / 4000.0, 0.0, 1.0))

    print(f"[EMOTION_MAP] Valence: {valence:.3f}, Arousal: {arousal:.3f}")
    return valence, arousal
