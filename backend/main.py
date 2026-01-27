from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.router import api_router
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Emotion-Preserving Video Dubbing API")

# Configure CORS
origins = [
    "http://localhost:5173",  # Vite default port
    "http://localhost:3000",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Video Dubbing API is running"}

from fastapi.staticfiles import StaticFiles
# Mount the outputs directory to serve generated files
os.makedirs("outputs", exist_ok=True)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# Mount the uploads directory to serve original files
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
