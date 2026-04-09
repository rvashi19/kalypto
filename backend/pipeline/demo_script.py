CURATED_DEMO_SEGMENTS = [
    {
        "hindi": (
            "\u092e\u0941\u0902\u092c\u0908 \u0915\u0940 \u0930\u093e\u0924 "
            "\u0915\u092d\u0940 \u0938\u0940\u0927\u0940 \u0928\u0939\u0940\u0902 \u0939\u094b\u0924\u0940\u0964"
        ),
        "romanized": "Mumbai ki raat kabhi seedhi nahin hoti.",
        "english": "Nights in Mumbai are never simple.",
        "scene_title": "Mumbai Rooftops",
    },
    {
        "hindi": (
            "\u090f\u0915 \u092b\u0948\u0938\u0932\u093e, \u090f\u0915 \u0917\u094b\u0932\u0940, "
            "\u0914\u0930 \u092a\u0942\u0930\u093e \u0916\u0947\u0932 \u092c\u0926\u0932 \u091c\u093e\u0924\u093e \u0939\u0948\u0964"
        ),
        "romanized": "Ek faisla, ek goli, aur poora khel badal jaata hai.",
        "english": "One decision, one bullet, and the whole game changes.",
        "scene_title": "Neon Alley",
    },
    {
        "hindi": (
            "\u0905\u0917\u0930 \u0906\u091c \u0939\u092e \u092a\u0940\u091b\u0947 \u0939\u091f\u0947, "
            "\u0924\u094b \u0915\u0932 \u0915\u094b\u0908 \u0939\u092e\u093e\u0930\u093e \u0928\u093e\u092e "
            "\u0928\u0939\u0940\u0902 \u0932\u0947\u0917\u093e\u0964"
        ),
        "romanized": "Agar aaj hum peeche hate, to kal koi hamara naam nahin lega.",
        "english": "If we step back tonight, tomorrow no one will even speak our name.",
        "scene_title": "The Chase",
    },
    {
        "hindi": (
            "\u0921\u0930 \u092e\u0924 \u0926\u093f\u0916\u093e\u0928\u093e... \u0906\u091c \u091c\u0940\u0924\u0928\u093e "
            "\u0939\u0940 \u0938\u093e\u0901\u0938 \u0932\u0947\u0928\u0947 \u091c\u0948\u0938\u093e "
            "\u091c\u0930\u0942\u0930\u0940 \u0939\u0948\u0964"
        ),
        "romanized": "Dar mat dikhana... aaj jeetna hi saans lene jaisa zaroori hai.",
        "english": "Show no fear. Tonight, winning is as necessary as breathing.",
        "scene_title": "Final Showdown",
    },
]

SHOWCASE_DEMO_SEGMENTS = [
    {
        "english": "Memory's strange... you bury it for years, and it still won't let go.",
    },
    {
        "english": "It never does. Reach for one small thing... and your mind goes blank.",
    },
]


def get_demo_full_transcript() -> str:
    return " ".join(segment["hindi"] for segment in CURATED_DEMO_SEGMENTS)


def get_demo_full_translation(target_lang: str) -> str | None:
    if target_lang.strip().lower() == "english":
        return " ".join(segment["english"] for segment in CURATED_DEMO_SEGMENTS)
    if target_lang.strip().lower() == "hindi":
        return get_demo_full_transcript()
    return None


def get_showcase_demo_translation(index: int, target_lang: str) -> str | None:
    if target_lang.strip().lower() != "english":
        return None
    if index < 0 or index >= len(SHOWCASE_DEMO_SEGMENTS):
        return None
    return SHOWCASE_DEMO_SEGMENTS[index]["english"]
