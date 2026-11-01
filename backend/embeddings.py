import json
import os
from http.client import HTTPException
from urllib import error, request

from backend.semantic_search import normalize_vector

EMBEDDING_MODEL = "qwen3-embedding:0.6b"
EMBEDDING_DIMENSIONS = 1024
QUERY_INSTRUCTION = "Given a question about home internet connectivity, retrieve relevant technical support instructions."


class EmbeddingError(RuntimeError):
    pass


def _embed(texts: list[str]) -> list[list[float]]:
    if not isinstance(texts, list) or not 1 <= len(texts) <= 16:
        raise ValueError("Нужно от 1 до 16 текстов в одном запросе")
    if any(not isinstance(text, str) or not text.strip() or len(text) > 8000 for text in texts):
        raise ValueError("Тексты должны быть непустыми строками длиной до 8000 символов")
    payload = {
        "model": EMBEDDING_MODEL, "input": texts, "truncate": False,
        "keep_alive": "5m", "options": {"num_ctx": 4096},
    }
    outgoing = request.Request(
        os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/') + '/api/embed', method="POST",
        data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(outgoing, timeout=120) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
    except error.HTTPError as exc:
        exc.close()
        raise EmbeddingError("Эмбеддинги недоступны: проверьте наличие embedding-модели в Ollama.") from None
    except (error.URLError, OSError, HTTPException):
        raise EmbeddingError("Не удалось получить эмбеддинги от локальной Ollama. Проверьте её запуск.") from None
    if len(raw) > 2 * 1024 * 1024:
        raise EmbeddingError("Ответ с эмбеддингами превышает допустимый размер")
    try:
        data = json.loads(raw)
        vectors = data.get("embeddings") if isinstance(data, dict) else None
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise ValueError("Неверное число векторов")
        result = []
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != EMBEDDING_DIMENSIONS:
                raise ValueError("Неверная размерность")
            result.append(normalize_vector(vector))
        return result
    except (ValueError, UnicodeError):
        raise EmbeddingError("Модель вернула некорректные эмбеддинги") from None


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _embed(texts)


def embed_query(text: str) -> list[float]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Нужен непустой текст вопроса")
    return _embed([f"Instruct: {QUERY_INSTRUCTION}\nQuery: {text.strip()}"])[0]
