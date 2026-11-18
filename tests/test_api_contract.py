import re

from app import create_app


def test_openapi_and_api_routes_have_matching_paths_and_methods(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'contract-test-only',
                      'DATABASE': str(tmp_path / 'unused.sqlite3'),
                      'GROQ_ENABLED': False, 'GROQ_API_KEY': '', 'GROQ_MODEL': ''})
    schema = app.test_client().get('/api/openapi.json').get_json()
    actual = set()
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith('/api/'):
            path = re.sub(r'<[^>]+>', '{}', rule.rule[len('/api'):])
            actual.update((path, method.lower()) for method in rule.methods - {'HEAD', 'OPTIONS'})
    declared = {(re.sub(r'\{[^}]+\}', '{}', path), method)
                for path, item in schema['paths'].items()
                for method in item if method in {'get', 'post', 'put', 'patch', 'delete'}}
    assert actual == declared
