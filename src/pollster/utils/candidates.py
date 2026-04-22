import unicodedata
from rapidfuzz import fuzz


def _normalize_name(name: str) -> str:
    name = name.upper().strip()
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def match_candidate_name(
    poll_name: str,
    official_names: list[str],
    poll_party: str | None = None,
    official_parties: dict[str, str] | None = None,
    fuzzy_threshold: float = 75.0,
) -> str | None:
    norm_poll = _normalize_name(poll_name)

    for official in official_names:
        if _normalize_name(official) == norm_poll:
            return official

    best_score = 0.0
    best_match = None
    for official in official_names:
        score = fuzz.token_sort_ratio(norm_poll, _normalize_name(official))
        if score > best_score:
            best_score = score
            best_match = official
    if best_score >= fuzzy_threshold and best_match is not None:
        return best_match

    if poll_party and official_parties:
        matches = [name for name, party in official_parties.items() if party == poll_party]
        if len(matches) == 1:
            return matches[0]

    return None
