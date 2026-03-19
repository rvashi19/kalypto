import numpy as np
import librosa
import librosa.display
import scipy.stats
import matplotlib.pyplot as plt
import os

def extract_features(audio_path: str):
    """
    Extracts prosodic, spectral, and temporal features from audio.
    """
    try:
        y, sr = librosa.load(audio_path, sr=None)
    except Exception as e:
        print(f"Error loading audio for extraction: {e}")
        return None, None

    # 1. Prosodic Features (Pitch - F0)
    f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
    
    # 2. Spectral Features (MFCCs, Spectral Centroid, Spectral Flux)
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    
    # 3. Temporal Features (Onset density, Root Mean Square energy)
    rms = librosa.feature.rms(y=y)
    zcr = librosa.feature.zero_crossing_rate(y)
    
    # Pitch jitter and shimmer are typically better with Praat/Parselmouth,
    # but we approximate with variations here for pure librosa implementation.
    
    features = {
        'f0': f0,
        'mfccs': mfccs,
        'spectral_centroid': spectral_centroid,
        'rms': rms,
        'zcr': zcr,
        'onset_env': onset_env,
        'sr': sr,
        'y': y
    }
    
    return features, y, sr

def compute_valence_arousal(features):
    """
    Maps acoustic features to a Valence-Arousal Model.
    - Arousal derived from RMS Energy and Zero-Crossing Rate.
    - Valence estimated from spectral centroid (brightness) and basic harmonicity.
    """
    if not features:
        return 0.5, 0.5
        
    rms_mean = np.mean(features['rms'])
    zcr_mean = np.mean(features['zcr'])
    
    # Normalize heuristically for prototype
    arousal = np.clip((rms_mean * 10) + (zcr_mean * 2), 0.0, 1.0)
    
    centroid_mean = np.mean(features['spectral_centroid'])
    # Normalize centroid to 0-1 range (assuming vocal range mostly < 4000Hz)
    valence = np.clip(centroid_mean / 4000.0, 0.0, 1.0) 
    
    return valence, arousal

def evaluate_prosody(original_path: str, generated_path: str, output_dir: str):
    """
    Performs Quantitative MIR Evaluation and visualization.
    Includes Pitch Correlation, Pearson Correlation on energy, and Dynamic Time Warping (DTW) for alignment.
    """
    try:
        y_orig, sr_orig = librosa.load(original_path, sr=16000)
        y_gen, sr_gen = librosa.load(generated_path, sr=16000)
        
        # Extract features for evaluation
        f0_orig, _, _ = librosa.pyin(y_orig, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
        f0_gen, _, _ = librosa.pyin(y_gen, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
        
        mfcc_orig = librosa.feature.mfcc(y=y_orig, sr=sr_orig, n_mfcc=13)
        mfcc_gen = librosa.feature.mfcc(y=y_gen, sr=sr_gen, n_mfcc=13)
        
        rms_orig = librosa.feature.rms(y=y_orig)[0]
        rms_gen = librosa.feature.rms(y=y_gen)[0]

        # 1. Mel-Cepstral Distortion (MCD) Approximation using DTW
        D, wp = librosa.sequence.dtw(X=mfcc_orig, Y=mfcc_gen, metric='euclidean')
        mcd_score = D[-1, -1] / len(wp)
        
        # 2. Pitch (F0) Correlation
        # Replace NaNs with 0 for correlation
        f0_orig_clean = np.nan_to_num(f0_orig)
        f0_gen_clean = np.nan_to_num(f0_gen)
        
        # Use DTW path to align f0 signals for correlation
        f0_orig_aligned = f0_orig_clean[wp[:, 0]]
        f0_gen_aligned = f0_gen_clean[wp[:, 1]]
        
        pitch_corr, _ = scipy.stats.pearsonr(f0_orig_aligned, f0_gen_aligned)
        
        # 3. Pearson Correlation (Energy Envelopes)
        rms_orig_aligned = rms_orig[wp[:, 0]]
        rms_gen_aligned = rms_gen[wp[:, 1]]
        energy_corr, _ = scipy.stats.pearsonr(rms_orig_aligned, rms_gen_aligned)
        
        # 4. Generate Visualization (Matplotlib)
        plot_path = os.path.join(output_dir, "prosody_match.png")
        plt.figure(figsize=(10, 6))
        
        plt.subplot(2, 1, 1)
        plt.title("Energy Envelope Match (DTW Aligned)")
        plt.plot(rms_orig_aligned, label="Original Energy", alpha=0.7)
        plt.plot(rms_gen_aligned, label="Dubbed Energy", alpha=0.7)
        plt.legend()
        
        plt.subplot(2, 1, 2)
        plt.title("Pitch (F0) Match (DTW Aligned)")
        plt.plot(f0_orig_aligned, label="Original Pitch", alpha=0.7)
        plt.plot(f0_gen_aligned, label="Dubbed Pitch", alpha=0.7)
        plt.legend()
        
        plt.tight_layout()
        plt.savefig(plot_path)
        plt.close()

        return {
            "mcd_score": float(mcd_score),
            "pitch_correlation": float(pitch_corr) if not np.isnan(pitch_corr) else 0.0,
            "energy_correlation": float(energy_corr) if not np.isnan(energy_corr) else 0.0,
            "plot_path": plot_path
        }

    except Exception as e:
        print(f"Error during prosody evaluation: {e}")
        return None
