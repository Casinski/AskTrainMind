from pathlib import Path

from asktrainmind.app.excel_model import parse_funzioni_sheet


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "DB Flotte ETR1000 Ver_0.5_MM.xlsx"


def test_parse_funzioni_sheet_found_and_level1_fields():
    records = parse_funzioni_sheet(WORKBOOK)
    assert records
    first = records[0]
    assert first.id
    assert first.funzione


def test_parse_doc_and_detail_rows_for_fs_dm1():
    records = parse_funzioni_sheet(WORKBOOK)
    fam = next(r for r in records if r.id == "Isolam_FAM_01")
    fs_dm1 = next(d for d in fam.documents if d.doc_id == "FS_DM1")

    assert any("VZI_IT_Base" in cfg for cfg in fs_dm1.config_links)
    assert any("VZI-6_IT_R1" in cfg for cfg in fs_dm1.config_links)
    assert not any("VZ-FR" in cfg for cfg in fs_dm1.config_links)

    titles = {d.title for d in fs_dm1.details}
    assert "Rif. Pagina" in titles
    assert "Componenti circuito elettrico" in titles
