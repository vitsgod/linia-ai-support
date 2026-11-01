from dataclasses import dataclass
from pathlib import Path

MAX_SECTION_LENGTH = 1600


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    document_id: str
    title: str
    section: str
    source: str
    content: str
    document_context: str

    @property
    def text(self) -> str:
        return "\n\n".join(part for part in (
            self.title, self.document_context, self.section, self.content
        ) if part)


def load_chunks(directory: Path) -> list[KnowledgeChunk]:
    paths = sorted(directory.glob("*.md"))
    if not paths:
        raise ValueError(f"Нет Markdown-инструкций в {directory}")
    chunks = []
    for path in paths:
        lines = path.read_text(encoding="utf-8-sig").strip().splitlines()
        if not lines or not lines[0].startswith("# ") or not lines[0][2:].strip():
            raise ValueError(f"{path.name}: нужен заголовок # с названием документа")
        title = lines[0][2:].strip()
        introduction = []
        sections = []
        heading = None
        body = []
        for line in lines[1:]:
            if line.startswith("# "):
                raise ValueError(f"{path.name}: в документе допускается один заголовок #")
            if line.startswith("## "):
                if heading is not None:
                    sections.append((heading, "\n".join(body).strip()))
                heading = line[3:].strip()
                body = []
            elif heading is None:
                introduction.append(line)
            else:
                body.append(line)
        if heading is not None:
            sections.append((heading, "\n".join(body).strip()))
        if not sections:
            raise ValueError(f"{path.name}: нужны разделы ##")
        seen = set()
        for index, (section, content) in enumerate(sections, start=1):
            if not section or not content:
                raise ValueError(f"{path.name}: пустое название или содержимое раздела")
            if section in seen:
                raise ValueError(f"{path.name}: повторяется раздел {section}")
            if len(content) > MAX_SECTION_LENGTH:
                raise ValueError(f"{path.name}: раздел {section} длиннее {MAX_SECTION_LENGTH} символов")
            seen.add(section)
            chunks.append(KnowledgeChunk(
                id=f"{path.stem}:{index:02d}", document_id=path.stem,
                title=title, section=section, source=path.name, content=content,
                document_context="\n".join(introduction).strip(),
            ))
    return chunks
