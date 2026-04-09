import os

import librosa
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy.stats


def _extract_pair_metrics(y_src: np.ndarray, y_tgt: np.ndarray, sr: int) -> tuple[dict, dict]:
    metrics = {
        "pitch_correlation": None,
        "energy_correlation": None,
        "mcd_score": None,
    }
    issues = {}

    f0_src, _, _ = librosa.pyin(y_src, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"))
    f0_tgt, _, _ = librosa.pyin(y_tgt, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"))
    rms_src = librosa.feature.rms(y=y_src)[0]
    rms_tgt = librosa.feature.rms(y=y_tgt)[0]

    min_len_f0 = min(len(f0_src), len(f0_tgt))
    if min_len_f0 > 10:
        f0_s = np.nan_to_num(f0_src[:min_len_f0])
        f0_t = np.nan_to_num(f0_tgt[:min_len_f0])
        if np.std(f0_s) > 1e-5 and np.std(f0_t) > 1e-5:
            pitch_corr, _ = scipy.stats.pearsonr(f0_s, f0_t)
            metrics["pitch_correlation"] = round(float(pitch_corr), 4)
        else:
            issues["pitch_correlation"] = "Signal lacks pitch variance."
    else:
        issues["pitch_correlation"] = "Source array too short to correlate (<10 frames)."

    min_len_rms = min(len(rms_src), len(rms_tgt))
    if min_len_rms > 10:
        r_s = rms_src[:min_len_rms]
        r_t = rms_tgt[:min_len_rms]
        if np.std(r_s) > 1e-5 and np.std(r_t) > 1e-5:
            energy_corr, _ = scipy.stats.pearsonr(r_s, r_t)
            metrics["energy_correlation"] = round(float(energy_corr), 4)
        else:
            issues["energy_correlation"] = "Signal lacks energy variance."
    else:
        issues["energy_correlation"] = "Source array too short to correlate (<10 frames)."

    mfcc_src = librosa.feature.mfcc(y=y_src, sr=sr, n_mfcc=13)
    mfcc_tgt = librosa.feature.mfcc(y=y_tgt, sr=sr, n_mfcc=13)
    min_frames = min(mfcc_src.shape[1], mfcc_tgt.shape[1])
    if min_frames > 0:
        mcd = float(np.mean(np.sqrt(np.sum((mfcc_src[:, :min_frames] - mfcc_tgt[:, :min_frames]) ** 2, axis=0))))
        metrics["mcd_score"] = round(mcd, 4)
    else:
        issues["mcd_score"] = "No MFCC frames generated."

    return metrics, issues


def evaluate_metrics(
    source_path: str,
    dubbed_path: str,
    result_dir: str,
    aligned_path: str | None = None,
    sample_rate: int = 16000,
) -> dict:
    """
    Compare source audio against both raw and aligned dubbed audio.
    """
    print("[EVALUATE] Running quantitative evaluation...")
    metrics = {
        "status": "completed",
        "raw_metrics": {},
        "aligned_metrics": {},
        "invalid_or_omitted_metrics": {},
    }

    try:
        y_src, sr = librosa.load(source_path, sr=sample_rate, mono=True)
        y_raw, _ = librosa.load(dubbed_path, sr=sample_rate, mono=True)
        y_aligned = y_raw
        if aligned_path and os.path.exists(aligned_path):
            y_aligned, _ = librosa.load(aligned_path, sr=sample_rate, mono=True)

        metrics["source_duration_s"] = round(len(y_src) / sr, 2)
        metrics["dubbed_duration_s"] = round(len(y_raw) / sr, 2)
        metrics["aligned_duration_s"] = round(len(y_aligned) / sr, 2)
        metrics["duration_ratio"] = round((len(y_raw) / max(len(y_src), 1)), 3)

        if abs(len(y_src) - len(y_raw)) / max(len(y_src), len(y_raw), 1) > 0.5:
            metrics["invalid_or_omitted_metrics"]["duration_warning"] = (
                "Duration mismatch >50% on raw dubbed audio. Prefer aligned metrics."
            )

        raw_metrics, raw_issues = _extract_pair_metrics(y_src, y_raw, sr)
        aligned_metrics, aligned_issues = _extract_pair_metrics(y_src, y_aligned, sr)
        metrics["raw_metrics"] = raw_metrics
        metrics["aligned_metrics"] = aligned_metrics
        metrics["invalid_or_omitted_metrics"].update(
            {f"raw_{key}": value for key, value in raw_issues.items()}
        )
        metrics["invalid_or_omitted_metrics"].update(
            {f"aligned_{key}": value for key, value in aligned_issues.items()}
        )

        _generate_plot(y_src, y_aligned, sr, result_dir)
    except Exception as exc:
        metrics["status"] = "partial"
        metrics["error"] = str(exc)
        print(f"         Evaluation error: {exc}")

    return metrics


def _generate_plot(y_src: np.ndarray, y_tgt: np.ndarray, sr: int, result_dir: str) -> None:
    f0_src, _, _ = librosa.pyin(y_src, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"))
    f0_tgt, _, _ = librosa.pyin(y_tgt, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"))
    rms_src = librosa.feature.rms(y=y_src)[0]
    rms_tgt = librosa.feature.rms(y=y_tgt)[0]

    min_len_f0 = min(len(f0_src), len(f0_tgt))
    min_len_rms = min(len(rms_src), len(rms_tgt))

    fig, axes = plt.subplots(2, 1, figsize=(12, 7))
    if min_len_f0 > 0:
        t_src = librosa.times_like(f0_src[:min_len_f0], sr=sr)
        axes[0].plot(t_src, np.nan_to_num(f0_src[:min_len_f0]), label="Source Pitch", color="#2196F3", alpha=0.8)
        axes[0].plot(t_src, np.nan_to_num(f0_tgt[:min_len_f0]), label="Aligned Dub Pitch", color="#FF9800", alpha=0.8)
    axes[0].set_title("Pitch (F0) Comparison")
    axes[0].legend()

    if min_len_rms > 0:
        t_rms = librosa.times_like(rms_src[:min_len_rms], sr=sr)
        axes[1].plot(t_rms, rms_src[:min_len_rms], label="Source Energy", color="#2196F3", alpha=0.8)
        axes[1].plot(t_rms, rms_tgt[:min_len_rms], label="Aligned Dub Energy", color="#FF9800", alpha=0.8)
    axes[1].set_title("Energy (RMS) Comparison")
    axes[1].legend()

    fig.tight_layout()
    fig.savefig(os.path.join(result_dir, "comparison_plot.png"), dpi=150)
    plt.close(fig)
