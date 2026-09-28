"""Canonical text for deterministic policy checks (not model instructions)."""
import unicodedata


def normalize_text(text: str, *, accents: bool = False) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Cf")
    if accents:
        text = "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        ).replace("đ", "d").replace("Đ", "D")
    return " ".join(text.casefold().split())
