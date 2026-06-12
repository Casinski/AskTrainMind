from pathlib import Path

from asktrainmind.app.comparison import (
    build_comparison_matrix,
    matrix_to_html_table,
    matrix_to_narrative_html,
    matrix_to_plain_text,
)
from asktrainmind.app.excel_model import DetailRecord, DocumentRecord, FunctionRecord, parse_funzioni_sheet


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "DB Flotte ETR1000 Ver_0.5_MM.xlsx"


def test_comparison_matrix_uses_stable_config_order_and_fs_dm1_partial_presence():
    records = parse_funzioni_sheet(WORKBOOK)
    matrix = build_comparison_matrix(records)

    assert matrix.config_names
    assert matrix.config_names == records[0].config_names

    fs_dm1_link_row = next(row for row in matrix.rows if row.doc_id == "FS_DM1" and row.label.endswith("— link"))
    assert fs_dm1_link_row.status == "parziale"
    assert fs_dm1_link_row.cells["VZI_IT_Base / VZI-50_ IT Flotta base"].present is True
    assert fs_dm1_link_row.cells["VZI-6_IT_R1 / VZI-6_IT Full HRI (New 14)"].present is True
    assert fs_dm1_link_row.cells["VZ-FR"].present is False
    assert fs_dm1_link_row.cells["VZ-ES"].present is False
    assert any("Rif. Pagina" in row.label for row in matrix.rows)


def test_comparison_status_uguale_and_diverso_with_synthetic_records():
    record = FunctionRecord(
        id="ID_TEST",
        funzione="Funzione Test",
        tipo="TBD",
        generale_link=None,
        config_names=["CONF_A", "CONF_B"],
        documents=[
            DocumentRecord(
                doc_id="DOC-1",
                info_doc="Info",
                config_links={"CONF_A": "link-1", "CONF_B": "link-1"},
                details=[
                    DetailRecord(title="Rif. Pagina", values={"CONF_A": "10", "CONF_B": "20"}),
                ],
            )
        ],
    )

    matrix = build_comparison_matrix([record])
    link_row = next(row for row in matrix.rows if row.label.endswith("— link"))
    rif_row = next(row for row in matrix.rows if "Rif. Pagina" in row.label)

    assert link_row.status == "uguale"
    assert link_row.all_equal is True
    assert rif_row.status == "diverso"
    assert rif_row.all_equal is False

    html = matrix_to_html_table(matrix)
    text = matrix_to_plain_text(matrix)
    narrative = matrix_to_narrative_html(matrix)
    assert "status-uguale" in html
    assert "status-diverso" in html
    assert "[diverso]" in text
    assert "CONF_A" in narrative and "CONF_B" in narrative
    assert "uguale" in narrative
    assert "diverso" in narrative


def test_comparison_narrative_mentions_parziale():
    record = FunctionRecord(
        id="ID_PARZ",
        funzione="Funzione parziale",
        tipo="TBD",
        generale_link=None,
        config_names=["CONF_A", "CONF_B", "CONF_C"],
        documents=[
            DocumentRecord(
                doc_id="DOC-P",
                info_doc="Info",
                config_links={"CONF_A": "link-a", "CONF_B": "link-b"},
                details=[DetailRecord(title="Rif. Pagina", values={"CONF_A": "10"})],
            )
        ],
    )
    matrix = build_comparison_matrix([record])
    narrative = matrix_to_narrative_html(matrix)
    assert "parziale" in narrative
    assert "CONF_C" in narrative
