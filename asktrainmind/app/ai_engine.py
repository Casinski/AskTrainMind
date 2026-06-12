from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from html import escape
from typing import TYPE_CHECKING

from asktrainmind.app.comparison import (
    ComparisonMatrix,
    build_comparison_matrix,
    matrix_to_html_table,
    matrix_to_narrative_html,
    matrix_to_plain_text,
    records_info_plain_text,
)
from asktrainmind.app.config import AIConfig
from asktrainmind.app.excel_model import FunctionRecord
from asktrainmind.app.image_extractor import WorkbookImage
from asktrainmind.app.reasoning import (
    analyze_records,
    build_local_narrative,
    build_overall_discussion,
    render_detailed_html,
)

if TYPE_CHECKING:
    from asktrainmind.app.document_extractor import ExtractedDocument

INFO_MARKER = "=== INFO ==="
DIFF_MARKER = "=== DIFFERENZE ==="


@dataclass
class AnalysisOutput:
    info_text: str
    differences_text: str
    diff_table_html: str = ""
    differences_detail_html: str = ""
    images: list[WorkbookImage] = field(default_factory=list)
    banner: str | None = None


class LLMProvider(ABC):
    @abstractmethod
    def analyze(
        self,
        records: list[FunctionRecord],
        matrix: ComparisonMatrix,
        images: list[WorkbookImage] | None = None,
        documents: list["ExtractedDocument"] | None = None,
        kb_entries: list[dict] | None = None,
    ) -> "AnalysisOutput | str":
        raise NotImplementedError


def _supports_vision(model_name: str) -> bool:
    model = (model_name or "").lower()
    return "gpt-4o" in model


def _split_sections(text: str) -> tuple[str, str]:
    if INFO_MARKER in text and DIFF_MARKER in text:
        _, tail = text.split(INFO_MARKER, 1)
        info_part, diff_part = tail.split(DIFF_MARKER, 1)
        return info_part.strip(), diff_part.strip()
    return "", text.strip()


def _build_prompt(
    records: list[FunctionRecord],
    matrix: ComparisonMatrix,
    documents: list["ExtractedDocument"] | None = None,
    kb_entries: list[dict] | None = None,
) -> str:
    doc_section = ""
    if documents:
        doc_lines = ["\n\nContenuto documenti collegati (estratto per pagina di riferimento):"]
        for doc in documents:
            if doc.pages:
                doc_lines.append(f"\n[Documento: {doc.source_url}]")
                for page in doc.pages[:5]:  # limit to first 5 pages to keep prompt size manageable
                    snippet = page.text[:600].strip()
                    if snippet:
                        doc_lines.append(f"  Pagina {page.page_number}: {snippet}")
        doc_section = "\n".join(doc_lines)

    kb_section = ""
    if kb_entries:
        kb_lines = ["\n\nNote utente (Knowledge Base) — usale come contesto aggiuntivo:"]
        for entry in kb_entries:
            title = entry.get("title") or "Nota"
            text = entry.get("text", "")
            kb_lines.append(f"  [{title}]: {text}")
        kb_section = "\n".join(kb_lines)

    return (
        "Sei AskTrainMind. Produci due sezioni distinte e ben strutturate in italiano.\n"
        f"Formato obbligatorio:\n{INFO_MARKER}\n...\n{DIFF_MARKER}\n...\n\n"
        "INFO: sintesi della funzione/ID selezionata per tutte le configurazioni.\n"
        "DIFFERENZE: spiega chiaramente cosa resta uguale e cosa cambia tra configurazioni, "
        "citando DOC ID e dettagli.\n\n"
        f"{records_info_plain_text(records)}\n\n{matrix_to_plain_text(matrix)}"
        f"{doc_section}{kb_section}"
    )


def _documents_html(documents: list["ExtractedDocument"]) -> str:
    """Build HTML rendering of extracted document page text for offline fallback."""
    if not documents:
        return ""
    lines = ["<div class='doc-extracts'><p><b>Testo documenti collegati (estratto):</b></p>"]
    for doc in documents:
        if doc.status not in ("ok", "partial_error") or not doc.pages:
            note = escape(doc.message or doc.status)
            lines.append(f"<p class='doc-note'>📄 {escape(doc.source_url[:80])}: {note}</p>")
            continue
        lines.append(f"<p><b>📄 Documento:</b> {escape(doc.source_url[:80])}</p>")
        lines.append("<ul class='doc-pages'>")
        for page in doc.pages[:5]:
            snippet = page.text[:400].strip()
            if snippet:
                lines.append(
                    f"<li><b>Pag. {page.page_number}:</b> {escape(snippet)}</li>"
                )
        lines.append("</ul>")
    lines.append("</div>")
    return "\n".join(lines)


