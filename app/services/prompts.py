_VALUES: dict[str, str] = {}
_ready = False


def init_defaults(defaults: dict[str, str]) -> None:
    """Load the default prompt values, replacing any previously stored ones.

    Args:
        defaults: Mapping of prompt name to its default text, as built by
            `app.config.defaults.build_prompt_defaults`.
    """
    global _ready
    _VALUES.clear()
    _VALUES.update(defaults)
    _ready = True


def set_prompt(name: str, value: str) -> None:
    """Override a prompt's value at runtime (e.g. from an admin/config UI).

    Lazily initializes the defaults from the prompt schema if this module
    hasn't been initialized yet.

    Args:
        name: Name of the prompt to set (as an attribute on this module).
        value: New prompt text.
    """
    if not _ready:
        from app.config.defaults import build_prompt_defaults, load_schema

        init_defaults(build_prompt_defaults(load_schema()))
    _VALUES[name] = value


def __getattr__(name: str) -> str:
    """Module-level `__getattr__` that resolves prompt names dynamically.

    Lets callers do `prompts.SOME_PROMPT` without every prompt name being a
    real module attribute; lazily initializes defaults on first access.

    Args:
        name: Attribute name being accessed, expected to be a prompt name.

    Returns:
        The current value of the requested prompt.

    Raises:
        AttributeError: If `name` is not a known prompt.
    """
    if not _ready:
        from app.config.defaults import build_prompt_defaults, load_schema

        init_defaults(build_prompt_defaults(load_schema()))
    if name in _VALUES:
        return _VALUES[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
