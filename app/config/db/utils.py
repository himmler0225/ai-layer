from sqlalchemy.inspection import inspect as sa_inspect


def model_to_dict(obj) -> dict:
    """Serialize a SQLAlchemy ORM instance's column attributes into a plain dict.

    Args:
        obj: A mapped SQLAlchemy model instance.

    Returns:
        dict: Column values keyed by attribute name; the `metadata_` attribute
        (used to avoid clashing with SQLAlchemy's reserved `metadata`) is renamed
        back to `metadata`.
    """
    data = {c.key: getattr(obj, c.key) for c in sa_inspect(obj).mapper.column_attrs}
    if "metadata_" in data:
        data["metadata"] = data.pop("metadata_")
    return data
