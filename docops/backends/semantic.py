"""Optional local embeddings for hybrid retrieval (extra ``semantic``).

Runs a small multilingual ONNX model on CPU through fastembed; no API, no key.
Long blocks are embedded as overlapping word windows and scored by their best
window, because compact models truncate their input (measured on the real
acceptance corpus: windowed hybrid raised recall@5 from 0.77 to 0.87).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Protocol

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# Models trained with asymmetric prefixes (query vs passage). The prefixes are
# part of the embedding profile, so changing them requires a rebuild; models
# without prefixes keep the exact 3.0 profile and their existing indexes.
PREFIXES: dict[str, tuple[str, str]] = {
    "intfloat/multilingual-e5-large": ("query: ", "passage: "),
    "Qwen/Qwen3-Embedding-0.6B": (
        "Instruct: Given a question, retrieve passages that answer it\nQuery: ",
        "",
    ),
    "Qwen/Qwen3-Embedding-0.6B-Q": (
        "Instruct: Given a question, retrieve passages that answer it\nQuery: ",
        "",
    ),
}
WINDOW_WORDS = 80
STRIDE_WORDS = 60


class Embedder(Protocol):
    profile: dict[str, Any]

    def embed_documents(self, texts: list[str]) -> Any: ...

    def embed_query(self, text: str) -> Any: ...


def windows(text: str, heading: str = "") -> list[str]:
    """Overlapping word windows of a block, each prefixed by its heading context."""

    words = text.split()
    prefix = f"{heading}\n" if heading else ""
    if len(words) <= WINDOW_WORDS:
        return [prefix + " ".join(words)]
    chunks = []
    for start in range(0, len(words), STRIDE_WORDS):
        chunks.append(prefix + " ".join(words[start : start + WINDOW_WORDS]))
        if start + WINDOW_WORDS >= len(words):
            break
    return chunks


@contextmanager
def _quiet_native_stderr() -> Iterator[None]:
    """Silence C-level warnings (onnxruntime device discovery) while the model loads.

    MCP clients read the server's stdio; native libraries must not write to it.
    """

    try:
        saved = os.dup(2)
    except OSError:
        yield
        return
    try:
        with open(os.devnull, "w") as sink:
            os.dup2(sink.fileno(), 2)
            yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)


class FastEmbedEmbedder:
    def __init__(self, model: str = DEFAULT_MODEL, cache_dir: Path | str | None = None, threads: int | None = None):
        directory = Path(cache_dir or os.environ.get("FAROL_MODELS_DIR") or Path.home() / ".cache" / "farol" / "models")
        with _quiet_native_stderr():
            import numpy  # noqa: F401  (declared dependency of the extra)
            import onnxruntime  # type: ignore[import-not-found]
            from fastembed import TextEmbedding  # type: ignore[import-not-found]

            onnxruntime.set_default_logger_severity(3)
            self._model = TextEmbedding(model, cache_dir=str(directory), threads=threads)
            dimension = self._dimension()
        self.query_prefix, self.passage_prefix = PREFIXES.get(model, ("", ""))
        self.profile: dict[str, Any] = {
            "model": model,
            "dim": dimension,
            "window": WINDOW_WORDS,
            "stride": STRIDE_WORDS,
        }
        if self.query_prefix or self.passage_prefix:
            self.profile.update(query_prefix=self.query_prefix, passage_prefix=self.passage_prefix)

    def _dimension(self) -> int:
        return int(len(next(iter(self._model.embed(["dimension probe"])))))

    def embed_documents(self, texts: list[str]) -> Any:
        import numpy as np

        texts = [self.passage_prefix + text for text in texts] if self.passage_prefix else texts
        return np.array(list(self._model.embed(texts, batch_size=32)), dtype=np.float32)

    def embed_query(self, text: str) -> Any:
        import numpy as np

        return np.array(next(iter(self._model.query_embed([self.query_prefix + text]))), dtype=np.float32)


def semantic_available() -> bool:
    """Whether the extra is installed, checked without importing native libraries."""

    from importlib.util import find_spec

    installed = all(find_spec(name) is not None for name in ("fastembed", "numpy", "onnxruntime"))
    return installed and os.environ.get("FAROL_SEMANTIC", "1") != "0"


def load_embedder() -> Embedder | None:
    """The default embedder when the ``semantic`` extra is installed, else None."""

    if not semantic_available():
        return None
    model = os.environ.get("FAROL_EMBEDDING_MODEL") or DEFAULT_MODEL
    try:
        return FastEmbedEmbedder(model)
    except Exception as exc:  # download blocked, unknown model, broken runtime
        from .base import BackendError

        raise BackendError(
            "embedding_model_unavailable",
            f"the embedding model {model} could not be loaded; check the network or set FAROL_SEMANTIC=0",
        ) from exc
