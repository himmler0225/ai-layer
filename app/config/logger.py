import json
import logging
import logging.handlers
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

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
    "["
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\uFE0F"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    """(Nội bộ) Strip emoji.

    Args:
        text: (str) Tham số `text`.

    Returns:
        (str) Kết quả trả về."""
    return _EMOJI_RE.sub("", text).strip()


def _display_logger(name: str, root: str) -> str:
    """(Nội bộ) Display logger.

    Args:
        name: (str) Tham số `name`.
        root: (str) Tham số `root`.

    Returns:
        (str) Kết quả trả về."""
    prefix = f"{root}."
    if name.startswith(prefix):
        return name[len(prefix) :]
    if name.startswith("uvicorn"):
        return "server"
    return name


class _ColorFormatter(logging.Formatter):
    """    Lớp `_ColorFormatter` (kế thừa logging.Formatter)."""
    root_name: str = "ai_layer"

    def format(self, record: logging.LogRecord) -> str:
        """Định dạng `format`.

    Args:
        record: (logging.LogRecord) Tham số `record`.

    Returns:
        (str) Kết quả trả về."""
        ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        color = _LEVEL_COLOR.get(record.levelname, "\x1b[37m")
        short = _display_logger(record.name, self.root_name)
        msg = _strip_emoji(record.getMessage())
        return (
            f"{_DIM}{ts}{_RESET}  "
            f"{color}{_BOLD}{record.levelname:<8}{_RESET}  "
            f"{_BLUE}{short:<24}{_RESET}  "
            f"{color}{msg}{_RESET}"
        )


class _JSONFormatter(logging.Formatter):
    """    Lớp `_JSONFormatter` (kế thừa logging.Formatter)."""
    def format(self, record: logging.LogRecord) -> str:
        """Định dạng `format`.

    Args:
        record: (logging.LogRecord) Tham số `record`.

    Returns:
        (str) Kết quả trả về."""
        data: Dict[str, Any] = {
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
    """    Lớp `Logger` (kế thừa object)."""
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
        """Cấu hình `setup`.

    Args:
        level: (str, mặc định 'INFO') Tham số `level`.
        log_dir: (str, mặc định 'logs') Tham số `log_dir`.
        max_bytes: (int, mặc định 10 * 1024 * 1024) Tham số `max_bytes`.
        backup_count: (int, mặc định 5) Tham số `backup_count`.

    Returns:
        (None) Kết quả trả về."""
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
        """Đồng bộ uvicorn.

    Args:
        level: (str, mặc định 'INFO') Tham số `level`.

    Returns:
        (None) Kết quả trả về."""
        cls._configure_uvicorn(level)

    @classmethod
    def _configure_uvicorn(cls, level: str) -> None:
        """(Nội bộ) Cấu hình uvicorn.

    Args:
        level: (str) Tham số `level`.

    Returns:
        (None) Kết quả trả về."""
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
        """Lấy `get`.

    Args:
        name: (str) Tham số `name`.

    Returns:
        (logging.Logger) Kết quả trả về."""
        short = name.removeprefix("app.")
        return logging.getLogger(f"{cls._root}.{short}")
