import os

DEMO_TRANSCRIPT = "[Unverified Audio Segment]"
DEMO_TRANSLATION = "[Segmento de audio no verificado]"

class TranslationService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")

    def transcribe(self, audio_path: str, output_dir: str) -> tuple[str, bool]:
        used_demo = False
        print("[TRANSCRIBE] Starting transcription...")
        
        if not self.api_key:
            print("         No OpenAI API key -- using demo transcript.")
            text = DEMO_TRANSCRIPT
            used_demo = True
        else:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.api_key)
                with open(audio_path, "rb") as f:
                    transcript = client.audio.transcriptions.create(model="whisper-1", file=f)
                text = transcript.text
                safe_print = text.encode('ascii', 'replace').decode('ascii')
                print(f"         API Success: \"{safe_print}\"")
            except Exception as e:
                print(f"         Whisper API failed: {e}. Using demo text.")
                text = DEMO_TRANSCRIPT
                used_demo = True

        out_path = os.path.join(output_dir, "transcription.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"[DEMO MODE]\n{text}" if used_demo else text)
        return text, used_demo

    def translate(self, text: str, target_lang: str, output_dir: str) -> tuple[str, bool]:
        used_demo = False
        print(f"[TRANSLATE] Translating to {target_lang}...")

        if not self.api_key:
            translated = DEMO_TRANSLATION
            used_demo = True
        else:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.api_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"Translate to {target_lang}. Output ONLY translated text."},
                        {"role": "user", "content": text}
                    ]
                )
                translated = response.choices[0].message.content.strip()
            except Exception as e:
                print(f"         GPT API failed: {e}. Using demo translation.")
                translated = DEMO_TRANSLATION
                used_demo = True

        out_path = os.path.join(output_dir, "translation.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"[DEMO MODE]\n{translated}" if used_demo else translated)
        return translated, used_demo
