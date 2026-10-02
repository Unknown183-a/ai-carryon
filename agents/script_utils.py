import re

# Sentence boundary: . ! ? and the Devanagari danda (।) followed by whitespace
_SENT_SPLIT = re.compile(r"(?<=[.!?\u0964])\s+")


def trim_to_sentences(script, max_words, keep_last_sentence=True):
    """Shorten a script to <= max_words WITHOUT cutting a sentence in half.

    - Drops whole sentences from the middle/end instead of slicing words.
    - keep_last_sentence=True always preserves the closing line (the CTA,
      e.g. "Follow for more AI and tech insights"), which a plain word
      slice would delete first.
    """
    script = script.strip()
    if len(script.split()) <= max_words:
        return script

    sentences = [s.strip() for s in _SENT_SPLIT.split(script) if s.strip()]
    tail = [sentences[-1]] if keep_last_sentence and len(sentences) > 2 else []
    body = sentences[: len(sentences) - len(tail)]
    budget = max_words - sum(len(s.split()) for s in tail)

    kept, used = [], 0
    for s in body:
        n = len(s.split())
        if used + n > budget:
            break
        kept.append(s)
        used += n

    if not kept:  # one giant sentence — last resort, plain word cut
        return " ".join(script.split()[:max_words])
    return " ".join(kept + tail)
