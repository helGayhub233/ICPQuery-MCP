"""Anticipated upstream failures with credential-safe messages."""


class QueryError(Exception):
    def __init__(self, error_type: str, message: str) -> None:
        self.error_type = error_type
        super().__init__(message)
