"""Test-wide defaults.

The optional ``semantic`` extra downloads an embedding model on first use.
Tests stay deterministic and offline: hybrid retrieval is exercised with an
explicit fake embedder, and the automatic embedder is disabled for every test
(and for CLI subprocesses, which inherit the environment).
"""

from __future__ import annotations

import os

os.environ.setdefault("FAROL_SEMANTIC", "0")
