_VALUES: dict[str, str] = {}
_ready = False


def init_defaults(defaults: dict[str, str]) -> None:
    """Khởi tạo defaults.

    Args:
        defaults: (dict[str, str]) Tham số `defaults`.

    Returns:
        (None) Kết quả trả về."""
    global _ready
    _VALUES.clear()
    _VALUES.update(defaults)
    _ready = True


def set_prompt(name: str, value: str) -> None:
    """Set prompt.

    Args:
        name: (str) Tham số `name`.
        value: (str) Tham số `value`.

    Returns:
        (None) Kết quả trả về."""
    if not _ready:
        from app.config.defaults import build_prompt_defaults, load_schema

        init_defaults(build_prompt_defaults(load_schema()))
    _VALUES[name] = value


def __getattr__(name: str) -> str:
    """Ủy quyền đọc attribute khi không tìm thấy trên module.

    Args:
        name: (str) Tham số `name`.

    Returns:
        (str) Kết quả trả về."""
    if not _ready:
        from app.config.defaults import build_prompt_defaults, load_schema

        init_defaults(build_prompt_defaults(load_schema()))
    if name in _VALUES:
        return _VALUES[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
