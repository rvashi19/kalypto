"""
Prosody Transfer Module (Dynamic Spectral Matching)
===================================================
Transfers emotional dynamics (energy envelopes and multiband frequency balance)
from the source audio onto the dubbed audio so the dubbed version preserves 
the same emotional intensity arc as the original. 

This approach completely replaces destructive pitch shifting with "Dynamic EQ".
If the original actor was intense/bassy at the start and airy/subtle at the end, 
this transfers that texture over time by scaling frequency bands dynamically,
preserving the clean TTS voice quality without robotic distortions.
"""

from __future__ import annotations

import os
from typing import Any

import librosa
import numpy as np
import soundfile as sf
from scipy.ndimage import gaussian_filter1d


def _resample_envelope(env: np.ndarray, target_len: int) -> np.ndarray:
    """Safely linearly interpolates a 1D envelope to a new length."""
    if len(env) == target_len:
        return env.copy()
    if len(env) < 2:
        return np.full(target_len, env[0] if env.size else 1.0)
    return np.interp(
        np.linspace(0, 1, target_len), 
        np.linspace(0, 1, len(env)), 
        env
    )


def _transfer_multiband_eq(
    y_dub: np.ndarray, 
    y_src: np.ndarray, 
    sr: int, 
    blend: float
) -> np.ndarray:
    """
    Splits both signals into Low (Bass), Mid, and High frequency bands.
    Dynamically Equalizes the dub frame-by-frame so its relative frequency 
    balance mimics the source's balance over time (for emotional texture).
    """
    if blend <= 0.05:
        return y_dub

    # 1. Compute STFTs
    S_dub = librosa.stft(y_dub)
    S_src = librosa.stft(y_src)
    
    mag_dub = np.abs(S_dub)
    mag_src = np.abs(S_src)
    freqs = librosa.fft_frequencies(sr=sr)
    
    # 2. Define bands
    # Low/Bass: < 180 Hz (Intensity/Strength)
    # Mid: 180 Hz - 4000 Hz (Core voice intelligibility)
    # High: > 4000 Hz (Air/Subtle breathiness)
    low_idx = freqs < 180
    mid_idx = (freqs >= 180) & (freqs < 4000)
    high_idx = freqs >= 4000
    
    def _get_band_envelope(mag: np.ndarray, band_idx: np.ndarray) -> np.ndarray:
        if not np.any(band_idx):
            return np.ones(mag.shape[1])
        energy = np.sqrt(np.mean(mag[band_idx, :]**2, axis=0))
        # Smooth heavily to track long emotional arcs, not micro-phonemes
        return gaussian_filter1d(energy, sigma=8.0)
        
    mag_out = mag_dub.copy()
    
    # 3. Match each band's shape
    for b_idx in [low_idx, mid_idx, high_idx]:
        if not np.any(b_idx): 
            continue
            
        env_src = _get_band_envelope(mag_src, b_idx)
        env_dub = _get_band_envelope(mag_dub, b_idx)
        env_src_res = _resample_envelope(env_src, len(env_dub))
        
        # Compute relative shapes (divided by their own means)
        src_shape = env_src_res / np.maximum(np.mean(env_src_res), 1e-6)
        dub_shape = env_dub / np.maximum(np.mean(env_dub), 1e-6)
        
        # Gain ratio limits: [0.75, 1.25] strictly prevent blowing out bands to keep voice clear
        gain = src_shape / np.maximum(dub_shape, 1e-6)
        gain = np.clip(gain, 0.75, 1.25) 
        
        # Apply blend
        gain = 1.0 + blend * (gain - 1.0)
        
        mag_out[b_idx, :] *= gain

    # 4. Inverse STFT to get back audio using original phase
    phase_dub = np.angle(S_dub)
    S_out = mag_out * np.exp(1j * phase_dub)
    y_out = librosa.istft(S_out, length=len(y_dub))
    
    return y_out.astype(np.float32)


def _transfer_energy(
    y_dub: np.ndarray, 
    y_src: np.ndarray, 
    sr: int, 
    blend: float
) -> np.ndarray:
    """
    Matches the overall volume (RMS energy) envelope so loud parts 
    in the source are loud in the dub, and quiet parts are quiet.
    """
    if blend <= 0.05:
        return y_dub

    hop_length = 256
    rms_dub = librosa.feature.rms(y=y_dub, hop_length=hop_length)[0]
    rms_src = librosa.feature.rms(y=y_src, hop_length=hop_length)[0]
    
    # Smooth envelopes
    rms_src = gaussian_filter1d(rms_src, sigma=8.0)
    rms_dub = gaussian_filter1d(rms_dub, sigma=8.0)
    
    rms_src_res = _resample_envelope(rms_src, len(rms_dub))
    
    # Relative shapes
    src_shape = rms_src_res / np.maximum(np.mean(rms_src_res), 1e-6)
    dub_shape = rms_dub / np.maximum(np.mean(rms_dub), 1e-6)
    
    # Gain ratio limits: [0.80, 1.20] highly conservative volume envelopes
    gain = src_shape / np.maximum(dub_shape, 1e-6)
    gain = np.clip(gain, 0.80, 1.20)
    gain = 1.0 + blend * (gain - 1.0)
    
    n_frames = len(gain)
    frame_times = librosa.frames_to_time(np.arange(n_frames), sr=sr, hop_length=hop_length)
    sample_times = np.arange(len(y_dub)) / sr
    sample_gain = np.interp(sample_times, frame_times, gain)
    
    result = y_dub * sample_gain.astype(np.float32)
    return result


