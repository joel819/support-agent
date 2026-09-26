"""Tiny keyword helpers shared by the offline embedder and the rule-based demo agent."""
import re

_WORD = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    "a an the is are was were be been of to in on for and or with what which who whom how when where why "
    "do does did can could should would will i we you it this that these those my our your their at by "
    "from as about into than then there here any all some much many me us get gets long need needs please tell know hi hello hey thanks thank hey am im its dont".split()
)


def stem(w: str) -> str:
    """Crude plural stripping: limits -> limit, webhooks -> webhook (but not 'access')."""
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def keywords(text: str) -> list[str]:
    return [stem(w) for w in _WORD.findall(text.lower()) if w not in STOPWORDS and len(w) > 1]


def terms(text: str) -> set[str]:
    return set(keywords(text))
