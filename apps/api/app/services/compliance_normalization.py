from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

SUPPORTED_COUNTRIES = (
    "Canada",
    "United Arab Emirates",
    "UK",
)

COUNTRY_ALIASES = {
    "canada": "Canada",
    "ca": "Canada",
    "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    "emirates": "United Arab Emirates",
    "uk": "UK",
    "united kingdom": "UK",
    "great britain": "UK",
}

SUPPORTED_CATEGORIES = (
    "beverages",
    "dry fruits",
    "spices",
    "textiles",
)

CATEGORY_ALIASES = {
    "spice": "spices",
    "spices": "spices",
    "dry fruit": "dry fruits",
    "dry fruits": "dry fruits",
    "dried fruit": "dry fruits",
    "dried fruits": "dry fruits",
    "beverage": "beverages",
    "beverages": "beverages",
    "drink": "beverages",
    "drinks": "beverages",
    "textile": "textiles",
    "textiles": "textiles",
    "garment": "textiles",
    "garments": "textiles",
}

REQUIREMENT_TYPE_ALIASES = {
    "document": "import_document",
    "documents": "import_document",
    "import document": "import_document",
    "import_document": "import_document",
    "certificate": "certificate",
    "certificates": "certificate",
    "label": "labeling",
    "labels": "labeling",
    "labeling": "labeling",
    "labelling": "labeling",
    "restriction": "restriction",
    "restricted": "restriction",
    "prohibited": "restriction",
    "inspection": "inspection",
    "testing": "inspection",
    "phytosanitary": "inspection",
    "fumigation": "inspection",
    "buyer question": "buyer_question",
    "buyer_question": "buyer_question",
    "question": "buyer_question",
    "other": "other",
}

STOP_WORDS = {
    "and",
    "for",
    "from",
    "into",
    "the",
    "with",
    "export",
    "indian",
    "india",
    "packed",
    "packaged",
}


def normalize_spaces(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_country(value: str) -> str:
    key = normalize_spaces(value).lower()
    return COUNTRY_ALIASES.get(key, normalize_spaces(value))


def normalize_category(value: str) -> str:
    key = normalize_spaces(value).lower()
    return CATEGORY_ALIASES.get(key, normalize_spaces(value).lower())


def normalize_requirement_type(value: str) -> str:
    key = normalize_spaces(value).lower()
    return REQUIREMENT_TYPE_ALIASES.get(key, key.replace(" ", "_"))


def normalize_hsn(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\D", "", value)
    if not cleaned:
        return None
    return cleaned[:8]


def tokenize_keywords(value: str | Iterable[str]) -> list[str]:
    if isinstance(value, str):
        raw_tokens = re.findall(r"[a-z0-9]{2,}", value.lower())
    else:
        raw_tokens = []
        for item in value:
            raw_tokens.extend(re.findall(r"[a-z0-9]{2,}", item.lower()))
    return sorted({token for token in raw_tokens if token not in STOP_WORDS})


def requirement_fingerprint(
    *,
    tenant_id: str,
    country: str,
    category: str,
    hsn_code: str | None,
    requirement_type: str,
    requirement_text: str,
    source_url: str,
) -> str:
    raw = "|".join(
        [
            tenant_id,
            normalize_country(country).lower(),
            normalize_category(category).lower(),
            hsn_code or "",
            normalize_requirement_type(requirement_type),
            normalize_spaces(requirement_text).lower(),
            source_url.strip().lower(),
        ],
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def source_snapshot_fingerprint(*, source_url: str, title: str, markdown: str) -> str:
    raw = "|".join(
        [
            source_url.strip().lower(),
            normalize_spaces(title).lower(),
            normalize_spaces(markdown).lower(),
        ],
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
