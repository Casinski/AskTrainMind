from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTextBrowser, QVBoxLayout, QWidget

from asktrainmind.app.ai_engine import AnalysisOutput
from asktrainmind.app.excel_model import FunctionRecord


class ResultsView(QWidget):
    def __init__(self, records: list[FunctionRecord], analysis: AnalysisOutput, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Risultati")

        layout = QVBoxLayout(self)

        if analysis.banner:
            banner = QLabel(analysis.banner)
            banner.setObjectName("banner")
            layout.addWidget(banner)

        link_header = QLabel("LINK")
        link_header.setObjectName("sectionTitle")
        link_box = QTextBrowser()
        link_box.setOpenExternalLinks(True)
        link_box.setHtml(self._build_links(records))

        info_header = QLabel("INFO")
        info_header.setObjectName("sectionTitle")
        info_box = QTextBrowser()
        info_box.setPlainText(analysis.info_text)

        diff_header = QLabel("DIFFERENZE")
        diff_header.setObjectName("sectionTitle")
        diff_box = QTextBrowser()
        diff_box.setPlainText(analysis.differences_text)

        for widget in (link_header, link_box, info_header, info_box, diff_header, diff_box):
            layout.addWidget(widget)

    def _build_links(self, records: list[FunctionRecord]) -> str:
        lines = []
        for record in records:
            lines.append(f"<h4>{record.id} - {record.funzione}</h4>")
            if record.generale_link:
                lines.append(f"<p><b>Generale:</b> <a href='{record.generale_link}'>{record.generale_link}</a></p>")
            for doc in record.documents:
                lines.append(f"<p><b>DOC {doc.doc_id}</b></p><ul>")
                for cfg, link in doc.config_links.items():
                    lines.append(f"<li>{cfg}: <a href='{link}'>{link}</a></li>")
                rif_pages = [d for d in doc.details if d.title.lower().startswith("rif")]
                for det in rif_pages:
                    lines.append(f"<li>Rif. Pagina: {det.values}</li>")
                lines.append("</ul>")
        return "\n".join(lines) if lines else "<p>Nessun link disponibile.</p>"
