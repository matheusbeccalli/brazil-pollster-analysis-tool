from pollster.config import POLLSTER_MERGES, POLLSTER_ALIASES


def normalize_pollster_name(raw_name: str) -> str:
    if raw_name in POLLSTER_MERGES:
        return POLLSTER_MERGES[raw_name]
    if raw_name in POLLSTER_ALIASES:
        return POLLSTER_ALIASES[raw_name]
    return raw_name
