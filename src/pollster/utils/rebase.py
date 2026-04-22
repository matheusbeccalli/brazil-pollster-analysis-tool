def rebase_to_valid_votes(raw_pcts: dict[str, float]) -> dict[str, float]:
    total = sum(raw_pcts.values())
    if total == 0:
        return raw_pcts
    return {name: (pct / total) * 100.0 for name, pct in raw_pcts.items()}
