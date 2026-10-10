"""Kennis voor de helpassistent: help-secties per rol en vaste kennisbestanden."""

import re
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "kennis"

# Vaste kennis voor iedereen en, apart, voor de superadmin; (id, titel) = bestand kennis/<id>.md.
GENERAL_KNOWLEDGE = (
    ("functies", "Functies en regels"),
    ("techniek", "Techniek, privacy en beveiliging"),
)
PLATFORM_KNOWLEDGE = (("platform-techniek", "Platformbeheer en techniek"),)


@dataclass(frozen=True)
class KnowledgeChunk:
    """Een deel van de kennis; `id` is wat de assistent als bron noemt."""

    id: str
    title: str
    text: str
    url: str | None = None


class _TextExtractor(HTMLParser):
    BLOCKS = {"p", "ul", "ol", "h1", "h2", "h3", "h4", "div", "section", "article", "br"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "li":
            self.parts.append("\n- ")
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(html: str) -> str:
    """Leesbare platte tekst uit een help-fragment: lijsten als '- ', zonder tags."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line and line != "-")


@lru_cache
def read_knowledge(knowledge_id: str) -> str:
    return (KNOWLEDGE_DIR / f"{knowledge_id}.md").read_text(encoding="utf-8").strip()


def fixed_knowledge(is_superadmin: bool) -> list[KnowledgeChunk]:
    items = GENERAL_KNOWLEDGE + (PLATFORM_KNOWLEDGE if is_superadmin else ())
    return [KnowledgeChunk(id_, title, read_knowledge(id_)) for id_, title in items]
