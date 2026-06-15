from __future__ import annotations

import json
import re
from typing import Iterable

from langchain_core.documents import Document

from .config import Settings


class GuardrailViolation(ValueError):
    """Raised when a configured guardrail blocks a request."""


FORBIDDEN_SQL_TOKENS = (
    " insert ",
    " update ",
    " delete ",
    " drop ",
    " alter ",
    " attach ",
    " detach ",
    " pragma ",
    " vacuum ",
    " create ",
    " replace ",
    " truncate ",
)


def validate_question(question: str, settings: Settings) -> str:
    cleaned = question.strip()
    if len(cleaned) < settings.min_question_chars:
        raise GuardrailViolation(
            (
                "Sua pergunta esta muito curta para a Maria responder com qualidade. "
                f"Use pelo menos {settings.min_question_chars} caracteres. "
                "Exemplo: 'quais produtos mais venderam hoje?'."
            )
        )
    if len(cleaned) > settings.max_question_chars:
        raise GuardrailViolation(
            (
                "Sua pergunta ficou grande demais para uma entrada unica. "
                f"O limite atual e de {settings.max_question_chars} caracteres. "
                "Tente dividir em duas perguntas menores."
            )
        )
    for pattern in settings.blocked_patterns:
        if re.search(pattern, cleaned):
            raise GuardrailViolation(
                (
                    "Sua mensagem foi bloqueada por uma regra de seguranca do agente. "
                    "Se sua intencao for valida, reformule a pergunta de forma mais objetiva "
                    "e sem comandos tecnicos."
                )
            )
    return cleaned


def validate_sql_query(query: str, settings: Settings) -> str:
    normalized = f" {query.strip().lower()} "
    if not normalized.strip():
        raise GuardrailViolation(
            "A consulta SQL veio vazia. Informe uma consulta de leitura para continuar."
        )

    if ";" in query.strip().rstrip(";"):
        raise GuardrailViolation(
            "A Maria aceita apenas uma consulta SQL por vez. Remova comandos extras e tente novamente."
        )

    if settings.allow_only_select_sql and not normalized.lstrip().startswith("select "):
        raise GuardrailViolation(
            "Por seguranca, a Maria aceita apenas consultas SQL de leitura usando SELECT."
        )

    for token in FORBIDDEN_SQL_TOKENS:
        if token in normalized:
            raise GuardrailViolation(
                (
                    "Sua consulta SQL contem uma instrucao bloqueada por seguranca. "
                    "Use apenas consultas de leitura para analisar os dados."
                )
            )

    return query.strip().rstrip(";")


def trim_documents(documents: Iterable[Document], settings: Settings) -> list[Document]:
    total_chars = 0
    selected: list[Document] = []
    for document in documents:
        new_total = total_chars + len(document.page_content)
        if new_total > settings.max_context_chars and selected:
            break
        selected.append(document)
        total_chars = new_total
    return selected


def ensure_minimum_context(documents: list[Document], settings: Settings) -> list[Document]:
    if len(documents) < settings.min_retrieved_documents:
        raise GuardrailViolation(
            (
                "A Maria nao encontrou contexto suficiente para responder com seguranca. "
                "Tente ser mais especifico, mencionar periodo, setor, produto ou tipo de indicador."
            )
        )
    return documents


def mask_output(text: str, settings: Settings) -> str:
    masked = text

    if settings.mask_emails:
        masked = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            "[REDACTED_EMAIL]",
            masked,
        )

    if settings.mask_phones:
        masked = re.sub(
            r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2}\)?[\s.-]?)?\d{4,5}[\s.-]?\d{4}(?!\d)",
            "[REDACTED_PHONE]",
            masked,
        )

    if settings.mask_cpfs:
        masked = re.sub(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "[REDACTED_CPF]", masked)

    return masked


def format_sources(documents: list[Document]) -> str:
    payload = []
    for document in documents:
        payload.append(
            {
                "table": document.metadata.get("table"),
                "record_id": document.metadata.get("record_id"),
                "source": document.metadata.get("source"),
                "title": document.metadata.get("title"),
            }
        )
    return json.dumps(payload, ensure_ascii=True, indent=2)
