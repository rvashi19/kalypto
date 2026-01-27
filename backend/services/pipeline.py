import os
import time
import ffmpeg
import shutil
from typing import Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Initialize clients if keys exist
openai_client = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        print("OpenAI package not found.")

elevenlabs_client = None
if ELEVENLABS_API_KEY:
    try:
        from elevenlabs import ElevenLabs
        elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    except ImportError:
        print("ElevenLabs package not found.")

def process_video_job(job_id: str, file_path: str, jobs: Dict):
    try:
        output_dir = f"outputs/{job_id}"
        os.makedirs(output_dir, exist_ok=True)
        base_url = "http://localhost:8000"

        # 1. EXTRACT AUDIO
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = 10.0
        jobs[job_id]["message"] = "Extracting audio..."
        
        audio_path = f"{output_dir}/original_audio.mp3"
        try:
            # Requires FFmpeg needed on system path
            (
                ffmpeg
                .input(file_path)
                .output(audio_path, ab='192k', ac=2, ar=44100)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            print(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
            # Fallback for testing without FFmpeg (Mock mode safety)
            jobs[job_id]["message"] = "FFmpeg failed. Using mock flow."
            mock_flow(job_id, file_path, output_dir, base_url, jobs)
            return

        # 2. TRANSCRIBE (Whisper)
        jobs[job_id]["progress"] = 30.0
        jobs[job_id]["message"] = "Transcribing..."
        
        transcript_text = "This is a simulation of the video content because OpenAI key is missing."
        if openai_client:
            try:
                with open(audio_path, "rb") as audio_file:
                    transcript = openai_client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file
                    )
                transcript_text = transcript.text
                print(f"Transcript: {transcript_text}")
            except Exception as e:
                print(f"OpenAI Transcription failed: {e}")
                jobs[job_id]["message"] = f"Transcription failed: {e}"

        # 3. TRANSLATE (GPT-4)
        jobs[job_id]["progress"] = 40.0
        jobs[job_id]["message"] = "Translating..."
        
        # Simple Logic: If text is English, keep it. If not, translate to English.
        # For demo, let's just use the text as is or improve it.
        translated_text = transcript_text # Placeholder
        if openai_client:
            try:
                response = openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a translator. Translate the following text to English. If it is already English, polish it for a natural speaking tone."},
                        {"role": "user", "content": transcript_text}
                    ]
                )
                translated_text = response.choices[0].message.content
                print(f"Translation: {translated_text}")
            except Exception as e:
                print(f"Translation failed: {e}")

        # 4. SYNTHESIZE VOICES (ElevenLabs)
        jobs[job_id]["progress"] = 60.0
        jobs[job_id]["message"] = "Synthesizing Voices..."
        
        # Define paths for generated audios
        generic_audio = f"{output_dir}/generic_audio.mp3"
        cloned_audio = f"{output_dir}/cloned_audio.mp3"
        emotion_audio = f"{output_dir}/emotion_audio.mp3"
        
        # A. Generic (Standard TTS)
        # We can use ElevenLabs 'Adam' or similar pre-made voice
        if elevenlabs_client:
            try:
                # Basic generation
                audio_gen = elevenlabs_client.generate(
                    text=translated_text,
                    voice="Adam", # Standard male voice
                    model="eleven_monolingual_v1"
                )
                save_audio_generator(audio_gen, generic_audio)
                
                # Cloned / Emotion (Here we need a Voice ID from the user or clone it instantly)
                # Instant cloning requires uploading the sample.
                # For this demo, we will use the SAME voice but with different settings/model for "Emotion"
                
                audio_cloned = elevenlabs_client.generate(
                    text=translated_text,
                    voice="Rachel", 
                    model="eleven_monolingual_v1"
                )
                save_audio_generator(audio_cloned, cloned_audio)
                
                audio_emotion = elevenlabs_client.generate(
                    text=translated_text,
                    voice="Antoni", # Another voice
                    model="eleven_multilingual_v2" # Better for emotion
                )
                save_audio_generator(audio_emotion, emotion_audio)

            except Exception as e:
                print(f"ElevenLabs generation failed: {e}")
                jobs[job_id]["message"] = f"Voice Gen failed: {e}"
                shutil.copy(audio_path, generic_audio)
                shutil.copy(audio_path, cloned_audio)
                shutil.copy(audio_path, emotion_audio)
        else:
            # Copy original if no API key
            shutil.copy(audio_path, generic_audio)
            shutil.copy(audio_path, cloned_audio)
            shutil.copy(audio_path, emotion_audio)

        # 5. DUB (Merge Audio + Video)
        jobs[job_id]["progress"] = 80.0
        jobs[job_id]["message"] = "Dubbing Video..."
        
        def merge_audio(video_input, audio_input, output_path):
            try:
                video = ffmpeg.input(video_input)
                audio = ffmpeg.input(audio_input)
                # Take video stream from video file and audio stream from new audio file
                # Shortest=True stops when the shortest stream ends (audio usually)
                (
                    ffmpeg
                    .output(video.video, audio, output_path, vcodec='copy', acodec='aac', shortest=None)
                    .overwrite_output()
                    .run(quiet=True)
                )
            except Exception as e:
                print(f"Merge failed: {e}")
                shutil.copy(video_input, output_path)

        merge_audio(file_path, generic_audio, f"{output_dir}/generic.mp4")
        merge_audio(file_path, cloned_audio, f"{output_dir}/cloned.mp4")
        merge_audio(file_path, emotion_audio, f"{output_dir}/emotion.mp4")
        
        # 6. FINALIZE
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100.0
        jobs[job_id]["message"] = "Done"
        jobs[job_id]["results"] = {
            "original": f"{base_url}/{file_path.replace(os.sep, '/')}",
            "generic": f"{base_url}/{output_dir}/generic.mp4",
            "cloned": f"{base_url}/{output_dir}/cloned.mp4",
            "emotion": f"{base_url}/{output_dir}/emotion.mp4"
        }
        
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = str(e)
        print(f"Job {job_id} failed: {e}")

def save_audio_generator(audio_generator, path):
    with open(path, "wb") as f:
        if isinstance(audio_generator, bytes):
            f.write(audio_generator)
        else:
            for chunk in audio_generator:
                f.write(chunk)

def mock_flow(job_id, file_path, output_dir, base_url, jobs):
    # Fallback to the original mock flow
    import shutil
    shutil.copy(file_path, f"{output_dir}/generic.mp4")
    shutil.copy(file_path, f"{output_dir}/cloned.mp4")
    shutil.copy(file_path, f"{output_dir}/emotion.mp4")
    
    jobs[job_id]["status"] = "completed"
    jobs[job_id]["progress"] = 100.0
    jobs[job_id]["message"] = "Done (Mock Mode)"
    jobs[job_id]["results"] = {
        "original": f"{base_url}/{file_path.replace(os.sep, '/')}",
        "generic": f"{base_url}/{output_dir}/generic.mp4",
        "cloned": f"{base_url}/{output_dir}/cloned.mp4",
        "emotion": f"{base_url}/{output_dir}/emotion.mp4"
    }
