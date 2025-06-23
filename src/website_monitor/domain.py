import time
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, NamedTuple, Optional


class HttpMethod(str, Enum):
    """
    Definisce i metodi HTTP supportati come un tipo sicuro e controllato.
    Ereditare da 'str' permette ai membri di comportarsi come stringhe.
    """

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class Target(NamedTuple):
    """
    Rappresenta un singolo target da monitorare, con la sua configurazione completa.
    Questa struttura dati corrisponde fedelmente alle colonne della tabella
    'monitored_targets'.
    """

    id: int
    url: str
    method: HttpMethod
    check_interval: timedelta
    regex_pattern: Optional[str]
    default_headers: Optional[Dict[str, Any]]


@dataclass
class RequestTrace:
    """A data class to store raw timing information for a single request."""

    request_start: float = field(default_factory=time.monotonic)
    dns_resolve_end: float = 0.0
    connect_end: float = 0.0
    request_sent: float = 0.0
    response_headers_received: float = 0.0
    response_body_received: float = 0.0
    request_end: float = 0.0


class FetchResult(NamedTuple):
    """
    A plain data structure holding the result of a single monitoring check.
    This object is passed through the result processing pipeline.
    """

    target: Target
    error: Optional[Exception]
    total_time: float
    status_code: Optional[int]
    request_trace: Optional[RequestTrace]
    regex_has_matches: Optional[bool]
