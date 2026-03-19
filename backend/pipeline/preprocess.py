import os
import json
import librosa
import soundfile as sf

def segment_audio(audio_path: str, output_dir: str, top_db: int = 30) -> list:
    """
    Real preprocessing: Segment audio based on silence using librosa.
    Falls back to single segment if extremely short or segmentation fails.
    """
    print("[PREPROCESS] Running silence-based segmentation...")
    y, sr = librosa.load(audio_path, sr=None)
    
    segments = []
    metadata = {"status": "success", "segments": []}
    
    try:
        # Split on silence that is top_db below peak
        intervals = librosa.effects.split(y, top_db=top_db)
        
        # If no intervals or just one unbroken interval, return full file
        if len(intervals) <= 1:
            print("         No distinct silences found. Returning full audio.")
            metadata["notes"] = "Full audio returned without splitting."
            segments.append(audio_path)
        else:
            print(f"         Found {len(intervals)} speech segments.")
            for i, (start, end) in enumerate(intervals):
                chunk_path = os.path.join(output_dir, f"segment_{i}.wav")
                sf.write(chunk_path, y[start:end], sr)
                segments.append(chunk_path)
                metadata["segments"].append({
                    "id": i,
                    "start_s": round(start / sr, 3),
                    "end_s": round(end / sr, 3),
                    "duration": round((end - start) / sr, 3),
                    "file": f"segment_{i}.wav"
                })
    except Exception as e:
        print(f"         [WARNING] Segmentation failed: {e}. Falling back to full audio.")
        metadata["status"] = "failed"
        metadata["error"] = str(e)
        segments = [audio_path]

    # Save segmentation metadata
    with open(os.path.join(output_dir, "segments.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return segments
