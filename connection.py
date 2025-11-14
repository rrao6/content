"""Databricks SQL connection utilities with retries and pooling."""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Generator, Optional

import structlog
from databricks import sql
from databricks.sql.client import Connection, Cursor
from tenacity import (
    RetryCallState,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import DatabricksConfig, get_config
from exceptions import DatabricksAuthenticationError, DatabricksConnectionError

logger = structlog.get_logger(__name__)


def _log_retry(retry_state: RetryCallState) -> None:
    logger.warning(
        "databricks_connection_retry",
        attempt=retry_state.attempt_number,
        last_exception=str(retry_state.outcome.exception())
        if retry_state.outcome
        else None,
    )


class ConnectionProvider:
    """Provides thread-safe access to a reused Databricks connection."""

    def __init__(self, config: Optional[DatabricksConfig] = None) -> None:
        self.config = config or get_config()
        self._connection: Optional[Connection] = None
        self._lock = threading.RLock()

    def close(self) -> None:
        """Close the underlying connection if it exists."""
        with self._lock:
            if self._connection:
                try:
                    self._connection.close()
                finally:
                    self._connection = None

    def _is_alive(self) -> bool:
        """Check whether existing connection responds."""
        if not self._connection:
            return False
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchall()
            cursor.close()
            return True
        except Exception:
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(DatabricksConnectionError),
        before_sleep=before_sleep_log(logger, log_level="warning"),
        reraise=True,
    )
    def _connect(self) -> Connection:
        """Establish a new Databricks connection."""
        try:
            logger.info("databricks_connecting", host=self.config.host)
            connection = sql.connect(
                server_hostname=self.config.host,
                http_path=self.config.http_path,
                access_token=self.config.token,
                _use_arrow_native_complex_types=self.config.enable_arrow,
            )
            logger.info("databricks_connection_established")
            return connection
        except sql.exc.ServerOperationError as exc:  # type: ignore[attr-defined]
            if "UNAUTHENTICATED" in str(exc).upper():
                raise DatabricksAuthenticationError(
                    "Authentication failed; verify token permissions"
                ) from exc
            raise DatabricksConnectionError(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - unexpected paths
            raise DatabricksConnectionError(str(exc)) from exc

    def get_connection(self) -> Connection:
        """Return a healthy connection, reconnect as needed."""
        with self._lock:
            if not self._is_alive():
                self.close()
                self._connection = self._connect()
            return self._connection

    @contextmanager
    def cursor(self) -> Generator[Cursor, None, None]:
        """Context manager returning a cursor."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()


_connection_provider: Optional[ConnectionProvider] = None


def get_connection_provider() -> ConnectionProvider:
    global _connection_provider
    if _connection_provider is None:
        _connection_provider = ConnectionProvider()
    return _connection_provider


@contextmanager
def get_cursor() -> Generator[Cursor, None, None]:
    """Convenience context manager for modules to use."""
    provider = get_connection_provider()
    with provider.cursor() as cursor:
        yield cursor

