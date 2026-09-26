"""Split the policy markdown into sections. Each `## Heading` becomes one searchable
section (long sections are split by paragraph), and the heading travels with every
piece so answers can cite which policy section they came from."""
import re
from dataclasses import dataclass
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parents[2] / "data_seed" / "policy.md"
MAX_CHARS = 900


@dataclass
class Section:
    id: str
    title: str
    text: str  # body only, heading excluded


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def load_sections(markdown: str) -> list[Section]:
    sections: list[Section] = []
    for block in re.split(r"(?m)^## ", markdown)[1:]:
        title, _, body = block.partition("\n")
        title, body = title.strip(), body.strip()
        if not body:
            continue
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        pieces, current = [], ""
        for p in paras:
            if current and len(current) + len(p) > MAX_CHARS:
                pieces.append(current)
                current = p
            else:
                current = f"{current}\n\n{p}" if current else p
        pieces.append(current)
        for i, piece in enumerate(pieces):
            sid = _slug(title) + (f"-{i + 1}" if len(pieces) > 1 else "")
            sections.append(Section(id=sid, title=title, text=piece))
    return sections


def load_policy(path: Path = POLICY_PATH) -> list[Section]:
    return load_sections(path.read_text(encoding="utf-8"))
