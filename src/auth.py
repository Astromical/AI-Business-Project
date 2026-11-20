"""Wachtwoorden en rechten per rol. Kent geen SQLite en geen Streamlit."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Literal

from src.models import Rol

Recht = Literal["accounts", "demodata", "gegevens", "importeren", "rooster", "eigen_rooster"]

MINIMALE_LENGTE = 8
_N, _R, _P = 2**14, 8, 1  # scrypt-kosten; staan ook in de hash, dus later aan te passen

RECHTEN: dict[Rol, frozenset[Recht]] = {
    "roostermaker": frozenset({"accounts", "demodata", "gegevens", "importeren", "rooster"}),
    "leraar": frozenset({"eigen_rooster"}),
}


def mag(rol: str, recht: Recht) -> bool:
    """Heeft deze rol dit recht? Een onbekende rol heeft geen enkel recht."""
    return recht in RECHTEN.get(rol, frozenset())


def _scrypt(wachtwoord: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    """De scrypt-sleutel van een wachtwoord."""
    return hashlib.scrypt(wachtwoord.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)


# Voorlopig (prototype): alle leraren krijgen hetzelfde wachtwoord.
LERAAR_WACHTWOORD = "docent123"


def hash_wachtwoord(wachtwoord: str) -> str:
    """Hash een wachtwoord met een eigen salt, als 'scrypt$n$r$p$salt$sleutel'."""
    salt = os.urandom(16)
    sleutel = _scrypt(wachtwoord, salt, _N, _R, _P)
    delen = (base64.b64encode(salt).decode(), base64.b64encode(sleutel).decode())
    return f"scrypt${_N}${_R}${_P}${delen[0]}${delen[1]}"


def controleer_wachtwoord(wachtwoord: str, opgeslagen: str) -> bool:
    """Klopt dit wachtwoord met de opgeslagen hash? Een onleesbare hash klopt nooit."""
    try:
        soort, n, r, p, salt, sleutel = opgeslagen.split("$")
        if soort != "scrypt":
            return False
        verwacht = base64.b64decode(sleutel)
        berekend = _scrypt(wachtwoord, base64.b64decode(salt), int(n), int(r), int(p))
    except ValueError:
        return False
    return hmac.compare_digest(berekend, verwacht)


# --- sessiecode: blijft ingelogd na vernieuwen van de pagina ---

SESSIE_DUUR_S = 8 * 3600


def _b64(gegevens: bytes) -> str:
    """URL-veilige base64 zonder opvulling."""
    return base64.urlsafe_b64encode(gegevens).decode().rstrip("=")


def _onderteken(deel: str, sleutel: bytes) -> str:
    """De HMAC-handtekening van een deel van de code."""
    return _b64(hmac.new(sleutel, deel.encode(), hashlib.sha256).digest())


def maak_sessiecode(naam: str, sleutel: bytes, nu: float) -> str:
    """Een ondertekende code die bewijst dat naam is ingelogd, geldig tot SESSIE_DUUR_S na nu."""
    deel = f"{_b64(naam.encode())}.{int(nu) + SESSIE_DUUR_S}"
    return f"{deel}.{_onderteken(deel, sleutel)}"


def lees_sessiecode(code: str, sleutel: bytes, nu: float) -> str | None:
    """De naam uit een geldige, niet verlopen code; anders None."""
    try:
        naam_b64, vervalt, handtekening = code.split(".")
        if not hmac.compare_digest(handtekening, _onderteken(f"{naam_b64}.{vervalt}", sleutel)):
            return None
        if int(vervalt) < nu:
            return None
        return base64.urlsafe_b64decode(naam_b64 + "=" * (-len(naam_b64) % 4)).decode()
    except (ValueError, TypeError, UnicodeDecodeError):
        return None
