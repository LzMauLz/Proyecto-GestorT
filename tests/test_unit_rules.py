"""Pure rules: these cases do not create Flask or SQLite fixtures."""
import pytest

from app.application.services import to_cents, _to_integer
from app.application.ai_import import parse_provider_json
from app.application.ports import AIProviderError
from app.domain.models import DomainError


@pytest.mark.parametrize(('price', 'expected'), [('0', 0), ('0.01', 1), ('12.34', 1234), ('92233720368547758.07', 9223372036854775807)])
def test_money_preserves_exact_cents_and_storage_boundary(price, expected):
    assert to_cents(price) == expected


@pytest.mark.parametrize('price', ['-0.01', '0.001', 'NaN', 'Infinity', '92233720368547758.08', '', None, True])
def test_invalid_money_cannot_be_persisted(price):
    with pytest.raises(DomainError):
        to_cents(price)


@pytest.mark.parametrize(('value', 'expected'), [(0, 0), ('0', 0), ('2147483647', 2147483647), (12, 12)])
def test_integer_input_has_no_rounding(value, expected):
    assert _to_integer(value) == expected


@pytest.mark.parametrize('value', [True, False, 1.5, '1.5', float('nan'), float('inf'), [], {}])
def test_fractional_or_structured_quantity_is_rejected(value):
    with pytest.raises((ValueError, TypeError)):
        _to_integer(value)


def test_provider_json_accepts_only_products_envelope():
    assert parse_provider_json('{"products": [{"source_row": 2}]}') == [{'source_row': 2}]
    for content in ('[]', 'null', '{}', '{"products": {}}', '{"products": [], "sql": "DROP TABLE products"}', 'broken'):
        with pytest.raises(AIProviderError):
            parse_provider_json(content)
