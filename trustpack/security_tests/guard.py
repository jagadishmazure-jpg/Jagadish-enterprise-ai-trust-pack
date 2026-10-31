"""A small deterministic guard used as the system under test. It is a stand-in, not a product.

Input side: prompt-injection and jailbreak pattern checks after normalisation (lowercase,
zero-width characters removed, whitespace collapsed, simple leetspeak folded).
Output side: PII redaction with checksum validation (Luhn for cards, mod-97 for IBANs) so
random digit runs are not flagged.
"""
from __future__ import annotations

import re
import unicodedata

ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))
LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})

INJECTION = [
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|rules|messages)",
    r"disregard (the |your )?(system|previous) (prompt|instructions)",
    r"(reveal|print|show|repeat) (me )?(your|the) (system prompt|hidden instructions|instructions (you were given|above))",
    r"you are now (in )?(developer|admin|debug) mode",
    r"send (the|all|this) (data|conversation|context|documents?) to (http|https|www)",
    r"!\[[^\]]*\]\(https?://[^)]*\?(q|data|d)=",
    r"new instructions?:",
    r"system override",
]
JAILBREAK = [
    r"\bdan\b.*(do anything now|no restrictions)",
    r"pretend (you are|to be) .*(no|without) (any )?(rules|restrictions|filters|guidelines)",
    r"(developer|god) mode (enabled|on)",
    r"hypothetically,? .*how (would|could) (someone|one|i) (make|build) (a )?(bomb|weapon|malware)",
    r"for a (story|novel|movie),? .*(step[- ]by[- ]step|detailed) (instructions|guide) (to|for) "
    r"(make|build|synthesi[sz]e)",
    r"ignore your (safety|content) (policy|policies|guidelines)",
]
_INJ = [re.compile(p) for p in INJECTION]
_JB = [re.compile(p) for p in JAILBREAK]

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
PHONE = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)")
SSN = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b")


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH).lower().translate(LEET)
    return re.sub(r"\s+", " ", t).strip()


def detect_injection(text: str) -> bool:
    n = normalise(text)
    return any(p.search(n) for p in _INJ)


def detect_jailbreak(text: str) -> bool:
    n = normalise(text)
    return any(p.search(n) for p in _JB)


def luhn_ok(digits: str) -> bool:
    if len(set(digits)) < 2:  # all-zero or repeated placeholders are not cards
        return False
    d = [int(c) for c in digits][::-1]
    total = sum(d[0::2]) + sum(sum(divmod(2 * x, 10)) for x in d[1::2])
    return total % 10 == 0


def iban_ok(iban: str) -> bool:
    s = iban.replace(" ", "")
    if not 15 <= len(s) <= 34:
        return False
    r = s[4:] + s[:4]
    num = "".join(str(int(c, 36)) for c in r)
    return int(num) % 97 == 1


def redact(text: str) -> tuple[str, list[str]]:
    found: list[str] = []

    def sub(kind: str, rx: re.Pattern, check=None):
        nonlocal text

        def rep(m: re.Match) -> str:
            raw = m.group(0)
            if check and not check(raw):
                return raw
            found.append(kind)
            return f"[{kind.upper()}]"
        text = rx.sub(rep, text)

    sub("email", EMAIL)
    sub("iban", IBAN, iban_ok)
    sub("card", CARD, lambda s: luhn_ok(re.sub(r"\D", "", s)))
    sub("ssn", SSN)
    sub("phone", PHONE)
    return text, found
