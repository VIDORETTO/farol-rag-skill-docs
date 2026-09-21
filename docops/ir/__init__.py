"""Canonical, immutable intermediate representation for Farol 2.0."""

from .core import (
    BackendMapping,
    ExtractionReceipt,
    IRBlock,
    IRDocument,
    IRStore,
    IRValidationError,
    ValidationReport,
    validate_ir_document,
)

__all__ = [
    "BackendMapping",
    "ExtractionReceipt",
    "IRBlock",
    "IRDocument",
    "IRStore",
    "IRValidationError",
    "ValidationReport",
    "validate_ir_document",
]
