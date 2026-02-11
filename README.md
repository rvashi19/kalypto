Project Title: SP14 Emotion-Preserving AI Video Dubbing System

Team Members: Nishant Sai Challa - nishantsaichalla@uvic.ca
              Dharun Kosanam - dharunk@uvic.ca
              Ravi Vashi - Rvashi@uvic.ca


Project Statement :
When we watch a dubbed movie or video today, we often lose the "soul" of the original performance. Standard AI dubbing sounds like a robot reading a script, while human dubbing replaces the original actor’s voice entirely. Our project, the Emotion-Preserving AI Video Dubbing System, solves this by creating a middle ground. We are building a tool that "listens" to the original speaker to learn two things: exactly what their voice sounds like (their unique vocal fingerprint) and how they are feeling (the excitement, sadness, or anger in their tone). The system then translates their words into English and speaks them back using that same original voice, keeping the same emotional energy and timing. Essentially, we want to make it sound as if the person in the video suddenly learned how to speak English perfectly, keeping their personality and feelings completely intact.



Technical Stack:
Our system is built on a modular AI pipeline to ensure high performance and scalability.

Frontend (The User Interface)
1. React 18+ & Vite: For a fast, responsive single-page application.
2. Tailwind CSS: For a modern, premium "SaaS-style" dashboard.
3. Axios: For handling asynchronous API communication and video upload tracking.

Backend (The Brains)
1. FastAPI (Python): High-performance web framework for handling concurrent AI requests.
2. Uvicorn: ASGI server for production-grade speed.
3. FFmpeg: The core engine for video/audio manipulation, including audio extraction, time-stretching, and final muxing.

AI & Cloud Services
1. OpenAI (Whisper & GPT-4o): Used for precise timestamped transcription and nuance-aware translation.
2. ElevenLabs: State-of-the-art voice cloning and Speech-to-Speech (STS) synthesis to preserve prosody and emotion.              


Project Workflow
1. The Input Phase
Upload: The user uploads a video file (MP4/MOV) via the React frontend.
Preprocessing: The FastAPI backend receives the file and uses FFmpeg to separate the audio track from the video.

2. The Intelligence Phase (The AI Loop)
Transcription: The audio is sent to OpenAI Whisper (or similar) to transcribe the original speech into text with precise timestamps.
Translation: The text is translated into English while maintaining the original meaning and sentence length.
Vocal Analysis: The system analyzes the original audio to extract the speaker's unique "voiceprint" and emotional cues (pitch, speed, and intensity).

3. The Synthesis Phase
Voice Cloning: Using ElevenLabs, we generate the English speech. Instead of a generic voice, we use the extracted "voiceprint" so the English words sound like the original speaker.
Emotion Injection: We apply the captured emotional markers to the synthesized speech so the tone (joy, anger, etc.) matches the visual performance.

4. The Assembly Phase
Audio Mastering: FFmpeg adjusts the speed of the new English audio to match the original lip movements (Time-Stretching).
Final Render: The new English audio is merged back with the original video, replacing the old track.
Delivery: The final "Identity-Preserved" dubbed video is served back to the user on the Tailwind-styled dashboard for download and side-by-side comparison.

## Prerequisites

- **Python 3.8+**
- **Node.js & npm**
- **FFmpeg** (Recommended for real processing, but mocked in this prototype)

> **Note on FFmpeg**: The current `pipeline.py` mocks the heavy video processing to run without FFmpeg for demonstration purposes. To enable real video processing, you will need to install FFmpeg, add it to your system PATH, and uncomment the actual processing logic in `backend/services/pipeline.py`.

## Project Structure

- `backend/`: FastAPI application handling video uploads and processing (Mocked).
- `frontend/`: React application for the user interface.

## Getting Started

### 1. Backend Setup

Open a terminal in the `backend` directory:

```bash
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

Start the backend server:

```bash
uvicorn main:app --reload
```

The backend runs on `http://localhost:8000`.

### 2. Frontend Setup

Open a new terminal in the `frontend` directory:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173`.

## Usage

1. Open `http://localhost:5173` in your browser.
2. Upload a short video file.
3. Watch the progress bars as the system "processes" your video.
4. Once complete, compare the "Original", "Prototyped Generic", "Cloned", and "Emotion" outputs (Currently all copies of the original in this mock).

## Configuration

To enable real AI features (if you modify the code):

1. Copy `backend/.env.example` to `backend/.env`.
2. Add your OpenAI and ElevenLabs API keys.
3. Update `backend/services/pipeline.py` to use `openai` and `elevenlabs-api` calls instead of `time.sleep`.

## Troubleshooting

- **Upload Fails**: Ensure the backend is running on port 8000.
- **Playback Fails**: ensure the backend is running so it can serve the video files from `uploads` and `outputs`.
