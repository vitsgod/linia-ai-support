import math

from backend.knowledge import KnowledgeChunk


def normalize_vector(vector: list[float]) -> list[float]:
    if not isinstance(vector, list) or not vector:
        raise ValueError("Вектор должен быть непустым списком чисел")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in vector):
        raise ValueError("Вектор содержит нечисловые или бесконечные значения")
    norm = math.hypot(*vector)
    if not norm or not math.isfinite(norm):
        raise ValueError("Вектор должен иметь конечную ненулевую длину")
    return [value / norm for value in vector]


def cosine_similarity(first: list[float], second: list[float]) -> float:
    if len(first) != len(second):
        raise ValueError("Размерности векторов не совпадают")
    a, b = normalize_vector(first), normalize_vector(second)
    score = math.fsum(x * y for x, y in zip(a, b))
    return max(-1.0, min(1.0, score))


def rank_chunks(chunks: list[KnowledgeChunk], embeddings: list[list[float]],
                query_vector: list[float], limit: int = 3) -> list[dict]:
    if not chunks or len(chunks) != len(embeddings):
        raise ValueError("Каждому фрагменту нужен один вектор, база не должна быть пустой")
    if type(limit) is not int or limit < 1:
        raise ValueError("Число результатов должно быть положительным целым")
    results = [
        {"chunk": chunk, "score": cosine_similarity(vector, query_vector)}
        for chunk, vector in zip(chunks, embeddings)
    ]
    return sorted(results, key=lambda result: (-result["score"], result["chunk"].id))[:limit]
