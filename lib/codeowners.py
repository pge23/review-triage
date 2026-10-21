"""CODEOWNERS pattern matching with gitignore-like semantics, last match wins."""

import re


def _pattern_to_regex(pattern: str) -> str:
    """Translate one CODEOWNERS path pattern into an anchored regex."""
    anchored = pattern.startswith("/")
    is_dir = pattern.endswith("/")
    body = pattern.strip("/")

    parts = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "*":
            if body[i : i + 2] == "**":
                parts.append(".*")
                i += 2
                continue
            parts.append("[^/]*")
        elif c == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(c))
        i += 1
    core = "".join(parts)

    # An unanchored pattern with no slash matches that segment at any depth.
    prefix = "" if anchored or "/" in body else "(?:.*/)?"
    suffix = "/.*" if is_dir else "(?:/.*)?"
    return f"^{prefix}{core}{suffix}$"


class CodeOwners:
    def __init__(self, text: str):
        self.rules = []
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            fields = line.split()
            if len(fields) < 2:
                continue
            pattern, owners = fields[0], [o.lower() for o in fields[1:]]
            try:
                self.rules.append((pattern, re.compile(_pattern_to_regex(pattern)), owners))
            except re.error:
                continue

    def owners_of(self, path: str):
        """Return (pattern, owners) for the last rule matching path, else (None, [])."""
        path = path.lstrip("/")
        for pattern, rx, owners in reversed(self.rules):
            if rx.match(path):
                return pattern, owners
        return None, []

    def matched_by(self, paths, owner: str):
        """Return the patterns through which `owner` owns any of `paths`."""
        owner = owner.lower()
        hits = {}
        for path in paths:
            pattern, owners = self.owners_of(path)
            if pattern and owner in owners:
                hits.setdefault(pattern, []).append(path)
        return hits
