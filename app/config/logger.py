import json
import logging
import logging.handlers
import re
from datetime import datetime
from pathlib import Path
from typing import Any

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"
_BLUE = "\x1b[34m"
_LEVEL_COLOR = {
    "DEBUG": "\x1b[36m",
    "INFO": "\x1b[32m",
    "WARNING": "\x1b[33m",
    "ERROR": "\x1b[31m",
    "CRITICAL": "\x1b[35m\x1b[1m",
}

_EMOJI_RE = re.compile(
    "[\U0001f300-\U0001faff\u2600-\u27bf\ufe0f]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    """Remove emoji characters from a string so log output stays emoji-free.

    Args:
        text: Text to sanitize.

    Returns:
        str: The text with emoji removed and surrounding whitespace stripped.
    """
    return _EMOJI_RE.sub("", text).strip()


def _display_logger(name: str, root: str) -> str:
    """Shorten a logger name for display: strip the app's root prefix and collapse
    any "uvicorn*" logger name to "server".

    Args:
        name: Full logger name (e.g. "ai_layer.config.db.session").
        root: The application's root logger name (e.g. "ai_layer").

    Returns:
        str: The shortened display name.
    """
    prefix = f"{root}."
    if name.startswith(prefix):
        return name[len(prefix) :]
    if name.startswith("uvicorn"):
        return "server"
    return name


class _ColorFormatter(logging.Formatter):
    """Console log formatter: colorizes level/logger name and strips emoji from messages."""

    root_name: str = "ai_layer"

    def format(self, record: logging.LogRecord) -> str:
        """Render a log record as a single colorized, human-readable console line.

        Args:
            record: The log record to format.

        Returns:
            str: The formatted line, with an appended traceback if `exc_info` is set.
        """
        ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        color = _LEVEL_COLOR.get(record.levelname, "\x1b[37m")
        short = _display_logger(record.name, self.root_name)
        msg = _strip_emoji(record.getMessage())
        rendered = (
            f"{_DIM}{ts}{_RESET}  "
            f"{color}{_BOLD}{record.levelname:<8}{_RESET}  "
            f"{_BLUE}{short:<24}{_RESET}  "
            f"{color}{msg}{_RESET}"
        )
        if record.exc_info:
            rendered = f"{rendered}\n{self.formatException(record.exc_info)}"
        return rendered


class _JSONFormatter(logging.Formatter):
    """Log formatter that renders each record as a single-line JSON object (for file logs)."""

    def format(self, record: logging.LogRecord) -> str:
        """Render a log record as a single-line JSON object.

        Args:
            record: The log record to format.

        Returns:
            str: A JSON string with timestamp, level, logger, message, module,
            function, line, and (if present) exception traceback.
        """
        data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _strip_emoji(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


class Logger:
    """Central logging setup: configures console + rotating file handlers under one root logger."""

    _root: str = "ai_layer"
    _configured: bool = False

    @classmethod
    def setup(
        cls,
        level: str = "INFO",
        log_dir: str = "logs",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> None:
        """Configure the root application logger with console, app-log, and error-log handlers.

        Idempotent: does nothing if already configured. Sets up a colorized
        console handler (DEBUG+), a rotating JSON app.log (DEBUG+), and a
        rotating JSON error.log (ERROR+), then syncs uvicorn's loggers to match.

        Args:
            level: Root logger level name (e.g. "INFO", "DEBUG").
            log_dir: Directory to create/write log files into.
            max_bytes: Max size in bytes before a log file rotates.
            backup_count: Number of rotated backup files to keep.
        """
        if cls._configured:
            return
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        root = logging.getLogger(cls._root)
        root.setLevel(getattr(logging, level.upper(), logging.INFO))
        root.handlers.clear()
        root.propagate = False
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        formatter = _ColorFormatter()
        formatter.root_name = cls._root
        console.setFormatter(formatter)
        root.addHandler(console)
        app_file = logging.handlers.RotatingFileHandler(
            log_path / "app.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        app_file.setLevel(logging.DEBUG)
        app_file.setFormatter(_JSONFormatter())
        root.addHandler(app_file)
        err_file = logging.handlers.RotatingFileHandler(
            log_path / "error.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        err_file.setLevel(logging.ERROR)
        err_file.setFormatter(_JSONFormatter())
        root.addHandler(err_file)
        cls._configure_uvicorn(level)
        cls._configured = True

    @classmethod
    def sync_uvicorn(cls, level: str = "INFO") -> None:
        """Re-apply the app's console formatter/level to uvicorn's loggers.

        Args:
            level: Log level name to apply to uvicorn's loggers.
        """
        cls._configure_uvicorn(level)

    @classmethod
    def _configure_uvicorn(cls, level: str) -> None:
        """Attach the app's colorized console handler to uvicorn's loggers so their
        output matches the rest of the app; the access log is capped at WARNING.

        Args:
            level: Log level name to apply to "uvicorn" and "uvicorn.error".
        """
        log_level = getattr(logging, level.upper(), logging.INFO)
        formatter = _ColorFormatter()
        formatter.root_name = cls._root
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        for name in ("uvicorn", "uvicorn.error"):
            uv_log = logging.getLogger(name)
            uv_log.handlers.clear()
            uv_log.propagate = False
            uv_log.addHandler(handler)
            uv_log.setLevel(log_level)
        access_log = logging.getLogger("uvicorn.access")
        access_log.handlers.clear()
        access_log.propagate = False
        access_log.addHandler(handler)
        access_log.setLevel(logging.WARNING)

    @classmethod
    def get(cls, name: str) -> logging.Logger:
        """Get a logger namespaced under the app's root logger.

        Args:
            name: Module name (e.g. `__name__`); an "app." prefix is stripped.

        Returns:
            logging.Logger: Logger named `{root}.{name}`.
        """
        short = name.removeprefix("app.")
        return logging.getLogger(f"{cls._root}.{short}")


def log_event(component: str, event: str, **fields: Any) -> str:
    """Format server log lines: ``[component] event key=value``.

    Convention (English-only):
    - ``component``: snake_case area (``agent``, ``worker``, ``db``, …)
    - ``event``: short verb phrase (``request failed``, ``catalog loaded``)
    - ``fields``: structured context as ``key=value`` pairs
    """
    if not fields:
        return f"[{component}] {event}"
    tail = " ".join(f"{key}={value}" for key, value in fields.items())
    return f"[{component}] {event} {tail}"
