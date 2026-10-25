"""
text_encoder.py — frozen text encoder for the semantic Brain features.

A pretrained sentence-embedding model turns a topic into a vector. It is used FROZEN (no fine-tuning, no gradients),
so nothing here needs training data. Everything is opt-in and fail-open: if no model is configured, the library is
not installed, or loading fails, `load_encoder_from_env()` returns None and the pipeline simply runs without
semantic features.

Configuration (env):
  BRAIN_TEXT_MODEL_NAME       Hugging Face model id (required to enable). Pick one that covers Hindi AND English
                              and check it on your own topics first; nothing here assumes a particular checkpoint.
  BRAIN_TEXT_MODEL_REVISION   immutable revision (commit hash) of that model (required: it is part of the cache key,
                              so a floating "main" would silently mix incompatible vectors)
  BRAIN_TEXT_MAX_LENGTH       tokens, default 128 (topics are short)
  BRAIN_TEXT_BATCH_SIZE       default 32
  BRAIN_TEXT_DEVICE           default cpu
  BRAIN_TEXT_CACHE_DIR        where weights are cached (cache this directory between CI runs)
  BRAIN_TEXT_PREFIX           optional text prefix some models need (e.g. "query: " for E5); it changes the vectors,
                              so it is folded into the preprocessing version

Do not commit weights. Install with:  pip install -r requirements_semantic.txt
"""
import hashlib
import os
import re
import unicodedata

PREPROCESSING_BASE = "v1"
MAX_TEXT_CHARS = 512

_WS = re.compile(r"\s+")


def normalize_text(text):
    """Deterministic cleanup shared by caching and encoding: Unicode NFKC, whitespace collapsed, casefolded,
    truncated. The original language and script are preserved (no transliteration, no translation)."""
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = _WS.sub(" ", t).strip().casefold()
    return t[:MAX_TEXT_CHARS]


def text_hash(normalized):
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def preprocessing_version(prefix=""):
    """Changes whenever the text fed to the model changes, so cached vectors can never go stale silently."""
    if not prefix:
        return PREPROCESSING_BASE
    return f"{PREPROCESSING_BASE}+p{hashlib.sha1(prefix.encode('utf-8')).hexdigest()[:8]}"


class SentenceTransformerEncoder:
    """Thin wrapper over sentence-transformers. Imported lazily so the rest of the pipeline never needs torch."""

    def __init__(self, model_id, revision, *, max_length=128, batch_size=32, device="cpu", cache_dir=None, prefix=""):
        from sentence_transformers import SentenceTransformer   # heavy import, only when actually enabled
        self.model_id, self.revision, self.prefix = model_id, revision, prefix
        self.batch_size = batch_size
        self.preprocessing_version = preprocessing_version(prefix)
        self._model = SentenceTransformer(model_id, revision=revision, device=device, cache_folder=cache_dir)
        self._model.max_seq_length = max_length

    def encode(self, texts):
        """list[str] (already normalized) -> list[list[float]], raw model output (normalisation is done at use)."""
        if not texts:
            return []
        inputs = [self.prefix + t for t in texts]
        vecs = self._model.encode(inputs, batch_size=self.batch_size, convert_to_numpy=True,
                                  normalize_embeddings=False, show_progress_bar=False)
        return [[float(x) for x in v] for v in vecs]


def _env_int(name, default):
    try:
        v = int(os.environ.get(name, default))
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


def load_encoder_from_env(log=print):
    """The configured encoder, or None (feature off). Never raises."""
    name = (os.environ.get("BRAIN_TEXT_MODEL_NAME") or "").strip()
    if not name:
        return None
    revision = (os.environ.get("BRAIN_TEXT_MODEL_REVISION") or "").strip()
    if not revision:
        log("Semantic: BRAIN_TEXT_MODEL_REVISION is not set; refusing to use a floating model revision")
        return None
    try:
        return SentenceTransformerEncoder(
            name, revision,
            max_length=_env_int("BRAIN_TEXT_MAX_LENGTH", 128),
            batch_size=_env_int("BRAIN_TEXT_BATCH_SIZE", 32),
            device=(os.environ.get("BRAIN_TEXT_DEVICE") or "cpu").strip() or "cpu",
            cache_dir=(os.environ.get("BRAIN_TEXT_CACHE_DIR") or "").strip() or None,
            prefix=os.environ.get("BRAIN_TEXT_PREFIX", ""))
    except Exception as e:   # missing library, bad model id, offline: semantic features are an enhancement
        log(f"Semantic: encoder unavailable ({type(e).__name__}): {e}")
        return None
