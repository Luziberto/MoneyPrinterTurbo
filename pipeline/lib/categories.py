"""Editorial categories and music defaults — technical identifiers in English."""

from __future__ import annotations

VALID_CATEGORIES = frozenset(
    {
        "culture",
        "society",
        "transport",
        "education",
        "work",
        "food",
        "tourism",
        "technology",
        "history",
        "weird_facts",
    }
)

CATEGORY_MUSIC_DEFAULTS: dict[str, list[str]] = {
    "culture": ["lofi", "city_pop"],
    "society": ["lofi", "documentary"],
    "transport": ["city_pop", "documentary"],
    "education": ["lofi", "documentary"],
    "work": ["lofi", "documentary"],
    "food": ["lofi", "city_pop"],
    "tourism": ["lofi", "city_pop"],
    "technology": ["documentary", "city_pop"],
    "history": ["traditional", "documentary"],
    "weird_facts": ["city_pop", "lofi"],
}

DEFAULT_MUSIC_PROFILES = ["lofi"]

DEFAULT_TOPIC_DISTRIBUTION: dict[str, int] = {
    "culture": 15,
    "society": 15,
    "transport": 10,
    "education": 10,
    "work": 10,
    "food": 10,
    "tourism": 10,
    "technology": 10,
    "history": 5,
    "weird_facts": 5,
}

# Legacy Portuguese slugs → English (one-shot migration)
LEGACY_CATEGORY_MAP: dict[str, str] = {
    "cultura": "culture",
    "sociedade": "society",
    "transporte": "transport",
    "educacao": "education",
    "trabalho": "work",
    "comida": "food",
    "turismo": "tourism",
    "tecnologia": "technology",
    "historia": "history",
    "curiosidades_bizarras": "weird_facts",
}


def music_profiles_for_category(
    category: str, overrides: dict[str, list[str]] | None = None
) -> list[str]:
    normalized_category = normalize_category(category)
    if overrides:
        override = overrides.get(normalized_category)
        if isinstance(override, list):
            normalized_override = [str(p).strip() for p in override if str(p).strip()]
            if normalized_override:
                return normalized_override
    return list(
        CATEGORY_MUSIC_DEFAULTS.get(normalized_category, DEFAULT_MUSIC_PROFILES)
    )


def topic_distribution_for_channel(
    overrides: dict[str, int] | None = None,
) -> dict[str, int]:
    distribution = dict(DEFAULT_TOPIC_DISTRIBUTION)
    if not isinstance(overrides, dict):
        return distribution

    for raw_category, raw_count in overrides.items():
        category = normalize_category(str(raw_category))
        if category not in VALID_CATEGORIES:
            continue
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            continue

        if count > 0:
            distribution[category] = count
        elif count == 0:
            distribution.pop(category, None)

    return distribution


def normalize_category(category: str) -> str:
    """Map legacy PT category slugs to English; pass through valid EN slugs."""
    if category in VALID_CATEGORIES:
        return category
    return LEGACY_CATEGORY_MAP.get(category, category)
