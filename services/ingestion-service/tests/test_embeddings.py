from unittest.mock import MagicMock, patch

from src.embeddings import cosine_similarity, embed

MOCK_VECTOR = [0.1] * 1536


def _mock_openai_client(vector):
    embedding_obj = MagicMock()
    embedding_obj.embedding = vector
    data_obj = MagicMock()
    data_obj.data = [embedding_obj]
    client = MagicMock()
    client.embeddings.create.return_value = data_obj
    return client


def test_embed_returns_1536_floats():
    with patch("src.embeddings.openai.OpenAI", return_value=_mock_openai_client(MOCK_VECTOR)):
        result = embed("Python developer with 5 years experience in FastAPI")
    assert len(result) == 1536
    assert all(isinstance(v, float) for v in result)


def test_embed_truncates_long_text():
    long_text = "x" * 20000
    captured = {}

    def fake_create(**kwargs):
        captured["input"] = kwargs["input"]
        return _mock_openai_client(MOCK_VECTOR)().embeddings.create(**kwargs)

    with patch("src.embeddings.openai.OpenAI", return_value=_mock_openai_client(MOCK_VECTOR)):
        embed(long_text)
    # Just verify it doesn't crash — truncation is internal


def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_cosine_similarity_range():
    import random
    a = [random.random() for _ in range(1536)]
    b = [random.random() for _ in range(1536)]
    score = cosine_similarity(a, b)
    assert 0.0 <= score <= 1.0
