import re
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def test_catalog_uses_content_versions_for_css_and_javascript(integration_app):
    client = integration_app.test_client()
    response = client.get('/catalog')
    assert response.status_code == 200
    urls = re.findall(r'(?:href|src)="(/static/(?:css|js)/[^"]+)"', response.get_data(as_text=True))
    paths = {urlsplit(url).path.removeprefix('/static/') for url in urls}
    assert paths >= {
        'css/app.css',
        'css/gestortech-theme.css',
        'css/catalog.css',
        'css/storefront.css',
        'js/app.js',
        'js/ui.js',
        'js/storefront.js',
    }

    for url in urls:
        resource = urlsplit(url)
        filename = resource.path.removeprefix('/static/')
        content = (Path(integration_app.static_folder) / filename).read_bytes()
        assert parse_qs(resource.query) == {'v': [sha256(content).hexdigest()[:12]]}
        asset = client.get(url)
        assert asset.status_code == 200
        assert asset.data == content
