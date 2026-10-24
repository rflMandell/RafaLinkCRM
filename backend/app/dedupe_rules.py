"""Etapa 10: regras de normalização e comparação usadas pela importação e pela deduplicação."""
import re
import unicodedata

COMPANY_SUFFIXES = {"ltda", "me", "epp", "eireli", "sa", "s", "a", "cia", "company", "inc", "llc", "do", "da", "de", "e"}


def norm_text(value) -> str:
    """minúsculas, sem acentos, sem pontuação, espaços únicos."""
    s = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


def norm_email(value) -> str | None:
    v = str(value or "").strip().lower()
    return v or None


def norm_phone(value) -> str | None:
    """Só dígitos; compara pelos últimos 9 (ignora +55 e DDD). Menos de 8 dígitos não conta."""
    digits = re.sub(r"\D+", "", str(value or ""))
    return digits[-9:] if len(digits) >= 8 else None


def norm_company(value) -> str | None:
    words = [w for w in norm_text(value).split() if w not in COMPANY_SUFFIXES]
    return " ".join(words) or None


def norm_domain(value) -> str | None:
    v = str(value or "").strip().lower()
    v = re.sub(r"^https?://", "", v)
    v = re.sub(r"^www\.", "", v).split("/")[0]
    return v or None