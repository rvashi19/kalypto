# Emotion-Preserving AI Video Dubbing System
## Architectural Overview

This document acts as the comprehensive guide to the "Ins and Outs" of the Emotion-Preserving AI Video Dubbing System. The project replaces generic translation workflows by focusing heavily on **Music Information Retrieval (MIR)** and **Digital Signal Processing (DSP)** algorithms to preserve the human emotional arcs and timing present in original video sources.

---

## 📥 **Inputs to the System**
1. **Source Media:** A video file (e.g., MP4, MOV) containing the original spoken dialogue.
2. **Target Language:** The desired language to translate and dub the video into.
3. **Environment Flags:** Configuration files (`.env`) specifying API Keys (OpenAI, ElevenLabs) and dynamic fallback toggles.

---

## ⚙️ **The Core Pipeline (Ins -> Outs Flow)**

The system operates via a highly modular pipeline coordinated by the `DubbingOrchestrator` (`orchestrator.py`). The pipeline stages are executed as follows:

### 1. Ingestion (`ingest.py`)
- **Action:** Strips the audio track from the uploaded video file using `ffmpeg`.
- **Output:** Raw 16kHz WAV format source audio.

### 2. Preprocessing & Segmentation (`preprocess.py`)
- **Action:** Divides the global source audio into logically smaller, manageable chunks or spoken clauses based on significant pauses.
- **Output:** A list of segment WAV files and metadata containing original timestamps.

### 3. Acoustic Analysis (`analyze.py`)
- **Action:** Runs MIR algorithms (using `librosa`) across each segmented chunk to mathematically interpret the speaker's vocal traits.
- **Extracted Features:** 
  - F0 (Fundamental Pitch)
  - RMS (Root Mean Square Energy/Volume)
  - Spectral Flux (Changes in frequency density)
  - Jitter / Shimmer (Vocal roughness)

### 4. Emotion Mapping (`emotion_map.py`)
- **Action:** Translates the raw acoustic features into a continuous emotional 2D plane.
- **Output:** 
  - **Valence** (Positivity/Negativity)
  - **Arousal** (Intensity/Calmness) 

### 5. Transcription & Translation (`transcribe_translate.py`)
- **Action:** Transcribes the source segments into text (handling the original language). It then acts as an intelligent translator, utilizing the previous segment's context and the mathematical `Valence`/`Arousal` values to guarantee the translation reflects the appropriate emotional tone.
- **Output:** Localized textual scripts tailored to fit the chronological timing of the source video.

### 6. Voice Synthesis (`synthesize.py`)
- **Action:** Drives Text-To-Speech (TTS) engines (ElevenLabs Speech-to-Speech / OpenAI TTS). 
- **The Magic:** Dynamically adjusts the prompt, speed, and API `stability/style` flags based on the `Valence`/`Arousal` metadata to get as close as possible to the emotion of the original text. It mathematically recreates natural pauses using silence interval extraction.
- **Output:** Raw synthesized audio in the target language.

### 7. Emotional Prosody Transfer (`prosody_transfer.py`)
*This is the core DSP manipulation identifying this system.*
- **Action:** Directly maps the emotional acoustic wave traits of the source voice onto the newly generated synthetic voice.
- **How it works:**
    - **Energy Envelope Matching:** Matches the exact local volume swells of the source.
    - **Multiband Dynamic EQ:** Adjusts Low/Mid/High frequencies dynamically. If the speaker gets raspy or bassy, the AI voice accurately mirrors this texture.
    - **Soft Noise Gating:** Uses heavily smoothed, continuous volume gates instead of harsh limits to mute any digital artifacts between words without popping or stuttering.

### 8. Strict Timeline Alignment (`align.py`)
- **Action:** Uses **Dynamic Time Warping (DTW)** heavily weighted by MFCCs and RMS Energy. 
- **The Magic:** Instead of naive phase-vocoding which causes voice staggering/algorithmic lag, this algorithm identifies pauses and strictly matches them, ensuring the dub stays 100% synchronized with the video lip-movements and visual pacing. Applies post-DTW soft-gating to prevent resampling background chirps.

### 9. Timeline Assembly & Final Render (`orchestrator.py`)
- **Action:** Muxes the aligned chunks together into a single master audio track with crossfade rendering. It finally merges this new dub back onto the original `mp4` video.
- **Output:** The final Dubbed Video.

### 10. Evaluation against Source (`evaluate.py`)
- **Action:** Compares the final dubbed track against the source track to score its success algorithmically.
- **Output Metrics:** MCD (Mel Cepstral Distortion score), Pitch Correlation, Energy Correlation.

---

## 📤 **Final Complete Outputs**
When a processing run concludes, the system deposits the following in the `output/results` directory:
- `dubbed_video.mp4`: **The final integrated video result.**
- `dubbed_audio.wav`: The standalone master dubbed audio.
- `pipeline_results.json`: A massive file covering the metadata, timing shifts, evaluation metrics, and API payloads executed.
- `transcription.txt` & `translation.txt`: Human-readable localized scripts.
- `run_summary.txt`: An executive textual breakdown of operations.

## 🔑 **Key Engineering Highlights applied over recent iterations**
- **Syllable-Preserving Alignment:** Avoids "lagging" audio by mapping silence strictly to silence; prevents the AI voice from drifting forward or backward out-of-sync with video cuts.
- **Artifact Suppression:** Utilizing continuous interpolation and Gaussian smoothed mathematical noise gates strictly prevents TTS metadata-hiss or distortion clicks near pauses, keeping output undeniably *clear*.
