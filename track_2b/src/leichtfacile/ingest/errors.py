"""Errors raised by the ingest stage."""

from __future__ import annotations


class IngestError(Exception):
    """Base class: the source could not be turned into a `SourceDocument`."""


class FetchError(IngestError):
    """Downloading a URL failed: network error, error status or a response that is too large."""


class UnknownHostError(FetchError):
    """The host name of a URL, or of a redirect target, does not resolve."""

    def __init__(self, host: str) -> None:
        self.host = host
        super().__init__(f"the host {host} cannot be found")


class PrivateAddressError(FetchError):
    """The host of a URL, or of a redirect target, resolves to an address that is not on
    the public internet (private, loopback, link-local, ...): refused, so that the
    server cannot be used to reach internal services (server-side request forgery)."""

    def __init__(self, host: str, address: str) -> None:
        self.host = host
        self.address = address
        where = host if host == address else f"{host} ({address})"
        super().__init__(f"{where} is in the private network; only public pages are fetched")


class UnsupportedSourceError(IngestError):
    """The content type or the file extension is not supported."""


class ExtractionError(IngestError):
    """The document could not be parsed, or it contains no usable text."""


class NoTextLayerError(ExtractionError):
    """The PDF has no extractable text, for example a scan.

    Scans need the model's image input, which the pipeline does not offer yet
    (track_2b/docs/architecture.md §4.1).
    """


class SectionNotFoundError(IngestError):
    """`select_section` found no heading that contains the query."""
