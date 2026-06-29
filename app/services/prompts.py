from __future__ import annotations

_VALUES: dict[str, str] = {}
_ready = False


def init_defaults(defaults: dict[str, str]) -> None:
    global _ready
    _VALUES.clear()
    _VALUES.update(defaults)
    _ready = True


def set_prompt(name: str, value: str) -> None:
    if not _ready:
        from app.config.defaults import build_prompt_defaults, load_schema

        init_defaults(build_prompt_defaults(load_schema()))
    _VALUES[name] = value


def __getattr__(name: str) -> str:
    if not _ready:
        from app.config.defaults import build_prompt_defaults, load_schema

        init_defaults(build_prompt_defaults(load_schema()))
    if name in _VALUES:
        return _VALUES[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
