import os
import json
import librosa
import numpy as np
import scipy.stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def evaluate_metrics(source_path: str, dubbed_path: str, result_dir: str, sample_rate: int = 16000) -> dict:
    """
    Compare source vs dubbed audio for pitch, energy, and MCD.
    """
    print("[EVALUATE] Running quantitative evaluation...")
    metrics = {
        "status": "completed",
        "raw_metrics": {},
        "aligned_metrics": {},
        "invalid_or_omitted_metrics": {}
    }

    try:
        y_src, sr = librosa.load(source_path, sr=sample_rate, mono=True)
        y_dub, _ = librosa.load(dubbed_path, sr=sample_rate, mono=True)

        dur_src = len(y_src) / sr
        dur_dub = len(y_dub) / sr
        metrics["source_duration_s"] = round(dur_src, 2)
        metrics["dubbed_duration_s"] = round(dur_dub, 2)
        metrics["duration_ratio"] = round(dur_dub / dur_src, 3) if dur_src > 0 else 0

        if abs(dur_src - dur_dub) / max(dur_src, dur_dub) > 0.5:
            metrics["invalid_or_omitted_metrics"]["duration_warning"] = "Duration mismatch >50%: raw correlations are computed on truncated signals. Rely on aligned_metrics."

        # Pitch
        f0_src, _, _ = librosa.pyin(y_src, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
        f0_dub, _, _ = librosa.pyin(y_dub, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
        # Energy
        rms_src = librosa.feature.rms(y=y_src)[0]
        rms_dub = librosa.feature.rms(y=y_dub)[0]

        # Pitch correlation
        min_len_f0 = min(len(f0_src), len(f0_dub))
        if min_len_f0 > 10:
            f0_s = np.nan_to_num(f0_src[:min_len_f0])
            f0_d = np.nan_to_num(f0_dub[:min_len_f0])
            
            # Avoid ConstantInputWarning and NaN
            if np.std(f0_s) > 1e-5 and np.std(f0_d) > 1e-5:
                pitch_corr, _ = scipy.stats.pearsonr(f0_s, f0_d)
                metrics["raw_metrics"]["pitch_correlation"] = round(float(pitch_corr), 4)
                
                # Aligned Pitch Correlation (DTW path)
                D_p, wp_p = librosa.sequence.dtw(f0_s.reshape(-1, 1), f0_d.reshape(-1, 1), metric='euclidean')
                f0_s_w, f0_d_w = f0_s[wp_p[:, 0]], f0_d[wp_p[:, 1]]
                if np.std(f0_s_w) > 1e-5 and np.std(f0_d_w) > 1e-5:
                    a_pitch_corr, _ = scipy.stats.pearsonr(f0_s_w, f0_d_w)
                    metrics["aligned_metrics"]["pitch_correlation"] = round(float(a_pitch_corr), 4)
                else:
                    metrics["aligned_metrics"]["pitch_correlation"] = None
                    metrics["invalid_or_omitted_metrics"]["aligned_pitch_correlation"] = "Signal lacks variance after DTW structural mapping."
            else:
                metrics["raw_metrics"]["pitch_correlation"] = None
                metrics["aligned_metrics"]["pitch_correlation"] = None
                metrics["invalid_or_omitted_metrics"]["pitch_correlation"] = "Signal lacks basic variance (flat tone or silence)."
        else:
            metrics["raw_metrics"]["pitch_correlation"] = None
            metrics["aligned_metrics"]["pitch_correlation"] = None
            metrics["invalid_or_omitted_metrics"]["pitch_correlation"] = "Source array too short to correlate (<10 frames)."

        # Energy correlation
        min_len_rms = min(len(rms_src), len(rms_dub))
        if min_len_rms > 10:
            r_s, r_d = rms_src[:min_len_rms], rms_dub[:min_len_rms]
            if np.std(r_s) > 1e-5 and np.std(r_d) > 1e-5:
                energy_corr, _ = scipy.stats.pearsonr(r_s, r_d)
                metrics["raw_metrics"]["energy_correlation"] = round(float(energy_corr), 4)

                # Aligned Energy Correlation (DTW path)
                D_e, wp_e = librosa.sequence.dtw(r_s.reshape(-1, 1), r_d.reshape(-1, 1), metric='euclidean')
                r_s_w, r_d_w = r_s[wp_e[:, 0]], r_d[wp_e[:, 1]]
                if np.std(r_s_w) > 1e-5 and np.std(r_d_w) > 1e-5:
                    a_energy_corr, _ = scipy.stats.pearsonr(r_s_w, r_d_w)
                    metrics["aligned_metrics"]["energy_correlation"] = round(float(a_energy_corr), 4)
                else:
                    metrics["aligned_metrics"]["energy_correlation"] = None
                    metrics["invalid_or_omitted_metrics"]["aligned_energy_correlation"] = "Energy array lacks variance after DTW structural mapping."
            else:
                metrics["raw_metrics"]["energy_correlation"] = None
                metrics["aligned_metrics"]["energy_correlation"] = None
                metrics["invalid_or_omitted_metrics"]["energy_correlation"] = "Signal lacks basic energy variance."
        else:
            metrics["raw_metrics"]["energy_correlation"] = None
            metrics["aligned_metrics"]["energy_correlation"] = None
            metrics["invalid_or_omitted_metrics"]["energy_correlation"] = "Source array too short to correlate (<10 frames)."

        # MCD
        mfcc_src = librosa.feature.mfcc(y=y_src, sr=sr, n_mfcc=13)
        mfcc_dub = librosa.feature.mfcc(y=y_dub, sr=sr, n_mfcc=13)
        min_frames = min(mfcc_src.shape[1], mfcc_dub.shape[1])
        if min_frames > 0:
            mcd = float(np.mean(np.sqrt(np.sum((mfcc_src[:, :min_frames] - mfcc_dub[:, :min_frames])**2, axis=0))))
            metrics["raw_metrics"]["mcd_score"] = round(mcd, 4)
        else:
            metrics["raw_metrics"]["mcd_score"] = None
            metrics["invalid_or_omitted_metrics"]["mcd_score"] = "No MFCC frames generated."

        _generate_plots(f0_src, f0_dub, rms_src, rms_dub, sr, min_len_f0, min_len_rms, result_dir)

    except Exception as e:
        metrics["status"] = "partial"
        metrics["error"] = str(e)
        print(f"         Evaluation error: {e}")

    return metrics

def _generate_plots(f0_src, f0_dub, rms_src, rms_dub, sr, min_len_f0, min_len_rms, result_dir):
    fig, axes = plt.subplots(2, 1, figsize=(12, 7))
    # Pitch
    if min_len_f0 > 0:
        t_src = librosa.times_like(f0_src[:min_len_f0], sr=sr)
        axes[0].plot(t_src, np.nan_to_num(f0_src[:min_len_f0]), label='Source Pitch', color='#2196F3', alpha=0.7)
        axes[0].plot(t_src, np.nan_to_num(f0_dub[:min_len_f0]), label='Dubbed Pitch', color='#FF9800', alpha=0.7)
    axes[0].set_title("Pitch (F0) Comparison")
    axes[0].legend()
    # Energy
    if min_len_rms > 0:
        t_rms = librosa.times_like(rms_src[:min_len_rms], sr=sr)
        axes[1].plot(t_rms, rms_src[:min_len_rms], label='Source Energy', color='#2196F3', alpha=0.7)
        axes[1].plot(t_rms, rms_dub[:min_len_rms], label='Dubbed Energy', color='#FF9800', alpha=0.7)
    axes[1].set_title("Energy (RMS) Comparison")
    axes[1].legend()

    fig.tight_layout()
    fig.savefig(os.path.join(result_dir, "comparison_plot.png"), dpi=150)
    plt.close(fig)
