class DomainError(Exception):
    """Base domain error for the application."""


class ValidationError(DomainError):
    """Generic validation error."""
