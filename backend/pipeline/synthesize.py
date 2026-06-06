import hashlib
import json
import os
import re
import subprocess
import tempfile
import numpy as np
import soundfile as sf
import librosa
import requests

from .audio_post import finalize_audio
from .performance_direction import build_clause_instructions, build_openai_instructions

GTTS_LANGUAGE_MAP = {
    "arabic": "ar",
    "english": "en",
    "french": "fr",
    "german": "de",
    "gujarati": "gu",
    "hindi": "hi",
    "italian": "it",
    "japanese": "ja",
    "korean": "ko",
    "portuguese": "pt",
    "spanish": "es",
}
LANGUAGE_CODE_MAP = {
    "arabic": "ar",
    "english": "en",
    "french": "fr",
    "german": "de",
    "gujarati": "gu",
    "hindi": "hi",
    "italian": "it",
    "japanese": "ja",
    "korean": "ko",
    "portuguese": "pt",
    "spanish": "es",
}
DEFAULT_ELEVENLABS_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
VOICE_CACHE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "outputs", "elevenlabs_voice_cache.json")
)
DEFAULT_ELEVENLABS_STS_MODEL_ID = "eleven_multilingual_sts_v2"
DEFAULT_ELEVENLABS_ENGLISH_STS_MODEL_ID = "eleven_english_sts_v2"
DEFAULT_ELEVENLABS_STS_OUTPUT_FORMAT = "wav_24000"


def _resolve_tts_language(target_lang: str) -> str:
    return GTTS_LANGUAGE_MAP.get(target_lang.strip().lower(), "en")


def _resolve_language_code(target_lang: str) -> str | None:
    return LANGUAGE_CODE_MAP.get(target_lang.strip().lower())


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _sanitize_text_for_tts(text: str) -> str:
    cleaned = (
        (text or "")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2026", "...")
    )
    cleaned = " ".join(cleaned.replace("\n", " ").split())
    return cleaned.strip()