def _kb_entries_html(kb_entries: list[dict]) -> str:
    """Render matching KB entries as an HTML block."""
    if not kb_entries:
        return ""
    lines = ["<div class='kb-block'><p><b>📝 Note utente / Knowledge base:</b></p><ul>"]
    for entry in kb_entries:
        title = escape(entry.get("title") or "Nota")
        text = escape(entry.get("text", ""))
        created = entry.get("created_at", "")[:10]
        lines.append(f"<li><b>{title}</b> <span class='kb-date'>({created})</span>: {text}</li>")
    lines.append("</ul></div>")
    return "\n".join(lines)


def _fallback_info_html(
    records: list[FunctionRecord],
    matrix: ComparisonMatrix,
    documents: list["ExtractedDocument"] | None = None,
    kb_entries: list[dict] | None = None,
) -> str:
    if not records:
        return "<p>Nessun record selezionato.</p>"
    lines = ["<p><b>Sintesi deterministica (offline):</b></p>"]
    for record in records:
        lines.append(f"<h4>{escape(record.id)} — {escape(record.funzione)}</h4>")
        if not record.documents:
            lines.append("<p>Nessun documento associato.</p>")
            continue
        lines.append("<ul>")
        for doc in record.documents:
            lines.append(f"<li><b>DOC {escape(doc.doc_id)}</b> — {escape(doc.info_doc)}</li>")
        lines.append("</ul>")
    lines.append(f"<p>Configurazioni rilevate: {escape(', '.join(matrix.config_names) or 'nessuna')}.</p>")
    if documents:
        lines.append(_documents_html(documents))
    if kb_entries:
        lines.append(_kb_entries_html(kb_entries))
    return "\n".join(lines)


def _fallback_diff_html(
    matrix: ComparisonMatrix,
    documents: list["ExtractedDocument"] | None = None,
) -> str:
    rows = [matrix_to_narrative_html(matrix)]
    if documents:
        rows.append(_documents_html(documents))
    return "\n".join(rows)


class NullProvider(LLMProvider):
    def analyze(
        self,
        records: list[FunctionRecord],
        matrix: ComparisonMatrix,
        images: list[WorkbookImage] | None = None,
        documents: list["ExtractedDocument"] | None = None,
        kb_entries: list[dict] | None = None,
    ) -> AnalysisOutput:
        local_analysis = analyze_records(records, matrix)
        discourse_parts = [build_overall_discussion(local_analysis)]
        if documents:
            discourse_parts.append(_documents_html(documents))
        differences_text = "\n".join(discourse_parts)
        detail_parts = [render_detailed_html(local_analysis), matrix_to_html_table(matrix)]
        if documents:
            detail_parts.append(_documents_html(documents))
        differences_detail_html = "\n".join(detail_parts)
        return AnalysisOutput(
            info_text=_fallback_info_html(records, matrix, documents, kb_entries),
            differences_text=differences_text,
            diff_table_html=matrix_to_html_table(matrix),
            differences_detail_html=differences_detail_html,
            images=list(images or []),
            banner="Modalità locale/offline: analisi generata dai dati del file Excel.",
        )


class OpenAIProvider(LLMProvider):
    def __init__(self, config: AIConfig):
        self.config = config

    def analyze(
        self,
        records: list[FunctionRecord],
        matrix: ComparisonMatrix,
        images: list[WorkbookImage] | None = None,
        documents: list["ExtractedDocument"] | None = None,
        kb_entries: list[dict] | None = None,
    ) -> AnalysisOutput:
        from openai import OpenAI

        model = self.config.model or "gpt-4o-mini"
        prompt = _build_prompt(records, matrix, documents, kb_entries)
        content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        if self.config.vision_enabled and _supports_vision(model):
            for image in images or []:
                payload = base64.b64encode(image.data).decode("ascii")
                content.append(
                    {"type": "image_url", "image_url": {"url": f"data:{image.mime_type};base64,{payload}"}}
                )
            # Also attach images extracted from documents
            for doc in documents or []:
                for doc_img in doc.images[:2]:  # limit to 2 images per doc to control token usage
                    payload = base64.b64encode(doc_img.data).decode("ascii")
                    content.append(
                        {"type": "image_url", "image_url": {"url": f"data:{doc_img.mime_type};base64,{payload}"}}
                    )

        client = OpenAI(api_key=self.config.api_key)
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            temperature=0.2,
        )
        text = completion.choices[0].message.content or ""
        info_text, differences_text = _split_sections(text)
        if not info_text:
            info_text = _fallback_info_html(records, matrix, documents, kb_entries)
        if not differences_text:
            differences_text = _fallback_diff_html(matrix, documents)
        if kb_entries:
            info_text = info_text + "\n" + _kb_entries_html(kb_entries)
        local_analysis = analyze_records(records, matrix)
        detail_parts = [render_detailed_html(local_analysis), matrix_to_html_table(matrix)]
        if documents:
            detail_parts.append(_documents_html(documents))
        differences_detail_html = "\n".join(detail_parts)
        return AnalysisOutput(
            info_text=info_text,
            differences_text=differences_text,
            diff_table_html=matrix_to_html_table(matrix),
            differences_detail_html=differences_detail_html,
            images=list(images or []),
        )


