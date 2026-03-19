import os
import subprocess
import numpy as np
import soundfile as sf
import librosa

def synthesize_speech(text: str, valence: float, arousal: float, output_dir: str, output_filename: str = "dubbed_audio.wav", sample_rate: int = 16000) -> str:
    """
    Generate dubbed audio via TTS.
    Primary: ElevenLabs (with valence-arousal mapped parameters).
    Fallback: gTTS (Google Text-to-Speech).
    """
    print(f"[SYNTHESIZE] Synthesizing dubbed speech for {output_filename}...")
    output_path = os.path.join(output_dir, output_filename)
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")

    if not text or not text.strip():
        print("         Skipping TTS -- no text available.")
        silence = np.zeros(sample_rate * 2, dtype=np.float32)
        sf.write(output_path, silence, sample_rate)
        return output_path

    # ElevenLabs mapping
    if elevenlabs_key:
        try:
            print("         Trying ElevenLabs TTS...")
            from elevenlabs import ElevenLabs, VoiceSettings
            client = ElevenLabs(api_key=elevenlabs_key)
            
            stability = max(0.1, 1.0 - arousal)
            similarity_boost = max(0.1, valence)

            audio_gen = client.text_to_speech.convert(
                text=text,
                voice_id="pNInz6obpgDQGcFmaJgB",
                model_id="eleven_multilingual_v2",
                voice_settings=VoiceSettings(
                    stability=stability,
                    similarity_boost=similarity_boost,
                    style=arousal,
                    use_speaker_boost=True
                )
            )

            mp3_path = output_path.replace(".wav", ".mp3")
            with open(mp3_path, "wb") as f:
                if isinstance(audio_gen, bytes):
                    f.write(audio_gen)
                else:
                    for chunk in audio_gen:
                        f.write(chunk)

            _convert_to_wav(mp3_path, output_path, sample_rate)
            print(f"         ElevenLabs TTS success -> {output_path}")
            return output_path

        except Exception as e:
            print(f"         ElevenLabs failed: {e}. Falling back to gTTS...")

    # Fallback: gTTS
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="es")
        mp3_path = output_path.replace(".wav", "_gtts.mp3")
        tts.save(mp3_path)
        _convert_to_wav(mp3_path, output_path, sample_rate)
        print(f"         gTTS success -> {output_path}")
        return output_path
    except Exception as e:
        print(f"         gTTS failed: {e}. Generating silence.")
        silence = np.zeros(sample_rate * 2, dtype=np.float32)
        sf.write(output_path, silence, sample_rate)
        return output_path

def _convert_to_wav(mp3_path: str, output_path: str, sample_rate: int):
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", os.path.abspath(mp3_path),
            "-ac", "1", "-ar", str(sample_rate),
            "-acodec", "pcm_s16le", os.path.abspath(output_path)
        ], capture_output=True, check=True)
        os.remove(mp3_path)
    except Exception:
        y_tts, _ = librosa.load(mp3_path, sr=sample_rate, mono=True)
        sf.write(output_path, y_tts, sample_rate)
        os.remove(mp3_path)
