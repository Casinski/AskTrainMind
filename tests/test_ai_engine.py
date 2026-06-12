from asktrainmind.app.ai_engine import AnalysisEngine
from asktrainmind.app.config import AIConfig
from asktrainmind.app.excel_model import DetailRecord, DocumentRecord, FunctionRecord
from asktrainmind.app.image_extractor import WorkbookImage


class StubProvider:
    def analyze(self, records, matrix, images=None):
        return "=== INFO ===\nSintesi INFO\n=== DIFFERENZE ===\nSintesi DIFFERENZE"


class StubFailProvider:
    def analyze(self, records, matrix, images=None):
        raise RuntimeError("boom")


def _records() -> list[FunctionRecord]:
    return [
        FunctionRecord(
            id="ID_TEST",
            funzione="Funzione Test",
            tipo="TBD",
            generale_link=None,
            config_names=["CONF_A", "CONF_B"],
            documents=[
                DocumentRecord(
                    doc_id="DOC-1",
                    info_doc="Info",
                    config_links={"CONF_A": "link-1"},
                    details=[
                        DetailRecord(title="Rif. Pagina", values={"CONF_A": "10", "CONF_B": "20"}),
                    ],
                )
            ],
            start_row=2,
            end_row=6,
        )
    ]


def test_engine_parses_marked_sections_from_provider(monkeypatch):
    engine = AnalysisEngine(AIConfig(provider="openai", api_key="x", model="gpt-4o-mini"))
    monkeypatch.setattr(engine, "_build_provider", lambda: StubProvider())

    output = engine.analyze(_records())

    assert output.info_text == "Sintesi INFO"
    assert output.differences_text == "Sintesi DIFFERENZE"


def test_engine_offline_mode_populates_diff_table():
    engine = AnalysisEngine(AIConfig(provider="null"))

    output = engine.analyze(_records())

    assert "deterministica" in (output.banner or "").lower()
    assert "diff-table" in output.diff_table_html
    assert output.info_text != output.differences_text


def test_engine_accepts_images_argument_without_crash(monkeypatch):
    engine = AnalysisEngine(AIConfig(provider="openai", api_key="x", model="gpt-4o-mini"))
    monkeypatch.setattr(engine, "_build_provider", lambda: StubProvider())
    images = [WorkbookImage(row=3, column=1, mime_type="image/png", data=b"not-an-image")]

    output = engine.analyze(_records(), images=images)

    assert output.images == images
    assert "diff-table" in output.diff_table_html


def test_engine_falls_back_to_null_provider_on_error(monkeypatch):
    engine = AnalysisEngine(AIConfig(provider="openai", api_key="x", model="gpt-4o-mini"))
    monkeypatch.setattr(engine, "_build_provider", lambda: StubFailProvider())

    output = engine.analyze(_records())

    assert "deterministica" in (output.banner or "").lower()
