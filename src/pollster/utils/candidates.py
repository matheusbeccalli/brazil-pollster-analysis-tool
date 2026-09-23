import unicodedata

from rapidfuzz import fuzz

FUZZY_THRESHOLD = 85.0
MIN_FUZZY_CHARS = 4


def _normalize_name(name: str) -> str:
    name = name.upper().strip()
    nfkd = unicodedata.normalize("NFKD", name)
    return " ".join("".join(c for c in nfkd if not unicodedata.combining(c)).split())


def match_candidate_name(
    poll_name: str,
    official_names: list[str],
    poll_party: str | None = None,
    official_parties: dict[str, str] | None = None,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
) -> str | None:
    """Match a poll candidate name to an official (TSE) name.

    Order: exact match after normalization; token-set similarity (a ballot name such as
    "DILMA" is a subset of "DILMA ROUSSEFF" and scores 100), ties broken by party;
    finally, the single official candidate of the same party.
    """
    norm_poll = _normalize_name(poll_name)

    for official in official_names:
        if _normalize_name(official) == norm_poll:
            return official

    scored = []
    if len(norm_poll.replace(" ", "")) >= MIN_FUZZY_CHARS:
        for official in official_names:
            norm_official = _normalize_name(official)
            if len(norm_official.replace(" ", "")) < MIN_FUZZY_CHARS:
                continue
            score = fuzz.token_set_ratio(norm_poll, norm_official)
            if score >= fuzzy_threshold:
                scored.append((score, official))
    if scored:
        best_score = max(s for s, _ in scored)
        tied = [name for s, name in scored if s == best_score]
        if len(tied) > 1 and poll_party and official_parties:
            same_party = [n for n in tied if official_parties.get(n) == poll_party]
            if len(same_party) == 1:
                return same_party[0]
        return tied[0]

    if poll_party and official_parties:
        matches = [name for name, party in official_parties.items() if party == poll_party]
        if len(matches) == 1:
            return matches[0]

    return None
