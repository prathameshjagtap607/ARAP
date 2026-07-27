import openai

_MODEL = "text-embedding-3-small"


def embed_texts(texts: list[str]) -> list[list[float]]:
    client = openai.OpenAI()
    response = client.embeddings.create(model=_MODEL, input=texts)
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
