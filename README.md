# Emotion-Preserving AI Video Dubbing System

This repository contains a local FastAPI + React application and a modular Python audio pipeline for emotion-preserving video dubbing. The current implementation emphasizes a MIR-first flow: it analyzes acoustic features from the source speech, maps them into a continuous valence/arousal space, synthesizes translated speech, time-matches the result, applies DTW-guided alignment, and remuxes the dubbed audio back into video for localhost playback.

## What the app does

- Upload a video from the localhost website
- Choose a target language for dubbing
- Extract and normalize the source audio
- Segment speech chunks using silence-aware preprocessing with segment merging
- Extract an acoustic fingerprint using Librosa-based MIR features
- Estimate continuous valence/arousal values from acoustic evidence
- Transcribe and translate speech with OpenAI when credentials are available
- Synthesize translated speech with ElevenLabs or gTTS fallback
- Match segment durations, assemble a dubbed timeline, and DTW-warp it onto the source timing
- Remux the final dubbed audio into a downloadable video
- Display MIR evaluation outputs and artifact downloads in the frontend

## Architecture

The modular source of truth lives in `backend/pipeline/`.

- `ingest.py`: FFmpeg/librosa ingestion and speech sanity checks
- `preprocess.py`: silence-based segmentation with padding and short-segment merging
- `analyze.py`: acoustic fingerprint extraction (`F0`, RMS, MFCCs, spectral centroid, spectral flux, onset density, syllabic-rate proxy, jitter/shimmer proxies, harmonicity proxy)
- `emotion_map.py`: maps acoustic statistics into continuous valence/arousal
- `transcribe_translate.py`: OpenAI transcription/translation with demo fallbacks
- `synthesize.py`: ElevenLabs/gTTS synthesis with language-aware fallback
- `align.py`: duration matching and DTW-guided time warping
- `evaluate.py`: raw vs aligned pitch/energy/MCD evaluation plus plot generation
- `orchestrator.py`: end-to-end run coordination, artifact writing, and video remuxing

The web app uses the same modular pipeline through `backend/services/pipeline.py`, which now acts only as a FastAPI job adapter.

## Local website

The frontend is meant to run on `http://127.0.0.1:5173`, with the API on `http://127.0.0.1:8010`.

### Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --host 127.0.0.1 --port 8010
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

After both services start, open `http://127.0.0.1:5173`, upload a dialogue video, choose a language, and wait for the dubbed output plus MIR metrics. For the presentation, the safest flow is the built-in Bollywood-style Hindi demo translated into English.

## Outputs

Each job writes artifacts under `backend/outputs/<job_id>/`.

- `source_audio.wav`
- `dubbed_audio_raw.wav`
- `dubbed_audio.wav`
- `dubbed_video.mp4` when the input is a video and FFmpeg remux succeeds
- `comparison_plot.png`
- `pipeline_results.json`
- `segment_manifest.json`
- `run_summary.txt`
- `transcription.txt`
- `translation.txt`

## CLI pipeline

You can still run the modular pipeline directly:

```powershell
.\backend\venv\Scripts\python.exe run_pipeline.py --input demo_video.mp4 --target-lang Spanish
```

## Current limitations

- Voice identity preservation is still synthesis-service dependent and not yet a full speaker-cloning research pipeline in the modular path.
- Jitter, shimmer, and harmonicity are currently transparent MIR proxies rather than Praat-grade measurements.
- Plot rendering is currently image-based; interactive frontend visualization can still be extended further.
- Better VAD, richer cross-lingual prosody transfer, and stronger human-speech benchmarking remain good next steps.