class AzureOpenAIProvider(LLMProvider):
    def __init__(self, config: AIConfig):
        self.config = config

    def analyze(
        self,
        records: list[FunctionRecord],
        matrix: ComparisonMatrix,
        images: list[WorkbookImage] | None = None,
        documents: list["ExtractedDocument"] | None = None,
        kb_entries: list[dict] | None = None,
    ) -> AnalysisOutput:
        from openai import AzureOpenAI

        model = self.config.deployment or self.config.model
        prompt = _build_prompt(records, matrix, documents, kb_entries)
        content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        if self.config.vision_enabled and _supports_vision(model):
            for image in images or []:
                payload = base64.b64encode(image.data).decode("ascii")
                content.append(
                    {"type": "image_url", "image_url": {"url": f"data:{image.mime_type};base64,{payload}"}}
                )
            for doc in documents or []:
                for doc_img in doc.images[:2]:
                    payload = base64.b64encode(doc_img.data).decode("ascii")
                    content.append(
                        {"type": "image_url", "image_url": {"url": f"data:{doc_img.mime_type};base64,{payload}"}}
                    )

        client = AzureOpenAI(
            api_key=self.config.api_key,
            api_version="2024-10-01-preview",
            azure_endpoint=self.config.endpoint,
        )
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            temperature=0.2,
        )
        text = completion.choices[0].message.content or ""
        info_text, differences_text = _split_sections(text)
        if not info_text:
            info_text = _fallback_info_html(records, matrix, documents, kb_entries)
        if not differences_text:
            differences_text = _fallback_diff_html(matrix, documents)
        if kb_entries:
            info_text = info_text + "\n" + _kb_entries_html(kb_entries)
        local_analysis = analyze_records(records, matrix)
        detail_parts = [render_detailed_html(local_analysis), matrix_to_html_table(matrix)]
        if documents:
            detail_parts.append(_documents_html(documents))
        differences_detail_html = "\n".join(detail_parts)
        return AnalysisOutput(
            info_text=info_text,
            differences_text=differences_text,
            diff_table_html=matrix_to_html_table(matrix),
            differences_detail_html=differences_detail_html,
            images=list(images or []),
        )


class AnalysisEngine:
    def __init__(self, config: AIConfig):
        self.config = config

    def _build_provider(self) -> LLMProvider:
        provider = self.config.provider.lower().strip()
        if provider == "openai" and self.config.api_key:
            return OpenAIProvider(self.config)
        if provider == "azure" and self.config.api_key and self.config.endpoint:
            return AzureOpenAIProvider(self.config)
        return NullProvider()

    def analyze(
        self,
        records: list[FunctionRecord],
        images: list[WorkbookImage] | None = None,
        documents: list["ExtractedDocument"] | None = None,
        kb_entries: list[dict] | None = None,
    ) -> AnalysisOutput:
        matrix = build_comparison_matrix(records)
        provider = self._build_provider()
        try:
            raw_output = provider.analyze(
                records, matrix, images=images, documents=documents, kb_entries=kb_entries
            )
        except Exception:
            raw_output = NullProvider().analyze(
                records, matrix, images=images, documents=documents, kb_entries=kb_entries
            )
        if isinstance(raw_output, str):
            info_text, differences_text = _split_sections(raw_output)
            if not info_text:
                info_text = _fallback_info_html(records, matrix, documents, kb_entries)
            if not differences_text:
                differences_text = _fallback_diff_html(matrix, documents)
            if kb_entries:
                info_text = info_text + "\n" + _kb_entries_html(kb_entries)
            local_analysis = analyze_records(records, matrix)
            detail_parts = [render_detailed_html(local_analysis), matrix_to_html_table(matrix)]
            output = AnalysisOutput(
                info_text=info_text,
                differences_text=differences_text,
                diff_table_html=matrix_to_html_table(matrix),
                differences_detail_html="\n".join(detail_parts),
                images=list(images or []),
            )
        else:
            output = raw_output
        if not output.diff_table_html:
            output.diff_table_html = matrix_to_html_table(matrix)
        if not output.differences_detail_html:
            output.differences_detail_html = output.diff_table_html
        return output