def _load_voice_cache() -> dict:
    if not os.path.exists(VOICE_CACHE_PATH):
        return {}
    try:
        with open(VOICE_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_voice_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(VOICE_CACHE_PATH), exist_ok=True)
    with open(VOICE_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def _hash_audio_file(path: str) -> str | None:
    if not path or not os.path.exists(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _write_stream_to_file(audio_gen, output_path: str) -> None:
    with open(output_path, "wb") as f:
        if isinstance(audio_gen, bytes):
            f.write(audio_gen)
        else:
            for chunk in audio_gen:
                f.write(chunk)


def _write_pcm_stream_to_wav(audio_gen, output_path: str, pcm_sample_rate: int) -> None:
    payload = bytearray()
    if isinstance(audio_gen, bytes):
        payload.extend(audio_gen)
    else:
        for chunk in audio_gen:
            payload.extend(chunk)

    samples = np.frombuffer(bytes(payload), dtype=np.int16).astype(np.float32) / 32768.0
    sf.write(output_path, samples, pcm_sample_rate)




def _elevenlabs_voice_settings(
    target_lang: str,
    valence: float,
    arousal: float,
    speed: float | None = None,
    quality_profile: str = "standard",
    delivery_mode: str = "tts",
):
    from elevenlabs import VoiceSettings

    is_english = target_lang.strip().lower() == "english"
    stability = float(np.clip(1.0 - arousal, 0.24, 0.76))
    similarity_boost = float(np.clip(0.52 + (valence * 0.28), 0.5, 0.84))
    style = float(np.clip(arousal * 0.55, 0.05, 0.48))

    if is_english:
        stability = float(np.clip(stability + 0.08, 0.3, 0.82))
        similarity_boost = float(np.clip(similarity_boost + 0.03, 0.54, 0.88))
        style = float(np.clip(style - 0.05, 0.05, 0.4))
    if delivery_mode == "sts":
        stability = float(np.clip(stability + 0.12, 0.42, 0.88))
        similarity_boost = float(np.clip(similarity_boost + 0.08, 0.72, 0.96))
        style = float(np.clip(style - 0.12, 0.02, 0.24))
    if quality_profile == "presentation":
        if delivery_mode == "sts":
            stability = float(np.clip(stability + 0.03, 0.48, 0.9))
            similarity_boost = float(np.clip(similarity_boost + 0.02, 0.76, 0.98))
            style = float(np.clip(style - 0.03, 0.02, 0.2))
        else:
            stability = float(np.clip(stability - (0.08 if is_english else 0.04), 0.22, 0.82))
            similarity_boost = float(np.clip(similarity_boost + 0.03, 0.58, 0.92))
            style = float(np.clip(style + (0.12 if is_english else 0.08), 0.08, 0.58))

    resolved_speed = None if speed is None else float(np.clip(speed, 0.6, 1.15))
    return VoiceSettings(
        stability=stability,
        similarity_boost=similarity_boost,
        style=style,
        use_speaker_boost=True,
        speed=resolved_speed,
    )


def _elevenlabs_voice_settings_payload(
    target_lang: str,
    valence: float,
    arousal: float,
    speed: float | None = None,
    quality_profile: str = "standard",
    delivery_mode: str = "tts",
) -> dict:
    is_english = target_lang.strip().lower() == "english"
    stability = float(np.clip(1.0 - arousal, 0.24, 0.76))
    similarity_boost = float(np.clip(0.52 + (valence * 0.28), 0.5, 0.84))
    style = float(np.clip(arousal * 0.55, 0.05, 0.48))

    if is_english:
        stability = float(np.clip(stability + 0.08, 0.3, 0.82))
        similarity_boost = float(np.clip(similarity_boost + 0.03, 0.54, 0.88))
        style = float(np.clip(style - 0.05, 0.05, 0.4))
    if delivery_mode == "sts":
        stability = float(np.clip(stability + 0.12, 0.42, 0.88))
        similarity_boost = float(np.clip(similarity_boost + 0.08, 0.72, 0.96))
        style = float(np.clip(style - 0.12, 0.02, 0.24))
    if quality_profile == "presentation":
        if delivery_mode == "sts":
            stability = float(np.clip(stability + 0.03, 0.48, 0.9))
            similarity_boost = float(np.clip(similarity_boost + 0.02, 0.76, 0.98))
            style = float(np.clip(style - 0.03, 0.02, 0.2))
        else:
            stability = float(np.clip(stability - (0.08 if is_english else 0.04), 0.22, 0.82))
            similarity_boost = float(np.clip(similarity_boost + 0.03, 0.58, 0.92))
            style = float(np.clip(style + (0.12 if is_english else 0.08), 0.08, 0.58))

    payload = {
        "stability": stability,
        "similarity_boost": similarity_boost,
        "style": style,
        "use_speaker_boost": True,
    }
    if speed is not None:
        payload["speed"] = float(np.clip(speed, 0.7, 1.08))
    return payload


def _resolve_mastering_profile(
    target_lang: str,
    quality_profile: str,
    *,
    is_guide: bool = False,
    delivery_mode: str = "generic",
) -> str:
    if is_guide:
        return "guide" if (quality_profile == "presentation" or target_lang.strip().lower() == "english") else "none"
    if delivery_mode == "cloned_sts":
        return "cloned_sts"
    if delivery_mode == "cloned_tts":
        return "cloned_tts"
    if quality_profile == "presentation" or target_lang.strip().lower() == "english":
        return "presentation"
    return "standard"


def _split_text_into_clauses(text: str) -> list[str]:
    normalized = _sanitize_text_for_tts(text)
    if not normalized:
        return []

    parts = re.split(r"(?:(?<=\.\.\.)|(?<=[.!?]))\s+", normalized)
    clauses: list[str] = []
    for part in parts:
        candidate = part.strip()
        if not candidate:
            continue
        if clauses and len(candidate.split()) <= 3:
            clauses[-1] = f"{clauses[-1]} {candidate}".strip()
        else:
            clauses.append(candidate)

    if len(clauses) > 3:
        head = clauses[:2]
        tail = " ".join(clauses[2:]).strip()
        clauses = [*head, tail]
    return clauses


def _extract_pause_plan(source_audio_path: str | None, sample_rate: int, pause_count: int) -> list[float]:
    if pause_count <= 0:
        return []

    defaults = [0.14] * pause_count
    if not source_audio_path or not os.path.exists(source_audio_path):
        return defaults

    try:
        y, _ = librosa.load(source_audio_path, sr=sample_rate, mono=True)
        if not y.size:
            return defaults

        intervals = librosa.effects.split(y, top_db=34, frame_length=1024, hop_length=256)
        gaps: list[float] = []
        for previous, following in zip(intervals[:-1], intervals[1:]):
            gap_s = float((following[0] - previous[1]) / sample_rate)
            if gap_s >= 0.05:
                gaps.append(float(np.clip(gap_s, 0.05, 0.45)))

        if not gaps:
            return defaults

        if len(gaps) >= pause_count:
            return gaps[:pause_count]

        return gaps + defaults[len(gaps):pause_count]
    except Exception:
        return defaults


def _soften_segment_edges(y: np.ndarray, sample_rate: int) -> np.ndarray:
    if not y.size:
        return y

    softened = y.astype(np.float32, copy=True)
    fade_samples = min(int(sample_rate * 0.012), max(len(softened) // 8, 1))
    if fade_samples > 1:
        fade_in = np.linspace(0.0, 1.0, fade_samples)
        fade_out = np.linspace(1.0, 0.0, fade_samples)
        softened[:fade_samples] *= fade_in
        softened[-fade_samples:] *= fade_out
    return softened


def _assemble_clause_audio(clause_paths: list[str], pause_plan: list[float], output_path: str, sample_rate: int) -> None:
    chunks: list[np.ndarray] = []
    for index, clause_path in enumerate(clause_paths):
        y_clause, _ = librosa.load(clause_path, sr=sample_rate, mono=True)
        if not y_clause.size:
            continue
        chunks.append(_soften_segment_edges(y_clause, sample_rate))
        if index < len(pause_plan):
            gap_samples = max(int(round(sample_rate * pause_plan[index])), 1)
            chunks.append(np.zeros(gap_samples, dtype=np.float32))

    combined = np.concatenate(chunks) if chunks else np.zeros(max(int(sample_rate * 0.2), 1), dtype=np.float32)
    peak = float(np.max(np.abs(combined))) if combined.size else 0.0
    if peak > 0.98:
        combined = combined / peak * 0.94
    sf.write(output_path, combined.astype(np.float32), sample_rate)


def _render_openai_tts(
    *,
    client,
    text: str,
    output_path: str,
    instructions: str,
) -> None:
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice=os.getenv("OPENAI_GUIDE_VOICE", "alloy").strip() or "alloy",
        input=text,
        instructions=instructions,
        response_format="wav",
    ) as response:
        response.stream_to_file(output_path)


def _sts_model_candidates(target_lang: str) -> list[str]:
    language = target_lang.strip().lower()
    configured_default = os.getenv("ELEVENLABS_STS_MODEL_ID", DEFAULT_ELEVENLABS_STS_MODEL_ID).strip() or DEFAULT_ELEVENLABS_STS_MODEL_ID
    candidates: list[str] = []

    if language == "english":
        english_model = os.getenv("ELEVENLABS_ENGLISH_STS_MODEL_ID", DEFAULT_ELEVENLABS_ENGLISH_STS_MODEL_ID).strip() or DEFAULT_ELEVENLABS_ENGLISH_STS_MODEL_ID
        candidates.append(english_model)

    candidates.append(configured_default)

    deduped = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _synthesize_with_openai_tts(
    *,
    text: str,
    output_path: str,
    sample_rate: int,
    target_lang: str,
    valence: float,
    arousal: float,
    feature_stats: dict | None = None,
    target_duration_s: float | None = None,
    quality_profile: str = "standard",
    trim_edges: bool = True,
    source_audio_path: str | None = None,
) -> bool:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return False

    from openai import OpenAI

    client = OpenAI(api_key=openai_key)
    clauses = _split_text_into_clauses(text) if source_audio_path else []
    if source_audio_path and len(clauses) > 1:
        with tempfile.TemporaryDirectory(prefix="guide_tts_") as temp_dir:
            full_line_path = os.path.join(temp_dir, "guide_full.wav")
            _render_openai_tts(
                client=client,
                text=text,
                output_path=full_line_path,
                instructions=build_openai_instructions(
                    target_lang,
                    valence,
                    arousal,
                    feature_stats=feature_stats,
                    target_duration_s=target_duration_s,
                    quality_profile=quality_profile,
                ),
            )

            chosen_path = full_line_path
            pause_plan = _extract_pause_plan(source_audio_path, sample_rate, len(clauses) - 1)
            clause_target_durations: list[float] | None = None
            if target_duration_s:
                speech_budget = max(float(target_duration_s) - sum(pause_plan), 0.6 * len(clauses))
                weights = [max(len(clause.split()), 1) for clause in clauses]
                weight_total = max(sum(weights), 1)
                clause_target_durations = [
                    max(0.42, speech_budget * (weight / weight_total))
                    for weight in weights
                ]

            clause_paths: list[str] = []
            for clause_index, clause_text in enumerate(clauses):
                clause_path = os.path.join(temp_dir, f"clause_{clause_index}.wav")
                _render_openai_tts(
                    client=client,
                    text=clause_text,
                    output_path=clause_path,
                    instructions=build_clause_instructions(
                        target_lang,
                        valence,
                        arousal,
                        feature_stats=feature_stats,
                        target_duration_s=clause_target_durations[clause_index] if clause_target_durations else target_duration_s,
                        quality_profile=quality_profile,
                        clause_index=clause_index,
                        clause_count=len(clauses),
                        clause_text=clause_text,
                    ),
                )
                clause_paths.append(clause_path)

            clause_mix_path = os.path.join(temp_dir, "guide_clause_mix.wav")
            _assemble_clause_audio(clause_paths, pause_plan, clause_mix_path, sample_rate)

            if target_duration_s:
                full_duration = librosa.get_duration(path=full_line_path)
                clause_duration = librosa.get_duration(path=clause_mix_path)
                full_error = abs(full_duration - target_duration_s) / max(target_duration_s, 1e-6)
                clause_error = abs(clause_duration - target_duration_s) / max(target_duration_s, 1e-6)
                if clause_duration <= target_duration_s * 1.16 and clause_error <= full_error + 0.03:
                    chosen_path = clause_mix_path
            else:
                chosen_path = clause_mix_path

            y_chosen, _ = librosa.load(chosen_path, sr=sample_rate, mono=True)
            sf.write(output_path, y_chosen.astype(np.float32), sample_rate)
    else:
        _render_openai_tts(
            client=client,
            text=text,
            output_path=output_path,
            instructions=build_openai_instructions(
                target_lang,
                valence,
                arousal,
                feature_stats=feature_stats,
                target_duration_s=target_duration_s,
                quality_profile=quality_profile,
            ),
        )

    finalize_audio(
        output_path,
        sample_rate,
        trim_edges=trim_edges,
        smart_trim=not trim_edges,
        mastering_profile=_resolve_mastering_profile(target_lang, quality_profile, is_guide=True),
        target_lang=target_lang,
    )
    return True


def resolve_elevenlabs_voice_profile(
    sample_audio_path: str | None = None,
    friendly_name: str | None = None,
) -> dict | None:
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    if not elevenlabs_key:
        return None

    configured_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if configured_voice_id:
        return {
            "provider": "elevenlabs",
            "voice_id": configured_voice_id,
            "model_id": os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip() or "eleven_multilingual_v2",
            "mode": "configured_voice_id",
        }

    auto_clone_enabled = _env_flag("ELEVENLABS_AUTO_CLONE", default=False)
    if auto_clone_enabled and sample_audio_path and os.path.exists(sample_audio_path):
        try:
            from elevenlabs import ElevenLabs

            client = ElevenLabs(api_key=elevenlabs_key)
            sample_hash = _hash_audio_file(sample_audio_path)
            cache = _load_voice_cache()
            cache_entry = cache.get(sample_hash or "")
            if cache_entry and cache_entry.get("voice_id"):
                try:
                    client.voices.get(cache_entry["voice_id"])
                    return {
                        "provider": "elevenlabs",
                        "voice_id": cache_entry["voice_id"],
                        "model_id": os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip() or "eleven_multilingual_v2",
                        "mode": "cached_auto_clone",
                    }
                except Exception:
                    pass

            clone_name = f"TrueDub {friendly_name or 'Auto Clone'}"
            clone_name = clone_name[:64]
            created = client.voices.ivc.create(
                name=clone_name,
                files=[sample_audio_path],
                remove_background_noise=True,
                description="Auto-created voice profile for the TrueDub beta pipeline.",
            )
            voice_id = getattr(created, "voice_id", None)
            if voice_id and sample_hash:
                cache[sample_hash] = {
                    "voice_id": voice_id,
                    "name": getattr(created, "name", clone_name),
                }
                _save_voice_cache(cache)
            if voice_id:
                return {
                    "provider": "elevenlabs",
                    "voice_id": voice_id,
                    "model_id": os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip() or "eleven_multilingual_v2",
                    "mode": "auto_clone",
                }
        except Exception as exc:
            print(f"         ElevenLabs auto-clone unavailable: {exc}")

    return {
        "provider": "elevenlabs",
        "voice_id": DEFAULT_ELEVENLABS_VOICE_ID,
        "model_id": os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip() or "eleven_multilingual_v2",
        "mode": "premade_fallback",
    }


def _synthesize_with_elevenlabs_tts(
    *,
    text: str,
    output_path: str,
    sample_rate: int,
    target_lang: str,
    valence: float,
    arousal: float,
    voice_profile: dict,
    previous_text: str | None = None,
    next_text: str | None = None,
    segment_index: int | None = None,
    tts_speed: float | None = None,
    quality_profile: str = "standard",
) -> bool:
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    if not elevenlabs_key or not voice_profile or not voice_profile.get("voice_id"):
        return False

    from elevenlabs import ElevenLabs

    client = ElevenLabs(api_key=elevenlabs_key)
    seed = None
    try:
        seed = int(hashlib.sha256(f"{segment_index or 0}:{text}".encode("utf-8")).hexdigest()[:8], 16)
    except Exception:
        seed = None

    audio_gen = client.text_to_speech.convert(
        text=text,
        voice_id=voice_profile["voice_id"],
        model_id=voice_profile.get("model_id") or "eleven_multilingual_v2",
        language_code=_resolve_language_code(target_lang),
        output_format="wav_24000",
        voice_settings=_elevenlabs_voice_settings(
            target_lang,
            valence,
            arousal,
            speed=tts_speed,
            quality_profile=quality_profile,
            delivery_mode="tts",
        ),
        seed=seed,
        previous_text=previous_text or None,
        next_text=next_text or None,
        apply_text_normalization="auto",
    )

    _write_stream_to_file(audio_gen, output_path)
    finalize_audio(
        output_path,
        sample_rate,
        trim_edges=False,
        smart_trim=True,
        mastering_profile=_resolve_mastering_profile(
            target_lang,
            quality_profile,
            delivery_mode="cloned_tts" if voice_profile.get("mode") in {"configured_voice_id", "cached_auto_clone", "auto_clone"} else "generic",
        ),
        target_lang=target_lang,
    )
    return True


def _fit_audio_to_target_duration(audio_path: str, target_duration_s: float, sample_rate: int) -> tuple[str, dict]:
    from .align import stretch_to_duration

    timed_output_path = audio_path.replace(".wav", "_timed.wav")
    timing_info = stretch_to_duration(
        audio_path,
        target_duration_s=target_duration_s,
        output_path=timed_output_path,
        sample_rate=sample_rate,
    )
    return timed_output_path, timing_info


def _convert_with_elevenlabs_speech_to_speech(
    *,
    guide_audio_path: str,
    output_path: str,
    sample_rate: int,
    voice_profile: dict,
    valence: float,
    arousal: float,
    target_lang: str,
    quality_profile: str = "standard",
) -> bool:
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    if not elevenlabs_key or not voice_profile or not voice_profile.get("voice_id"):
        return False

    output_format = os.getenv("ELEVENLABS_STS_OUTPUT_FORMAT", DEFAULT_ELEVENLABS_STS_OUTPUT_FORMAT).strip() or DEFAULT_ELEVENLABS_STS_OUTPUT_FORMAT
    voice_id = voice_profile["voice_id"]
    request_url = f"https://api.elevenlabs.io/v1/speech-to-speech/{voice_id}"

    last_error = None
    response = None
    for model_id in _sts_model_candidates(target_lang):
        with open(guide_audio_path, "rb") as audio_file:
            candidate_response = requests.post(
                request_url,
                params={"output_format": output_format},
                headers={"xi-api-key": elevenlabs_key},
                files={"audio": (os.path.basename(guide_audio_path), audio_file, "audio/wav")},
                data={
                    "model_id": model_id,
                    "remove_background_noise": "false",
                    "file_format": "other",
                    "voice_settings": json.dumps(
                        _elevenlabs_voice_settings_payload(
                            target_lang,
                            valence,
                            arousal,
                            quality_profile=quality_profile,
                            delivery_mode="sts",
                        )
                    ),
                },
                timeout=120,
            )
        if candidate_response.ok:
            response = candidate_response
            break
        last_error = f"{model_id}: {candidate_response.status_code} {candidate_response.text[:180]}"

    if response is None:
        raise RuntimeError(f"ElevenLabs STS failed for all model candidates. Last error: {last_error}")

    if output_format.startswith("wav_"):
        with open(output_path, "wb") as f:
            f.write(response.content)
    elif output_format.startswith("mp3_"):
        temp_mp3_path = output_path.replace(".wav", "_sts.mp3")
        with open(temp_mp3_path, "wb") as f:
            f.write(response.content)
        _convert_to_wav(temp_mp3_path, output_path, sample_rate)
    else:
        raise RuntimeError(f"Unsupported ElevenLabs STS output format: {output_format}")

    finalize_audio(
        output_path,
        sample_rate,
        trim_edges=False,
        smart_trim=True,
        mastering_profile=_resolve_mastering_profile(target_lang, quality_profile, delivery_mode="cloned_sts"),
        target_lang=target_lang,
    )
    return True


def synthesize_speech(
    text: str,
    valence: float,
    arousal: float,
    output_dir: str,
    output_filename: str = "dubbed_audio.wav",
    sample_rate: int = 16000,
    target_lang: str = "Spanish",
    feature_stats: dict | None = None,
    target_duration_s: float | None = None,
    quality_profile: str = "standard",
    voice_profile: dict | None = None,
    previous_text: str | None = None,
    next_text: str | None = None,
    segment_index: int | None = None,
    tts_speed: float | None = None,
    source_audio_path: str | None = None,
) -> tuple[str, dict]:
    """
    Generate dubbed audio via TTS.
    Primary: ElevenLabs (with valence-arousal mapped parameters).
    Fallback: gTTS (Google Text-to-Speech).
    """
    print(f"[SYNTHESIZE] Synthesizing dubbed speech for {output_filename}...")
    output_path = os.path.join(output_dir, output_filename)
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    prefer_elevenlabs = bool(voice_profile) or _env_flag("ELEVENLABS_PREFER", default=False)
    use_sts = (
        _env_flag("ELEVENLABS_USE_STS", default=True)
        and bool(voice_profile)
        and voice_profile.get("mode") in {"configured_voice_id", "cached_auto_clone", "auto_clone"}
    )

    if not text or not text.strip():
        print("         Skipping TTS -- no text available.")
        silence = np.zeros(sample_rate * 2, dtype=np.float32)
        sf.write(output_path, silence, sample_rate)
        return output_path, {"method": "silence", "voice_profile_mode": voice_profile.get("mode") if voice_profile else None}

    text = _sanitize_text_for_tts(text)

    if use_sts and elevenlabs_key and voice_profile:
        try:
            print(f"         Trying guide TTS + ElevenLabs speech-to-speech ({voice_profile.get('mode', 'configured')})...")
            guide_path = output_path.replace(".wav", "_guide.wav")
            guide_method = None
            guide_ready_path = guide_path
            guide_timing_info = None

            if openai_key and _synthesize_with_openai_tts(
                text=text,
                output_path=guide_path,
                sample_rate=sample_rate,
                target_lang=target_lang,
                valence=valence,
                arousal=arousal,
                feature_stats=feature_stats,
                target_duration_s=target_duration_s,
                quality_profile=quality_profile,
                trim_edges=True,
                source_audio_path=source_audio_path,
            ):
                guide_method = "openai_guide_tts"
            else:
                guide_voice_profile = {
                    "provider": "elevenlabs",
                    "voice_id": os.getenv("ELEVENLABS_GUIDE_VOICE_ID", DEFAULT_ELEVENLABS_VOICE_ID).strip() or DEFAULT_ELEVENLABS_VOICE_ID,
                    "model_id": os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip() or "eleven_multilingual_v2",
                    "mode": "guide_voice",
                }
                if _synthesize_with_elevenlabs_tts(
                    text=text,
                    output_path=guide_path,
                    sample_rate=sample_rate,
                    target_lang=target_lang,
                    valence=valence,
                    arousal=arousal,
                    voice_profile=guide_voice_profile,
                    previous_text=previous_text,
                    next_text=next_text,
                    segment_index=segment_index,
                    tts_speed=tts_speed,
                    quality_profile="standard",
                ):
                    guide_method = "elevenlabs_guide_tts"

            if guide_method and target_duration_s:
                guide_ready_path, guide_timing_info = _fit_audio_to_target_duration(
                    guide_path,
                    target_duration_s=target_duration_s,
                    sample_rate=sample_rate,
                )

            if guide_method and _convert_with_elevenlabs_speech_to_speech(
                guide_audio_path=guide_ready_path,
                output_path=output_path,
                sample_rate=sample_rate,
                voice_profile=voice_profile,
                valence=valence,
                arousal=arousal,
                target_lang=target_lang,
                quality_profile=quality_profile,
            ):
                print(f"         ElevenLabs speech-to-speech success -> {output_path}")
                return output_path, {
                    "method": "guide_tts_plus_speech_to_speech",
                    "guide_method": guide_method,
                    "guide_audio_path": guide_ready_path,
                    "guide_timing": guide_timing_info,
                    "voice_profile_mode": voice_profile.get("mode"),
                    "voice_id": voice_profile.get("voice_id"),
                    "tts_speed": tts_speed,
                }
        except Exception as e:
            print(f"         ElevenLabs speech-to-speech failed: {e}. Falling back to direct TTS...")

    if prefer_elevenlabs and elevenlabs_key and voice_profile:
        try:
            print(f"         Trying ElevenLabs TTS ({voice_profile.get('mode', 'configured')})...")
            if _synthesize_with_elevenlabs_tts(
                text=text,
                output_path=output_path,
                sample_rate=sample_rate,
                target_lang=target_lang,
                valence=valence,
                arousal=arousal,
                voice_profile=voice_profile,
                previous_text=previous_text,
                next_text=next_text,
                segment_index=segment_index,
                tts_speed=tts_speed,
                quality_profile=quality_profile,
            ):
                print(f"         ElevenLabs TTS success -> {output_path}")
                return output_path, {
                    "method": "elevenlabs_tts",
                    "voice_profile_mode": voice_profile.get("mode"),
                    "voice_id": voice_profile.get("voice_id"),
                    "tts_speed": tts_speed,
                }
        except Exception as e:
            print(f"         ElevenLabs failed: {e}. Falling back to OpenAI/gTTS...")

    if openai_key:
        try:
            print("         Trying OpenAI TTS...")
            if _synthesize_with_openai_tts(
                text=text,
                output_path=output_path,
                sample_rate=sample_rate,
                target_lang=target_lang,
                valence=valence,
                arousal=arousal,
                feature_stats=feature_stats,
                target_duration_s=target_duration_s,
                quality_profile=quality_profile,
                trim_edges=False,
                source_audio_path=source_audio_path,
            ):
                print(f"         OpenAI TTS success -> {output_path}")
                return output_path, {"method": "openai_tts"}
        except Exception as e:
            print(f"         OpenAI TTS failed: {e}. Falling back to ElevenLabs/gTTS...")

    # ElevenLabs mapping
    if elevenlabs_key:
        try:
            fallback_profile = voice_profile or resolve_elevenlabs_voice_profile()
            print(f"         Trying ElevenLabs TTS ({fallback_profile.get('mode', 'fallback')})...")
            if _synthesize_with_elevenlabs_tts(
                text=text,
                output_path=output_path,
                sample_rate=sample_rate,
                target_lang=target_lang,
                valence=valence,
                arousal=arousal,
                voice_profile=fallback_profile,
                previous_text=previous_text,
                next_text=next_text,
                segment_index=segment_index,
                tts_speed=tts_speed,
                quality_profile=quality_profile,
            ):
                print(f"         ElevenLabs TTS success -> {output_path}")
                return output_path, {
                    "method": "elevenlabs_tts",
                    "voice_profile_mode": fallback_profile.get("mode"),
                    "voice_id": fallback_profile.get("voice_id"),
                    "tts_speed": tts_speed,
                }
        except Exception as e:
            print(f"         ElevenLabs failed: {e}. Falling back to gTTS...")

    # Fallback: gTTS
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=_resolve_tts_language(target_lang))
        mp3_path = output_path.replace(".wav", "_gtts.mp3")
        tts.save(mp3_path)
        _convert_to_wav(mp3_path, output_path, sample_rate)
        finalize_audio(
            output_path,
            sample_rate,
            trim_edges=False,
            smart_trim=True,
            mastering_profile=_resolve_mastering_profile(target_lang, quality_profile),
            target_lang=target_lang,
        )
        print(f"         gTTS success -> {output_path}")
        return output_path, {"method": "gtts"}
    except Exception as e:
        print(f"         gTTS failed: {e}. Generating silence.")
        silence = np.zeros(sample_rate * 2, dtype=np.float32)
        sf.write(output_path, silence, sample_rate)
        return output_path, {"method": "silence_fallback"}

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
