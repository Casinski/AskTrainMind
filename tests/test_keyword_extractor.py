from asktrainmind.app.keyword_extractor import extract_keywords


def test_extract_keywords_captures_fam_and_component_code():
    question = "Come funziona il FAM? e il componente GG-A024?"
    keys = extract_keywords(question)
    assert "FAM" in keys
    assert "GG-A024" in keys
