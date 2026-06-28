from __future__ import annotations

"""Helper chuyển SQLAlchemy model → dict."""


from sqlalchemy.inspection import inspect as sa_inspect


def model_to_dict(obj) -> dict:
    """Chuyển ORM row sang dict (metadata_ → metadata)."""
    data = {c.key: getattr(obj, c.key) for c in sa_inspect(obj).mapper.column_attrs}
    if "metadata_" in data:
        data["metadata"] = data.pop("metadata_")
    return data