def transfer_prosody(
    source_audio_path: str,
    dubbed_audio_path: str,
    output_path: str,
    sample_rate: int = 16000,
    *,
    eq_blend: float = 0.50,
    energy_blend: float = 0.60,
    enable_eq: bool = True,
    enable_energy: bool = True,
) -> dict[str, Any]:
    """
    Apply the source audio's dynamic texture to the dubbed audio.

    Parameters
    ----------
    source_audio_path : str
        Path to the original (source language) segment audio.
    dubbed_audio_path : str
        Path to the synthesized dubbed segment audio.
    output_path : str
        Where to write the prosody-transferred result.
    sample_rate : int
        Working sample rate.
    eq_blend : float
        0.0 = no EQ transfer, 1.0 = heavy dynamic spectral transfer
    energy_blend : float
        0.0 = no energy transfer, 1.0 = heavy volume envelope matching.
    enable_eq : bool
        Whether to apply multiband EQ transfer.
    enable_energy : bool
        Whether to apply energy envelope transfer.

    Returns
    -------
    dict with transfer metadata
    """
    info: dict[str, Any] = {
        "status": "success",
        "eq_applied": False,
        "energy_applied": False,
        "eq_blend": eq_blend,
        "energy_blend": energy_blend,
        "pitch_shift_removed": True,
    }

    try:
        y_src, _ = librosa.load(source_audio_path, sr=sample_rate, mono=True)
        y_dub, _ = librosa.load(dubbed_audio_path, sr=sample_rate, mono=True)

        if y_src.size < 512 or y_dub.size < 512:
            info["status"] = "skipped"
            info["reason"] = "Audio too short."
            sf.write(output_path, y_dub.astype(np.float32), sample_rate)
            return info

        result = y_dub.copy()

        # 1. Apply Dynamic EQ (Texture)
        if enable_eq and eq_blend > 0.05:
            print(f"         [PROSODY] Applying Dynamic EQ texture (blend={eq_blend:.2f})...")
            result = _transfer_multiband_eq(result, y_src, sample_rate, blend=eq_blend)
            info["eq_applied"] = True

        # 2. Apply Energy Envelope (Volume Arc)
        if enable_energy and energy_blend > 0.05:
            print(f"         [PROSODY] Applying Energy Envelope (blend={energy_blend:.2f})...")
            result = _transfer_energy(result, y_src, sample_rate, blend=energy_blend)
            info["energy_applied"] = True

        peak = float(np.max(np.abs(result))) if result.size else 0.0
        if peak > 0.98:
            result = result / peak * 0.94
        elif peak < 0.01:
            result = y_dub  # fallback

        # 4. Mathematical Noise Gate (Mute artifacts during pauses)
        # Compute local RMS. Use continuous soft gate to avoid popping/interruptions
        gate_rms = librosa.feature.rms(y=result, frame_length=512, hop_length=256)[0]
        gate_gain = np.interp(gate_rms, [0.008, 0.025], [0.0, 1.0])
        
        # Smooth the gate heavily to avoid sputtering
        gate_gain = gaussian_filter1d(gate_gain, sigma=4.0)
        
        # Apply gate to sample-level
        n_frames = len(gate_gain)
        frame_times = librosa.frames_to_time(np.arange(n_frames), sr=sample_rate, hop_length=256)
        sample_times = np.arange(len(result)) / sample_rate
        sample_gate = np.interp(sample_times, frame_times, gate_gain)
        
        result = result * sample_gate.astype(np.float32)

        # Soft fade edges
        fade_samples = min(int(sample_rate * 0.01), max(len(result) // 10, 1))
        if fade_samples > 1:
            result[:fade_samples] *= np.linspace(0.0, 1.0, fade_samples).astype(np.float32)
            result[-fade_samples:] *= np.linspace(1.0, 0.0, fade_samples).astype(np.float32)

        sf.write(output_path, result.astype(np.float32), sample_rate)
        print(f"         [PROSODY] Texture transfer complete -> {os.path.basename(output_path)}")

    except Exception as exc:
        info["status"] = "failed"
        info["error"] = str(exc)
        print(f"         [PROSODY] Transfer failed: {exc}. Using original dub.")
        try:
            y_dub, _ = librosa.load(dubbed_audio_path, sr=sample_rate, mono=True)
            sf.write(output_path, y_dub.astype(np.float32), sample_rate)
        except Exception:
            pass

    return info
