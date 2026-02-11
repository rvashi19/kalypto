# SP14 Emotion-Preserving AI Video Dubbing System

## Project Overview

When we watch a dubbed movie or video today, we often lose the *soul* of the original performance. Traditional AI dubbing systems produce flat, robotic speech, while human dubbing replaces the original speaker’s voice entirely.

The **Emotion-Preserving AI Video Dubbing System** bridges this gap by analyzing the original speaker’s **voice identity** and **emotional prosody**, translating the speech into English, and re-synthesizing it so that it sounds as if the original speaker is speaking English naturally—**with their personality, timing, and emotional energy preserved**.

This project is developed as part of **CSC 475 – Music Information Retrieval (University of Victoria)**. The README serves as the **design and requirement specification**, and will be expanded into the final project report and later formatted as an ISMIR paper in LaTeX.

---

## Team Members

- **Nishant Sai Challa** – nishantsaichalla@uvic.ca  
- **Dharun Kosanam** – dharunk@uvic.ca  
- **Ravi Vashi** – rvashi@uvic.ca  

---

## Problem Statement & Motivation

Global video content consumption continues to grow, but language remains a major accessibility barrier. Existing dubbing approaches suffer from one or more of the following limitations:

- Loss of emotional nuance  
- Loss of speaker identity  
- High cost and long production timelines  

Automated text-to-speech dubbing fails to preserve prosody and affect, while professional dubbing replaces the original voice entirely. Our project aims to solve this by creating an **identity- and emotion-preserving speech-to-speech translation pipeline**.

The system focuses on preserving:
- **Who is speaking** (voiceprint)
- **How they feel** (emotion, energy, timing)
- **What they say** (accurate, context-aware translation)

Target applications include educational content, interviews, documentaries, accessibility tools, and user-generated media.

---

## System Architecture & Workflow

### 1. Input Phase
- User uploads a video file (MP4/MOV) via a React frontend.
- FastAPI backend receives the file.
- FFmpeg extracts the audio track.

### 2. Intelligence Phase (AI Loop)
- **Transcription:** OpenAI Whisper generates timestamped text.
- **Translation:** GPT-4o translates speech into English while preserving meaning and sentence length.
- **Vocal & Emotion Analysis:**
  - Speaker voice characteristics (“voiceprint”)
  - Emotional cues (pitch, speed, intensity, energy)

### 3. Synthesis Phase
- **Voice Cloning:** ElevenLabs generates English speech using the cloned voice of the original speaker.
- **Emotion Injection:** Emotional parameters are applied so the tone (joy, anger, sadness, etc.) matches the original delivery.

### 4. Assembly Phase
- FFmpeg time-stretches synthesized audio to match original timing.
- The new English audio replaces the original audio track.
- The final dubbed video is returned to the user for download and comparison.

---

## Technical Stack

### Frontend
- React 18+ & Vite
- Tailwind CSS
- Axios

### Backend
- FastAPI (Python)
- Uvicorn
- FFmpeg

### AI & Cloud Services
- OpenAI Whisper (speech-to-text)
- OpenAI GPT-4o (translation)
- ElevenLabs (voice cloning & speech synthesis)

---

## Tools, Datasets & Related Work

### Datasets
- **RAVDESS** – Emotional speech dataset for emotion recognition
- **ESD** – Multilingual emotional speech dataset
- **Mozilla Common Voice** – Large-scale multilingual speech corpus
- **Custom Test Corpus** – Curated real-world video clips

### Research Areas
- Speech Emotion Recognition (SER)
- Expressive Text-to-Speech (TTS)
- Voice Cloning & Speaker Embeddings
- Cross-lingual Speech Translation
- Prosody and Emotion Transfer

---

## Project Timeline

| Phase | Objectives |
|------|-----------|
| Weeks 1–2 | Literature review, dataset setup, audio extraction pipeline |
| Weeks 3–4 | Transcription and translation integration |
| Weeks 5–6 | Voice cloning and emotion analysis |
| Weeks 7–8 | End-to-end evaluation and refinement |
| Week 9 | Final report (ISMIR format) and presentation |

---

## Individual Objectives & Performance Indicators

### Nishant Sai Challa

**Objective:** Core backend pipeline and AI integration  

- **PI1 (Basic):** Implement FFmpeg-based audio extraction  
- **PI2 (Basic):** Integrate Whisper transcription  
- **PI3 (Expected):** Integrate GPT-4o translation  
- **PI4 (Expected):** Implement FastAPI orchestration and error handling  
- **PI5 (Advanced):** Optimize pipeline latency via parallel processing  

---

### Dharun Kosanam

**Objective:** Emotion analysis and synthesis quality  

- **PI1 (Basic):** Extract pitch and energy features from speech  
- **PI2 (Basic):** Implement baseline TTS comparison  
- **PI3 (Expected):** Integrate emotion classification model  
- **PI4 (Expected):** Apply emotion-aware synthesis parameters  
- **PI5 (Advanced):** Quantitatively evaluate emotion preservation  

---

### Ravi Vashi

**Objective:** Frontend development, evaluation, and usability  

- **PI1 (Basic):** Build React-based video upload interface  
- **PI2 (Basic):** Implement video comparison player  
- **PI3 (Expected):** Visualize processing progress and pipeline stages  
- **PI4 (Expected):** Conduct user testing and collect feedback  
- **PI5 (Advanced):** Design evaluation dashboard for side-by-side comparison  

---

## References
