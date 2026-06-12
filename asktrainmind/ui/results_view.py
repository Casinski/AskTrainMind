from __future__ import annotations

from html import escape

from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextDocument
from PySide6.QtWidgets import QLabel, QTextBrowser, QVBoxLayout, QWidget

from asktrainmind.app.ai_engine import AnalysisOutput
from asktrainmind.app.excel_model import FunctionRecord
from asktrainmind.app.image_extractor import WorkbookImage
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
        link_box.setOpenExternalLinks(True)
        link_box.setHtml(self._build_links(records))

        info_header = QLabel("INFO")
        info_header.setObjectName("sectionTitle")
        info_box = QTextBrowser()
        info_box.setOpenExternalLinks(True)
        info_box.setHtml(self._section_html(info_box, analysis.info_text, render_images, "info"))

        diff_header = QLabel("DIFFERENZE")
        diff_header.setObjectName("sectionTitleImportant")
        diff_box = QTextBrowser()
        diff_box.setOpenExternalLinks(True)
        diff_html = analysis.differences_text
        if analysis.diff_table_html:
            diff_html += "\n" + analysis.diff_table_html
        diff_box.setHtml(self._section_html(diff_box, diff_html, render_images, "diff"))

        for widget in (link_header, link_box, info_header, info_box, diff_header, diff_box):
            layout.addWidget(widget)

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
        lines = []
        for record in records:
            lines.append(f"<h4>{escape(record.id)} - {escape(record.funzione)}</h4>")
            if record.generale_link:
                link = escape(record.generale_link)
                lines.append(f"<p><b>Generale:</b> <a href='{link}'>{link}</a></p>")
            for doc in record.documents:
                lines.append(f"<p><b>DOC {escape(doc.doc_id)}</b> — {escape(doc.info_doc)}</p><ul>")
                for cfg, link in doc.config_links.items():
                    safe_link = escape(link)
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
                    lines.append(
                        f"<li>{escape(cfg)}: <a href='{safe_link}'>{safe_link}</a>{page_links}</li>"
                    )
                lines.append("</ul>")
        return "\n".join(lines) if lines else "<p>Nessun link disponibile.</p>"

