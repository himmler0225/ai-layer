from app.repositories.pgvector import vector_literal


def test_vector_literal_format():
    assert vector_literal([1.0, 0.5, 0.0]) == "[1.00000000,0.50000000,0.00000000]"
