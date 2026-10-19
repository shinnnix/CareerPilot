import hashlib
import json
import logging

request_logger = logging.getLogger("careerpilot.requests")


def configure_observability() -> None:
    if not request_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        request_logger.addHandler(handler)
    request_logger.setLevel(logging.INFO)
    request_logger.propagate = False


def hash_identifier(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def log_request(**fields: object) -> None:
    request_logger.info(json.dumps(fields, ensure_ascii=False, separators=(",", ":")))
