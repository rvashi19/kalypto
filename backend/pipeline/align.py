import librosa
import numpy as np

def align_prosody(source_audio: str, dubbed_audio: str, sample_rate: int = 16000) -> dict:
    """
    Perform Dynamic Time Warping (DTW) alignment between source and dubbed audio
    using MFCC sequences to calculate a structural distance metric.
    """
    print("[ALIGN] Analyzing temporal alignment via DTW...")
    
    try:
        y_src, sr = librosa.load(source_audio, sr=sample_rate, mono=True)
        y_dub, _ = librosa.load(dubbed_audio, sr=sample_rate, mono=True)

        if len(y_src) < 512 or len(y_dub) < 512:
            return {"status": "skipped", "reason": "Audio too short for alignment."}

        # Use MFCCs for structural alignment
        mfcc_src = librosa.feature.mfcc(y=y_src, sr=sr, n_mfcc=13)
        mfcc_dub = librosa.feature.mfcc(y=y_dub, sr=sr, n_mfcc=13)

        # Compute DTW cost and path
        D, wp = librosa.sequence.dtw(X=mfcc_src, Y=mfcc_dub, metric='euclidean')
        
        # Normalized distance (cost / path length)
        normalized_distance = float(D[-1, -1] / wp.shape[0])
        
        print(f"         DTW structural alignment completed (Normalized cost: {normalized_distance:.2f})")
        
        info = {
            "status": "success",
            "dtw_normalized_cost": round(normalized_distance, 4),
            "source_frames": mfcc_src.shape[1],
            "dubbed_frames": mfcc_dub.shape[1],
            "notes": "Cost represents structural MFCC distance. Lower is better aligned."
        }
        import os
        import json
        out_path = os.path.join(os.path.dirname(dubbed_audio), "alignment.json")
        with open(out_path, "w") as f:
            json.dump(info, f, indent=2)
            
        return info

    except Exception as e:
        print(f"         [WARNING] DTW Alignment failed: {e}")
        return {"status": "failed", "error": str(e)}
