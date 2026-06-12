from __future__ import annotations

from html import escape

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QImage, QTextDocument
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from asktrainmind.app.ai_engine import AnalysisOutput
from asktrainmind.app.excel_model import FunctionRecord
from asktrainmind.app.image_extractor import WorkbookImage
from asktrainmind.app.link_utils import is_openable_url
from asktrainmind.app.page_reference import get_document_reference


class ResultsView(QWidget):
    def __init__(
        self,
        records: list[FunctionRecord],
        analysis: AnalysisOutput,
        images: list[WorkbookImage] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Risultati")

        render_images = list(images if images is not None else analysis.images)
        layout = QVBoxLayout(self)

        if analysis.banner:
            banner = QLabel(analysis.banner)
            banner.setObjectName("banner")
            banner.setWordWrap(True)
            layout.addWidget(banner)

        link_header = QLabel("LINK")
        link_header.setObjectName("sectionTitle")
        link_box = QTextBrowser()
        link_box.setOpenLinks(False)
        link_box.setHtml(self._build_links(records))
        link_box.anchorClicked.connect(self._open_url)

        diff_header = QLabel("DIFFERENZE")
        diff_header.setObjectName("sectionTitleImportant")

        # Visible overall discourse
        diff_box = QTextBrowser()
        diff_box.setOpenLinks(False)
        diff_box.setHtml(self._section_html(diff_box, analysis.differences_text, render_images, "diff"))
        diff_box.anchorClicked.connect(self._open_url)

        # Collapsible "Analisi dettagliata" toggle row
        toggle_row = QHBoxLayout()
        detail_toggle = QToolButton()
        detail_toggle.setObjectName("detailToggle")
        detail_toggle.setCheckable(True)
        detail_toggle.setChecked(False)
        detail_toggle.setText("\u25b8 Mostra analisi dettagliata")
        toggle_row.addWidget(detail_toggle)
        toggle_row.addStretch()

        # Hidden detailed analysis browser
        detail_html = analysis.differences_detail_html or analysis.diff_table_html
        detail_box = QTextBrowser()
        detail_box.setOpenLinks(False)
        detail_box.setHtml(detail_html)
        detail_box.setVisible(False)
        detail_box.anchorClicked.connect(self._open_url)

        def _on_toggle(checked: bool) -> None:
            detail_box.setVisible(checked)
            detail_toggle.setText(
                "\u25be Nascondi analisi dettagliata" if checked else "\u25b8 Mostra analisi dettagliata"
            )

        detail_toggle.toggled.connect(_on_toggle)

        for widget in (link_header, link_box, diff_header, diff_box):
            layout.addWidget(widget)
        layout.addLayout(toggle_row)
        layout.addWidget(detail_box)

    def _open_url(self, url: QUrl) -> None:
        """Robustly open a URL via QDesktopServices, ignoring errors."""
        try:
            QDesktopServices.openUrl(url)
        except Exception:
            pass

    def _to_html(self, text: str) -> str:
        if "<" in text and ">" in text:
            return text
        return "<p>" + escape(text).replace("\n", "<br/>") + "</p>"

    def _section_html(
        self,
        browser: QTextBrowser,
        text: str,
        images: list[WorkbookImage],
        section_name: str,
    ) -> str:
        images_html = []
        for index, image in enumerate(images):
            if not image.data:
                continue
            qimage = QImage.fromData(image.data)
            if qimage.isNull():
                continue
            image_url = QUrl(f"atm://img/{section_name}/{index}")
            browser.document().addResource(QTextDocument.ImageResource, image_url, qimage)
            images_html.append(
                "<div class='atm-image'>"
                f"<img src='{image_url.toString()}' alt='Immagine {index + 1}'/>"
                f"<div class='atm-caption'>Immagine riga {image.row}</div>"
                "</div>"
            )
        if images_html:
            return self._to_html(text) + "<div class='atm-images'>" + "".join(images_html) + "</div>"
        return self._to_html(text)

    def _build_links(self, records: list[FunctionRecord]) -> str:
        lines: list[str] = []
        lines.append("<p>I link sono mostrati per flotta/configurazione. Offline i link potrebbero non aprirsi, ma i dati restano disponibili.</p>")
        general_entries: list[str] = []
        grouped_links: dict[str, list[str]] = {}

        for record in records:
            if record.generale_link:
                link = escape(record.generale_link)
                general_entries.append(
                    f"<li><b>{escape(record.id)} — {escape(record.funzione)}</b>: "
                    f"<a href='{link}'>{link}</a></li>"
                )
            for doc in record.documents:
                for cfg, link in doc.config_links.items():
                    safe_link = escape(link)
                    title = escape(doc.link_title_for_config(cfg) or link)
                    # Look up Rif. Pagina for this config
                    _url, pages = get_document_reference(doc, cfg)
                    page_links = ""
                    if pages:
                        page_items = []
                        for page_num in pages:
                            frag_url = f"{safe_link}#page={page_num}"
                            page_items.append(
                                f"<a href='{frag_url}' title='Apri documento a pagina {page_num}'>"
                                f"📖 Apri a pagina {page_num}</a>"
                            )
                        page_links = " &nbsp; ".join(page_items)
                        page_links = f" <span class='page-links'>({page_links})</span>"
                    grouped_links.setdefault(cfg, []).append(
                        f"<li><b>{escape(record.id)}</b> · DOC {escape(doc.doc_id)} — "
                        f"{escape(doc.info_doc)}: <a href='{safe_link}'>{title}</a>{page_links}</li>"
                    )

        if general_entries:
            lines.append("<h4>Generale / Documenti supplementari</h4><ul>")
            lines.extend(general_entries)
            lines.append("</ul>")

        for config_name, entries in grouped_links.items():
            lines.append(f"<h4>{escape(config_name)}</h4><ul>")
            lines.extend(entries)
            lines.append("</ul>")

        if not general_entries and not grouped_links:
            return "<p>Nessun link disponibile.</p>"
        return "\n".join(lines)
