"""Errors raised by the ingest stage."""

from __future__ import annotations


class IngestError(Exception):
    """Base class: the source could not be turned into a `SourceDocument`."""


class FetchError(IngestError):
    """Downloading a URL failed: network error, error status or a response that is too large."""


class UnsupportedSourceError(IngestError):
    """The content type or the file extension is not supported."""


class ExtractionError(IngestError):
    """The document could not be parsed, or it contains no usable text."""


class NoTextLayerError(ExtractionError):
    """The PDF has no extractable text, for example a scan.

    Scans need the model's image input, which the pipeline does not offer yet
    (docs/architecture.md §4.1).
    """


class SectionNotFoundError(IngestError):
    """`select_section` found no heading that contains the query."""
