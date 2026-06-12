from asktrainmind.app.sharepoint import parse_sharepoint_folder_url


def test_parse_sharepoint_folder_url():
    url = (
        "https://gruppofsitaliane.sharepoint.com/:f:/r/sites/"
        "IngegneriaETReMezziLeggeri-Trenitalia/Shared%20Documents/Prova%20Doc%20ETR1000"
        "?csf=1&web=1&e=bmZNVq"
    )
    parsed = parse_sharepoint_folder_url(url)
    assert parsed.tenant == "gruppofsitaliane.sharepoint.com"
    assert parsed.site_path == "IngegneriaETReMezziLeggeri-Trenitalia"
    assert parsed.folder_path == "Shared Documents/Prova Doc ETR1000"
