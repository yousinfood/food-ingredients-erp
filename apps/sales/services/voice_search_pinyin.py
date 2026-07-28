"""Minimal hanzi → pinyin skeleton for voice fuzzy matching (no third-party deps)."""
from __future__ import annotations

# Common readings for customer-name search; unknown chars kept as-is (lowered).
_CHAR_PINYIN: dict[str, str] = {
    "布": "bu",
    "不": "bu",
    "哺": "bu",
    "步": "bu",
    "部": "bu",
    "炸": "zha",
    "乍": "zha",
    "雞": "ji",
    "鸡": "ji",
    "機": "ji",
    "机": "ji",
    "去": "qu",
    "洗": "xi",
    "澡": "zao",
    "店": "dian",
    "餐": "can",
    "廳": "ting",
    "厅": "ting",
    "食": "shi",
    "品": "pin",
    "有": "you",
    "信": "xin",
    "華": "hua",
    "华": "hua",
    "姐": "jie",
    "都": "du",
    "國": "guo",
    "国": "guo",
    "街": "jie",
    "小": "xiao",
    "籠": "long",
    "笼": "long",
    "包": "bao",
    "黑": "hei",
    "輪": "lun",
    "轮": "lun",
    "蚵": "ke",
    "仔": "zi",
    "煎": "jian",
    "彩": "cai",
    "虹": "hong",
    "日": "ri",
    "本": "ben",
}


def text_to_pinyin_skeleton(text: str) -> str:
    parts: list[str] = []
    for ch in text or "":
        py = _CHAR_PINYIN.get(ch)
        if py:
            parts.append(py)
        elif "\u4e00" <= ch <= "\u9fff":
            parts.append(ch.casefold())
        elif ch.isalnum():
            parts.append(ch.casefold())
    return "".join(parts)
