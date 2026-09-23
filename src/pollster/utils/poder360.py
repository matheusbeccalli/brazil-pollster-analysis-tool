"""Parsing helpers for the Poder360 aggregator backend JSON (2026 cycle)."""
import unicodedata

import pandas as pd

from pollster.config import POLLSTER_ALIASES_2026
from pollster.utils.normalize import normalize_pollster_name

# Substrings (accent-stripped, lower-case) that mark non-candidate rows.
NON_VALID_PATTERNS = ("branco", "nulo", "indecis", "nao sabe", "nao respond", "nao decid",
                      "nao opinou", "nenhum", "ninguem", "nao vai votar", "nao iria votar",
                      "outros")

FRAME_COLUMNS = ["poll_id", "instituto", "pollster_display_name", "data", "contratante",
                 "entrevistas", "margem", "registro", "turno", "cenario_idx",
                 "nome_candidato", "candidate_key", "partido", "percentual",
                 "is_valid_candidate"]


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c))


def candidate_key(name: str) -> str:
    """Accent- and case-insensitive key used to match the same candidate across polls."""
    return " ".join(_strip_accents(name or "").lower().split())


def parse_sample_size(value) -> int | None:
    """The API returns '2.006' (thousands separator) as the float 2.006."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    if v < 100:
        v *= 1000
    return int(round(v))


def is_valid_candidate(name: str) -> bool:
    key = candidate_key(name)
    return bool(key) and not any(p in key for p in NON_VALID_PATTERNS)


def split_scenarios(entries: list[dict], overflow: float = 103.0) -> list[list[dict]]:
    """The API flattens several scenarios into one list.

    A new scenario starts when a candidate name repeats, or when a valid candidate
    follows the blank/undecided block and adding it would push the running total
    past ``overflow`` (the previous scenario was already complete).
    """
    scenarios: list[list[dict]] = []
    current: list[dict] = []
    seen: set[str] = set()
    total = 0.0
    prev_valid = True
    for e in entries:
        name = e.get("nome")
        if not name:
            continue
        key = candidate_key(name)
        valid = is_valid_candidate(name)
        pct = e.get("percentual") or 0.0
        overflow_break = valid and not prev_valid and current and total + pct > overflow
        if key in seen or overflow_break:
            scenarios.append(current)
            current, seen, total = [], set(), 0.0
        current.append(e)
        seen.add(key)
        total += pct
        prev_valid = valid
    if current:
        scenarios.append(current)
    return scenarios


def normalize_pollster_2026(raw_name: str) -> str:
    name = (raw_name or "").strip()
    name = POLLSTER_ALIASES_2026.get(name, name)
    return normalize_pollster_name(name)


def polls_to_frame(raw: list[dict], turno: int) -> pd.DataFrame:
    rows = []
    for poll in raw:
        instituto = (poll.get("instituto") or poll.get("contratante") or "").strip()
        base = {
            "poll_id": poll.get("id"),
            "instituto": instituto,
            "pollster_display_name": normalize_pollster_2026(instituto),
            "data": pd.to_datetime(str(poll.get("data") or "")[:10], errors="coerce"),
            "contratante": poll.get("contratante"),
            "entrevistas": parse_sample_size(poll.get("entrevistas")),
            "margem": poll.get("margem"),
            "registro": poll.get("registro"),
            "turno": turno,
        }
        idx = 0
        for group in poll.get("apuracoes") or []:
            for scenario in split_scenarios(group):
                for e in scenario:
                    name = e["nome"].strip()
                    rows.append({**base, "cenario_idx": idx, "nome_candidato": name,
                                 "candidate_key": candidate_key(name),
                                 "partido": e.get("partido"),
                                 "percentual": e.get("percentual"),
                                 "is_valid_candidate": is_valid_candidate(name)})
                idx += 1
    return pd.DataFrame(rows, columns=FRAME_COLUMNS)
