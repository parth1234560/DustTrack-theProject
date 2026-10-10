"""Error taxonomy: API error codes and workflow exceptions."""

from __future__ import annotations

from typing import Any

# API error code -> HTTP status. UNAUTHORIZED is additive: the contract's
# status table needs 401 but the brief's code list omits it.
API_STATUS: dict[str, int] = {
    "INVALID_JSON": 400,
    "VALIDATION_ERROR": 400,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "SEGMENT_NOT_FOUND": 404,
    "INSPECTION_NOT_FOUND": 404,
    "ROUTE_NOT_FOUND": 404,
    "INTERNAL_ERROR": 500,
}


class ApiError(Exception):
    """An error that maps directly to an API error response."""

    def __init__(self, code: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status if status is not None else API_STATUS.get(code, 500)

    def to_body(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message}}


class InspectionRejected(Exception):
    """Raised by validate_input after persisting REJECTED.

    Step Functions treats this as a terminal Fail state; the DB is already
    correct, so nothing else may write.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.rejection_code = code
        self.rejection_message = message
