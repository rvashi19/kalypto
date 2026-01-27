from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Optional
import shutil
import os
import uuid
from services.pipeline import process_video_job

router = APIRouter()

# In-memory storage for job status (replace with proper DB in production)
jobs: Dict[str, Dict] = {}

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

class JobStatus(BaseModel):
    job_id: str
    status: str  # 'processing', 'completed', 'failed'
    progress: Optional[float] = 0.0
    message: Optional[str] = None
    results: Optional[Dict[str, str]] = None

@router.post("/upload", response_model=JobStatus)
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0.0,
        "file_path": file_path,
        "filename": file.filename
    }

    background_tasks.add_task(process_video_job, job_id, file_path, jobs)

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
