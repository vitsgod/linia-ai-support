"""Preview knowledge chunks without a database or model call."""

from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.knowledge import load_chunks


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    chunks = load_chunks(ROOT / "knowledge")
    counts = Counter(chunk.source for chunk in chunks)
    output = [
        "# Предпросмотр базы знаний", "",
        "Учебные материалы демонстрационного сервиса. Это подготовка текстов: "
        "эмбеддинги, смысловой поиск и передача найденного контекста модели ещё не подключены.", "",
        f"Документов: {len(counts)}. Фрагментов: {len(chunks)}.", "",
    ]
    for chunk in chunks:
        output.extend([
            f"## {chunk.id} · {chunk.title}", "",
            f"Источник: [{chunk.source}](../knowledge/{chunk.source}). Раздел: **{chunk.section}**.", "",
            chunk.document_context, "", chunk.content, "",
        ])
    destination = ROOT / "docs" / "knowledge-preview.md"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text("\n".join(output), encoding="utf-8")
    print(f"Документов: {len(counts)}; фрагментов: {len(chunks)}")
    for source, count in counts.items():
        print(f"  {source}: {count}")
    print(f"Предпросмотр: {destination}")


if __name__ == "__main__":
    main()
