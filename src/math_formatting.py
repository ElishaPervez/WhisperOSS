import re


_SUPERSCRIPTS = str.maketrans(
    {
        "0": "⁰",
        "1": "¹",
        "2": "²",
        "3": "³",
        "4": "⁴",
        "5": "⁵",
        "6": "⁶",
        "7": "⁷",
        "8": "⁸",
        "9": "⁹",
        "-": "⁻",
    }
)


def _to_superscript(value: str) -> str:
    return str(value).translate(_SUPERSCRIPTS)


def _looks_like_math_dictation(text: str) -> bool:
    lower = f" {str(text or '').lower()} "
    keywords = (
        " plus ",
        " minus ",
        " equals ",
        " equal ",
        " square",
        " cubed",
        " power ",
        " times ",
        " divided ",
    )
    if not any(keyword in lower for keyword in keywords):
        return False
    return bool(re.search(r"\b[xyz]\b|\d|[=+\-×÷]", lower))


def normalize_math_dictation(text: str) -> str:
    """Normalize common spoken math dictation into readable symbolic text."""
    source = str(text or "")
    if not source.strip():
        return source
    if not _looks_like_math_dictation(source):
        return source

    normalized = " ".join(source.split())

    normalized = re.sub(r"\bis\s+equals?\b", "=", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bis\s+equal\s+to\b", "=", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bequals?\s+to\b", "=", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bequals?\b", "=", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bplus\b", "+", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bminus\b", "-", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bmultiplied\s+by\b", "×", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\btimes\b", "×", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bdivided\s+by\b", "÷", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bby\s+taking\b", ", taking", normalized, flags=re.IGNORECASE)

    token = r"[A-Za-z0-9]+"
    grouped_power_hint = r"(?:the\s+whole|whole|all|entire)"
    normalized = re.sub(
        rf"\b({token})\s*\+\s*({token})\s*(?:{grouped_power_hint}\s*)?(?:square|squared)\b",
        r"(\1 + \2)²",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        rf"\b({token})\s*-\s*({token})\s*(?:{grouped_power_hint}\s*)?(?:square|squared)\b",
        r"(\1 - \2)²",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        rf"\b({token})\s*\+\s*({token})\s*(?:{grouped_power_hint}\s*)?(?:cube|cubed)\b",
        r"(\1 + \2)³",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        rf"\b({token})\s*-\s*({token})\s*(?:{grouped_power_hint}\s*)?(?:cube|cubed)\b",
        r"(\1 - \2)³",
        normalized,
        flags=re.IGNORECASE,
    )

    normalized = re.sub(
        rf"\b((?!(?:whole|all|entire|the)\b){token})\s*(?:square|squared)\b(?!\s*root)",
        r"\1²",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        rf"\b((?!(?:whole|all|entire|the)\b){token})\s*(?:cube|cubed)\b",
        r"\1³",
        normalized,
        flags=re.IGNORECASE,
    )

    def _power_replacement(match: re.Match) -> str:
        base = match.group(1)
        exponent = match.group(2)
        return f"{base}{_to_superscript(exponent)}"

    normalized = re.sub(
        rf"(\b{token}|\))\s*(?:to\s+the\s+power\s+of|power)\s*(-?\d+)\b",
        _power_replacement,
        normalized,
        flags=re.IGNORECASE,
    )

    normalized = re.sub(r"\s*([=+\-×÷])\s*", r" \1 ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"\s+,", ",", normalized)
    normalized = re.sub(r",\s*", ", ", normalized)
    normalized = re.sub(r"(\d),(\d)", r"\1, \2", normalized)
    normalized = re.sub(r"\s+\.", ".", normalized)
    normalized = re.sub(r"\s+([!?])", r"\1", normalized)

    return normalized
