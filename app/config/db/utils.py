from __future__ import annotations
from sqlalchemy.inspection import inspect as sa_inspect

def model_to_dict(obj) -> dict:
    """Model to dict.

    Args:
        obj: (Any) Tham số `obj`.

    Returns:
        (dict) Kết quả trả về."""
    data = {c.key: getattr(obj, c.key) for c in sa_inspect(obj).mapper.column_attrs}
    if 'metadata_' in data:
        data['metadata'] = data.pop('metadata_')
    return data
