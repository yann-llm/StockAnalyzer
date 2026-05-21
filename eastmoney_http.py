"""HTTP helpers for Eastmoney fetchers."""

from __future__ import annotations

import ssl
import warnings
from http.client import HTTPResponse
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import certifi
import requests


EASTMONEY_HOST_SUFFIXES = (
    ".eastmoney.com",
    ".eastmoney.com.cn",
)

_CERTIFI_CONTEXT = ssl.create_default_context(cafile=certifi.where())
_INSECURE_CONTEXT = ssl._create_unverified_context()


def _request_url(request: Request | str) -> str:
    return request.full_url if isinstance(request, Request) else request


def _is_eastmoney_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host == "eastmoney.com" or any(host.endswith(suffix) for suffix in EASTMONEY_HOST_SUFFIXES)


def _is_ssl_certificate_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        current = current.__cause__ or current.__context__
    return "CERTIFICATE_VERIFY_FAILED" in str(exc)


def eastmoney_urlopen(request: Request | str, timeout: int) -> HTTPResponse:
    """Open Eastmoney URLs with certifi, falling back only for certificate-chain failures."""
    url = _request_url(request)
    try:
        return urlopen(request, timeout=timeout, context=_CERTIFI_CONTEXT)
    except Exception as exc:
        if not _is_eastmoney_url(url) or not _is_ssl_certificate_error(exc):
            raise
        warnings.warn(
            f"TLS certificate verification failed for {url}; retrying Eastmoney request without certificate verification.",
            RuntimeWarning,
            stacklevel=2,
        )
        return urlopen(request, timeout=timeout, context=_INSECURE_CONTEXT)


def eastmoney_requests_get(url: str, **kwargs: Any) -> requests.Response:
    """requests.get wrapper matching eastmoney_urlopen's scoped TLS fallback."""
    try:
        return requests.get(url, **kwargs)
    except requests.exceptions.SSLError:
        if not _is_eastmoney_url(url):
            raise
        warnings.warn(
            f"TLS certificate verification failed for {url}; retrying Eastmoney request without certificate verification.",
            RuntimeWarning,
            stacklevel=2,
        )
        kwargs["verify"] = False
        return requests.get(url, **kwargs)
