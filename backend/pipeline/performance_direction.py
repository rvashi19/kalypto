from __future__ import annotations


def _safe_float(value: float | None, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _language_key(target_lang: str) -> str:
    return (target_lang or "").strip().lower()


def estimate_word_budget(target_lang: str, source_duration_s: float) -> int:
    language = _language_key(target_lang)
    words_per_second = 2.2
    if language in {"spanish", "italian", "portuguese"}:
        words_per_second = 2.5
    elif language in {"german", "french"}:
        words_per_second = 2.3
    elif language in {"hindi", "gujarati"}:
        words_per_second = 2.4
    return max(4, int(round(max(source_duration_s, 0.8) * words_per_second)))


def describe_emotional_tone(valence: float | None, arousal: float | None) -> str:
    valence = _safe_float(valence)
    arousal = _safe_float(arousal)

    if arousal >= 0.8 and valence <= 0.42:
        return "fierce, defiant, and high-stakes"
    if arousal >= 0.76 and valence >= 0.58:
        return "urgent, triumphant, and emotionally charged"
    if arousal >= 0.68:
        return "intense, dramatic, and emotionally exposed"
    if arousal <= 0.35 and valence <= 0.42:
        return "restrained, heavy, and emotionally burdened"
    if arousal <= 0.35:
        return "steady, intimate, and controlled"
    if valence >= 0.62:
        return "warm, confident, and uplifting"
    return "grounded, dramatic, and sincere"


def describe_pacing(feature_stats: dict | None = None) -> str:
    feature_stats = feature_stats or {}
    syllabic_rate = _safe_float(feature_stats.get("syllabic_rate"))
    onset_density = _safe_float(feature_stats.get("onset_density"))
    pace_driver = max(syllabic_rate, onset_density)

    if pace_driver >= 4.8:
        return "Use short, punchy clauses with minimal slack between stressed words."
    if pace_driver <= 2.2:
        return "Keep the cadence measured, deliberate, and actor-friendly."
    return "Keep the cadence compact, speakable, and naturally cinematic."


def describe_pitch_shape(feature_stats: dict | None = None) -> str:
    feature_stats = feature_stats or {}
    pitch_std = _safe_float(feature_stats.get("pitch_std_hz"))
    if pitch_std >= 45.0:
        return "Let emphasis rise and fall with noticeable emotional pitch movement."
    if pitch_std <= 18.0:
        return "Keep pitch movement controlled, focused, and restrained."
    return "Use natural pitch movement with clear emphasis on key words."


def describe_delivery_arc(valence: float | None, arousal: float | None) -> str:
    valence = _safe_float(valence)
    arousal = _safe_float(arousal)

    if arousal >= 0.75 and valence <= 0.45:
        return "Start already under pressure and let the feeling sharpen into defiance."
    if arousal >= 0.72:
        return "Start energized and let the line build with visible urgency."
    if valence <= 0.42:
        return "Start intimate and reflective, then let the ache show more clearly by the end."
    if arousal <= 0.35:
        return "Keep it inward, controlled, and deeply felt rather than performed outwardly."
    return "Let the thought unfold naturally, with a clear emotional turn before the ending lands."


def build_clause_instructions(
    target_lang: str,
    valence: float,
    arousal: float,
    *,
    feature_stats: dict | None = None,
    target_duration_s: float | None = None,
    quality_profile: str = "standard",
    clause_index: int = 0,
    clause_count: int = 1,
    clause_text: str = "",
) -> str:
    base = build_openai_instructions(
        target_lang,
        valence,
        arousal,
        feature_stats=feature_stats,
        target_duration_s=target_duration_s,
        quality_profile=quality_profile,
    )

    clause_text = (clause_text or "").strip()
    punctuation_hint = ""
    if clause_text.endswith("..."):
        punctuation_hint = "Honor the ellipsis with a brief thought-filled suspension, not dead air. "
    elif clause_text.endswith("?"):
        punctuation_hint = "Let it feel searching and alive, not recited. "
    elif clause_text.endswith("!"):
        punctuation_hint = "Land it with pressure and conviction, but stay screen-natural. "

    if clause_count <= 1:
        beat = "Deliver it like a thought arriving on the actor's face in real time, not like a narrator reading copy."
    elif clause_index == 0:
        beat = (
            f"Opening beat: {describe_delivery_arc(valence, arousal)} "
            "Enter conversationally, as if the actor is discovering the line in the moment."
        )
    elif clause_index == clause_count - 1:
        if _safe_float(valence) <= 0.45:
            beat = "Closing beat: let the final words land with weight and emotional residue, without flattening the phrasing."
        elif _safe_float(arousal) >= 0.68:
            beat = "Closing beat: let the ending land with bite and conviction, without sounding shouted."
        else:
            beat = "Closing beat: land the final phrase with clear emotional emphasis and a believable release."
    else:
        beat = "Middle beat: treat this as the emotional turn in the thought and let the internal pressure rise slightly."

    if target_lang.strip().lower() == "english":
        beat += " Keep it grounded in natural American film-dialogue rhythm, not an announcer cadence."

    return f"{base} {punctuation_hint}{beat}".strip()


def build_translation_prompt(
    target_lang: str,
    source_duration_s: float | None = None,
    tighten: bool = False,
    expand: bool = False,
    valence: float | None = None,
    arousal: float | None = None,
    feature_stats: dict | None = None,
) -> str:
    language = _language_key(target_lang)
    constraints = [
        f"Translate the dialogue into natural {target_lang}.",
        "Preserve the speaker's intent, dramatic stakes, and emotional temperature.",
        f"The dubbed performance should land as {describe_emotional_tone(valence, arousal)}.",
        describe_pacing(feature_stats),
        "Keep the line speakable for film dubbing, not literary translation.",
        "Keep the beat structure and pause pattern close to the source.",
        "Avoid filler words, added exposition, or long explanatory phrasing.",
        "Output only the translated dialogue.",
    ]

    if language == "english":
        constraints[1:1] = [
            "Write it as natural, idiomatic American English for a contemporary film dub.",
            "Make it feel like the same on-screen actor is now speaking fluent English, not a separate dubbing narrator.",
            "Prefer contractions, compact phrasing, and clean clause endings that an American actor would say aloud.",
            "Avoid literal translation, bookish wording, or awkward carryover that makes the dub sound translated.",
        ]

    if source_duration_s:
        word_budget = estimate_word_budget(target_lang, source_duration_s)
        constraints.insert(
            3,
            (
                f"The line should feel natural when spoken in about {source_duration_s:.1f} seconds. "
                f"If the target language uses spaces, aim for about {word_budget} words or fewer."
            ),
        )

    if tighten:
        constraints.insert(
            4,
            "The previous dub ran too long. Compress the line by roughly 15-25% while preserving meaning, emotional force, and clean lip-sync timing.",
        )
    elif expand:
        constraints.insert(
            4,
            "The previous dub landed too short. Expand the line by roughly 10-20% with natural, emotionally equivalent phrasing, not filler.",
        )

    return " ".join(item.strip() for item in constraints if item)


def build_openai_instructions(
    target_lang: str,
    valence: float,
    arousal: float,
    feature_stats: dict | None = None,
    target_duration_s: float | None = None,
    quality_profile: str = "standard",
) -> str:
    feature_stats = feature_stats or {}
    language = _language_key(target_lang)
    emotion = describe_emotional_tone(valence, arousal)
    pacing = describe_pacing(feature_stats)
    pitch_shape = describe_pitch_shape(feature_stats)

    register = ""
    pitch_mean = _safe_float(feature_stats.get("pitch_mean_hz"))
    if pitch_mean and pitch_mean < 135.0:
        register = "Lean into a slightly lower, grounded register. "
    elif pitch_mean and pitch_mean > 185.0:
        register = "Use a slightly lighter, brighter register without sounding cartoonish. "

    timing = ""
    if target_duration_s:
        timing = (
            f"Keep the spoken line tight enough to land naturally in about {target_duration_s:.1f} seconds. "
            "Do not add extra pauses or trailing words. "
        )

    accent = ""
    if language == "english":
        accent = (
            "Use clear, modern General American English pronunciation. "
            "Favor crisp consonants, clean vowel shapes, and natural American dialogue rhythm. "
            "Avoid singsong translated cadence or non-American accent drift. "
            "Make it feel like the same actor on screen is speaking fluent English in real time. "
        )

    polish = ""
    if quality_profile == "presentation":
        polish = (
            "Sound like a polished lead actor in a film dub. "
            "Keep the performance emotionally legible, intimate, and screen-natural. "
            "Underplay rather than over-announcing. Avoid exaggerated diction, trailer-voice emphasis, or artificial punchiness. "
        )

    return (
        f"Speak in {target_lang}. {accent}"
        f"The performance should feel {emotion}. "
        f"{pacing} {pitch_shape} "
        f"{register}{timing}{polish}"
        "Keep articulation crisp, dialogue-forward, and emotionally transparent."
    )
