from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form
from pydantic import BaseModel
from typing import Any, Dict, Optional
import shutil
import os
import uuid
from services.pipeline import process_video_job

router = APIRouter()

# In-memory storage for job status (replace with proper DB in production)
jobs: Dict[str, Dict] = {}

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
DEMO_VIDEO_CANDIDATES = [
    os.path.join(PROJECT_DIR, "WhatsApp Video 2026-04-08 at 7.35.05 PM.mp4"),
    os.path.join(PROJECT_DIR, "demo_video.mp4"),
]
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _resolve_demo_video_path() -> str | None:
    for candidate in DEMO_VIDEO_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None

class JobStatus(BaseModel):
    job_id: str
    status: str  # 'processing', 'completed', 'failed'
    progress: Optional[float] = 0.0
    message: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    target_language: Optional[str] = None

@router.post("/upload", response_model=JobStatus)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_language: str = Form("English"),
):
    job_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0.0,
        "file_path": file_path,
        "filename": file.filename,
        "target_language": target_language,
    }

    background_tasks.add_task(process_video_job, job_id, file_path, target_language, jobs)

    return jobs[job_id]

@router.post("/demo", response_model=JobStatus)
async def run_demo(background_tasks: BackgroundTasks, target_language: str = Form("English")):
    demo_video_path = _resolve_demo_video_path()
    if not demo_video_path:
        raise HTTPException(status_code=404, detail="Built-in demo video not found")

    job_id = str(uuid.uuid4())
    demo_copy_path = os.path.join(UPLOAD_DIR, f"{job_id}_showcase_demo.mp4")
    shutil.copy2(demo_video_path, demo_copy_path)

    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0.0,
        "file_path": demo_copy_path,
        "filename": os.path.basename(demo_video_path),
        "target_language": target_language,
        "message": "Queued showcase demo clip...",
    }

    background_tasks.add_task(process_video_job, job_id, demo_copy_path, target_language, jobs)
    return jobs[job_id]

@router.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@router.get("/result/{job_id}")
async def get_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    # In a real app, you might serve files or return signed URLs
    # For this prototype, we'll return the paths/urls assuming static serving
    return jobs[job_id].get("results", {})
