"""Custom exception hierarchy for Databricks access."""


class DatabricksError(Exception):
    """Base exception for Databricks operations."""


class DatabricksAuthenticationError(DatabricksError):
    """Raised when authentication fails."""


class DatabricksConnectionError(DatabricksError):
    """Raised when we cannot establish or maintain a connection."""


class DatabricksQueryError(DatabricksError):
    """Raised when a query fails."""


class ContentNotFoundError(DatabricksError):
    """Raised when a content_id is not present."""


class InvalidContentIdError(DatabricksError):
    """Raised when a provided content_id is malformed."""


class RateLimitExceededError(DatabricksError):
    """Raised when the warehouse throttles requests."""

