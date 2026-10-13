"""Input validation shared by import and maintenance tools."""
VALID_EFFECTS = frozenset(("allow", "deny"))

def require_effect(effect):
    if effect not in VALID_EFFECTS:
        raise ValueError("effect must be allow or deny")
    return effect

def require_interval(start, end):
    if end is not None and end <= start:
        raise ValueError("validity end must be after validity start")
    return start, end

def require_window(since, until):
    if until <= since:
        raise ValueError("export window must be nonempty")
    return since, until

def require_prefix(prefix):
    if not isinstance(prefix, str):
        raise TypeError("resource prefix must be text")
    return prefix
