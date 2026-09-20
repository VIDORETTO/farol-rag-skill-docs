"""Governed extractor registry for canonical IR production."""

from .base import ExtractionResult, Extractor, ExtractorError, ExtractorPolicy
from .legacy_text import LegacyTextExtractor
from .pdf import DoclingOcrAdapter
from .registry import ExtractorRegistry, default_registry
from .repository import RepositoryExtractor

__all__ = [
    "Extractor",
    "ExtractorError",
    "ExtractorPolicy",
    "ExtractionResult",
    "ExtractorRegistry",
    "DoclingOcrAdapter",
    "LegacyTextExtractor",
    "RepositoryExtractor",
    "default_registry",
]
