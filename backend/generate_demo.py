import os
import shutil
import ffmpeg
from elevenlabs import ElevenLabs
from dotenv import load_dotenv

# Load keys
load_dotenv()
api_key = os.getenv("ELEVENLABS_API_KEY")

if not api_key:
    print("Error: No ElevenLabs API Key found in .env")
    exit(1)

client = ElevenLabs(api_key=api_key)

print("Generating Gujarati Audio...")
text_gujarati = "Namaste. Aa video amara nava dubbing system no test che. Swagat che tamaru."

try:
    # v1.x / modern SDK pattern
    audio_gen = client.text_to_speech.convert(
        text=text_gujarati,
        voice_id="21m00Tcm4TlvDq8ikWAM", # Rachel
        model_id="eleven_multilingual_v2"
    )

    audio_path = "gujarati_test.mp3"
    with open(audio_path, "wb") as f:
        # Handle bytes vs generator
        if isinstance(audio_gen, bytes):
            f.write(audio_gen)
        else:
            for chunk in audio_gen:
                f.write(chunk)
    
    print("Audio generated successfully.")

    # Generate Video
    print("Generating Video...")
    video_path = "gujarati_demo.mp4"
    
    # Create a 5-second blue video (or duration of audio if we check it, but generic 5s is fine for MVP)
    # Actually, let's make it match audio + 1 sec
    
    # We will use a simple color source.
    # We combine it with the audio.
    input_audio = ffmpeg.input(audio_path)
    input_video = ffmpeg.input('color=c=orange:s=1280x720', f='lavfi')
    
    (
        ffmpeg
        .output(input_video, input_audio, video_path, t=5, vcodec='libx264', acodec='aac', shortest=True)
        .overwrite_output()
        .run(quiet=True)
    )
    
    print(f"Video saved to: {os.path.abspath(video_path)}")
    
    # Copy to Desktop/beta if exists
    desktop_path = os.path.expanduser("~/Desktop/beta")
    if os.path.exists(desktop_path):
        shutil.copy(video_path, os.path.join(desktop_path, video_path))
        print(f"Copied to {desktop_path}")
        
except Exception as e:
    print(f"Failed: {e}")
