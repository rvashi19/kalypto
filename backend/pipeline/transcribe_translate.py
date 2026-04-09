import os

from .demo_script import (
    CURATED_DEMO_SEGMENTS,
    get_demo_full_transcript,
    get_demo_full_translation,
    get_showcase_demo_translation,
)
from .performance_direction import build_translation_prompt

DEMO_TRANSCRIPT = "[Audio transcription unavailable]"
DEMO_TRANSLATIONS = {
    "english": "[Translation unavailable]",
    "spanish": "[Traduccion no disponible]",
    "french": "[Traduction indisponible]",
    "german": "[Ubersetzung nicht verfugbar]",
    "hindi": "[Anuvaad upalabdh nahin hai]",
    "gujarati": "[Anuvad uplabdh nathi]",
    "italian": "[Traduzione non disponibile]",
    "portuguese": "[Traducao indisponivel]",
    "japanese": "[Translation unavailable]",
}

def get_demo_transcript() -> str:
    return get_demo_full_transcript()


def get_demo_translation(target_lang: str) -> str | None:
    return get_demo_full_translation(target_lang)


def get_showcase_translation(index: int, target_lang: str) -> str | None:
    return get_showcase_demo_translation(index, target_lang)


def get_demo_segment(index: int, target_lang: str) -> tuple[str, str] | None:
    if index >= len(CURATED_DEMO_SEGMENTS):
        return None

    segment = CURATED_DEMO_SEGMENTS[index]
    if target_lang.strip().lower() == "english":
        translated = segment["english"]
    elif target_lang.strip().lower() == "hindi":
        translated = segment["hindi"]
    else:
        translated = None

    return segment["hindi"], translated


def get_placeholder_translation(target_lang: str) -> str:
    return DEMO_TRANSLATIONS.get(target_lang.strip().lower(), DEMO_TRANSLATIONS["english"])


def _normalize_dialogue_text(text: str) -> str:
    normalized = text or ""
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
    }
    for src, dest in replacements.items():
        normalized = normalized.replace(src, dest)
    return " ".join(normalized.split()).strip()


def _polish_english_dialogue(text: str, target_lang: str) -> str:
    if target_lang.strip().lower() != "english":
        return text

    polished = text
    replacements = {
        "something little": "something small",
        "a little thing": "a small thing",
        "it won't come to her": "it just won't come to her",
        "it won't come to him": "it just won't come to him",
    }
    for src, dest in replacements.items():
        polished = polished.replace(src, dest)
        polished = polished.replace(src.capitalize(), dest.capitalize())
    return polished

class TranslationService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")

    def transcribe(self, audio_path: str, output_dir: str, artifact_name: str = "transcription.txt") -> tuple[str, bool]:
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

        out_path = os.path.join(output_dir, artifact_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"[DEMO MODE]\n{text}" if used_demo else text)
        return text, used_demo

    def translate(
        self,
        text: str,
        target_lang: str,
        output_dir: str,
        artifact_name: str = "translation.txt",
        source_duration_s: float | None = None,
        tighten: bool = False,
        expand: bool = False,
        valence: float | None = None,
        arousal: float | None = None,
        feature_stats: dict | None = None,
        previous_context: str | None = None,
        next_context: str | None = None,
    ) -> tuple[str, bool]:
        used_demo = False
        print(f"[TRANSLATE] Translating to {target_lang}...")

        if not self.api_key:
            translated = get_placeholder_translation(target_lang)
            used_demo = True
        else:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.api_key)
                user_content = []
                if previous_context:
                    user_content.append(f"Previous dialogue for context only: {previous_context}")
                user_content.append(f"Current dialogue to translate: {text}")
                if next_context:
                    user_content.append(f"Next dialogue for context only: {next_context}")
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": build_translation_prompt(
                                target_lang,
                                source_duration_s=source_duration_s,
                                tighten=tighten,
                                expand=expand,
                                valence=valence,
                                arousal=arousal,
                                feature_stats=feature_stats,
                            ),
                        },
                        {"role": "user", "content": "\n".join(user_content)}
                    ]
                )
                translated = _normalize_dialogue_text(response.choices[0].message.content)
            except Exception as e:
                print(f"         GPT API failed: {e}. Using demo translation.")
                translated = get_placeholder_translation(target_lang)
                used_demo = True

        translated = _normalize_dialogue_text(translated)
        translated = _polish_english_dialogue(translated, target_lang)
        out_path = os.path.join(output_dir, artifact_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"[DEMO MODE]\n{translated}" if used_demo else translated)
        return translated, used_demo
