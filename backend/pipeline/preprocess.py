import os
import json
import librosa
import soundfile as sf

def _merge_intervals(intervals, gap_samples: int, min_samples: int):
    merged = []
    for start, end in intervals:
        start = int(start)
        end = int(end)

        if not merged:
            merged.append([start, end])
            continue

        prev_start, prev_end = merged[-1]
        prev_len = prev_end - prev_start
        gap = start - prev_end

        if gap <= gap_samples or prev_len < min_samples:
            merged[-1][1] = end
        else:
            merged.append([start, end])

    if len(merged) > 1 and (merged[-1][1] - merged[-1][0]) < min_samples:
        merged[-2][1] = merged[-1][1]
        merged.pop()

    return merged


def _pad_intervals(intervals, padding_samples: int, total_samples: int):
    padded = []
    for start, end in intervals:
        pad_start = max(0, start - padding_samples)
        pad_end = min(total_samples, end + padding_samples)

        if padded and pad_start <= padded[-1][1]:
            padded[-1][1] = max(padded[-1][1], pad_end)
        else:
            padded.append([pad_start, pad_end])

    return padded


def segment_audio(
    audio_path: str,
    output_dir: str,
    top_db: int = 28,
    min_segment_duration: float = 1.2,
    min_gap_duration: float = 0.35,
    padding_duration: float = 0.12,
) -> list:
    """
    Segment speech using silence detection, then merge overly-fragmented chunks.
    """
    print("[PREPROCESS] Running silence-based segmentation...")
    y, sr = librosa.load(audio_path, sr=None)
    
    segments = []
    metadata = {
        "status": "success",
        "segments": [],
        "parameters": {
            "top_db": top_db,
            "min_segment_duration": min_segment_duration,
            "min_gap_duration": min_gap_duration,
            "padding_duration": padding_duration,
        },
    }
    
    try:
        intervals = librosa.effects.split(y, top_db=top_db, frame_length=2048, hop_length=256)
        min_samples = int(min_segment_duration * sr)
        gap_samples = int(min_gap_duration * sr)
        padding_samples = int(padding_duration * sr)
        intervals = _merge_intervals(intervals, gap_samples=gap_samples, min_samples=min_samples)
        intervals = _pad_intervals(intervals, padding_samples=padding_samples, total_samples=len(y))
        
        if len(intervals) <= 1:
            print("         No distinct silences found. Returning full audio.")
            metadata["notes"] = "Full audio returned without splitting."
            segments.append(audio_path)
            metadata["segments"].append({
                "id": 0,
                "start_s": 0.0,
                "end_s": round(len(y) / sr, 3),
                "duration": round(len(y) / sr, 3),
                "file": os.path.basename(audio_path),
            })
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
