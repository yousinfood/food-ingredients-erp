"""Normalize voice/STT transcripts before customer search (no SpeechRecognition changes)."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# Longest-first phrase mishears (Mandarin STT confusions).
_PHRASE_MISHEARS: tuple[tuple[str, str], ...] = (
    ("去洗澡機", "布布炸雞"),
    ("去洗澡机", "布布炸雞"),
    ("去洗澡鸡", "布布炸雞"),
    ("去洗澡雞", "布布炸雞"),
)

# Bopomofo syllable (no tone) → default hanzi for search normalization.
_ZHUYIN_SYLLABLE_TO_HANZI: dict[str, str] = {
    "ㄅㄨ": "布",
    "ㄅㄨˋ": "布",
    "ㄅㄨˊ": "布",
    "ㄅㄨˇ": "布",
    "ㄅㄨ˙": "布",
    "ㄓㄚ": "炸",
    "ㄓㄚˋ": "炸",
    "ㄐㄧ": "雞",
}

# Extend: common syllables without tone marks (STT often drops tones).
for _base, _han in list(_ZHUYIN_SYLLABLE_TO_HANZI.items()):
    _plain = _base.rstrip("ˊˇˋ˙")
    if _plain not in _ZHUYIN_SYLLABLE_TO_HANZI:
        _ZHUYIN_SYLLABLE_TO_HANZI[_plain] = _han

_BOPOMOFO_RE = re.compile(r"[ㄅ-ㄩˊˇˋ˙]+")
_SPACE_RE = re.compile(r"\s+")
_FRIED_SUFFIX_RE = re.compile(r"炸[机機鸡雞]")
_TWIN_BU_RE = re.compile(r"(?:不|哺|布|步)(?:不|哺|布|步)")


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def _strip_spaces(text: str) -> str:
    return _SPACE_RE.sub("", text)


def _apply_phrase_mishears(text: str) -> str:
    out = text
    for src, dst in _PHRASE_MISHEARS:
        if src in out:
            out = out.replace(src, dst)
    return out


def _twin_bu_to_bubu(text: str) -> str:
    def repl(_m: re.Match[str]) -> str:
        return "布布"

    return _TWIN_BU_RE.sub(repl, text)


def _fried_chicken_suffix(text: str) -> str:
    return _FRIED_SUFFIX_RE.sub("炸雞", text)


def _bopomofo_to_hanzi(text: str) -> str:
    if not _BOPOMOFO_RE.search(text):
        return text

    syllables = sorted(_ZHUYIN_SYLLABLE_TO_HANZI.keys(), key=len, reverse=True)

    def replace_run(match: re.Match[str]) -> str:
        run = match.group(0)
        out: list[str] = []
        i = 0
        while i < len(run):
            matched = False
            for syll in syllables:
                if run.startswith(syll, i):
                    out.append(_ZHUYIN_SYLLABLE_TO_HANZI[syll])
                    i += len(syll)
                    matched = True
                    break
            if not matched:
                i += 1
        return "".join(out) if out else run

    return _BOPOMOFO_RE.sub(replace_run, text)


def normalize_voice_query(query: str) -> str:
    """Canonical form for voice-driven customer search."""
    q = _strip_spaces(_nfkc(query))
    if not q:
        return ""
    q = _bopomofo_to_hanzi(q)
    q = _twin_bu_to_bubu(q)
    q = _fried_chicken_suffix(q)
    q = _apply_phrase_mishears(q)
    return q


def _pinyin_skeleton(text: str) -> str:
    """Rough romanization skeleton for fuzzy compare (no external deps)."""
    from apps.sales.services.voice_search_pinyin import text_to_pinyin_skeleton

    return text_to_pinyin_skeleton(text)


def similarity_score(a: str, b: str) -> float:
    """0–1 similarity using normalized text and pinyin skeleton."""
    if not a or not b:
        return 0.0
    na = normalize_voice_query(a)
    nb = normalize_voice_query(b)
    scores = [
        SequenceMatcher(None, na, nb).ratio(),
        SequenceMatcher(None, a, b).ratio(),
    ]
    pa, pb = _pinyin_skeleton(na or a), _pinyin_skeleton(nb or b)
    if pa and pb:
        scores.append(SequenceMatcher(None, pa, pb).ratio())
    return max(scores)


VOICE_SIMILARITY_THRESHOLD = 0.7
