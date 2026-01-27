# Emotion-Preserving AI Video Dubbing System (Prototype)

This is a prototype application that demonstrates the workflow of an AI video dubbing system. It includes a FastAPI backend and a React (Vite) frontend.

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
