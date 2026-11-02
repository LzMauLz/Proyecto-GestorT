"""Application orchestration for optional, human-reviewed product proposals."""
import json

from app.application.ports import AIProviderError

AI_FIELDS = ('name', 'description', 'category')
MAX_AI_ROWS = 50


def prepare_product_proposal(rows, provider=None):
    """Return source rows and validated suggestions; failures preserve manual input."""
    if provider is None or len(rows) > MAX_AI_ROWS or any(row.get('error') for row in rows):
        return rows, 'manual'

    payload = [
        {'source_row': row['source_row'], **{key: row.get(key, '') for key in AI_FIELDS}}
        for row in rows
    ]
    try:
        proposals = provider.propose_products(payload)
        if not isinstance(proposals, list) or len(proposals) != len(rows):
            raise AIProviderError('Invalid proposal shape')
        by_row = {}
        for proposal in proposals:
            if not isinstance(proposal, dict) or set(proposal) != {'source_row', *AI_FIELDS}:
                raise AIProviderError('Invalid proposal fields')
            row_id = proposal['source_row']
            if not isinstance(row_id, int) or row_id in by_row:
                raise AIProviderError('Invalid proposal row')
            for key in AI_FIELDS:
                value = proposal[key]
                if not isinstance(value, str) or len(value) > {'name': 160, 'description': 2000, 'category': 100}[key]:
                    raise AIProviderError('Invalid proposal value')
            by_row[row_id] = proposal
        if set(by_row) != {row['source_row'] for row in rows}:
            raise AIProviderError('Proposal rows mismatch')
        prepared = []
        for source in rows:
            suggestion = by_row[source['source_row']]
            row = dict(source)
            row['original_values'] = {key: source.get(key, '') for key in AI_FIELDS}
            for key in AI_FIELDS:
                row[key] = suggestion[key].strip()
            row['ai_suggested'] = True
            prepared.append(row)
        return prepared, 'groq'
    except Exception:
        # Do not log provider content. Any failure keeps the verified source values.
        return rows, 'manual'


def parse_provider_json(content):
    """Parse a JSON object containing only a products array."""
    try:
        value = json.loads(content)
    except (TypeError, ValueError) as exc:
        raise AIProviderError('Invalid provider JSON') from exc
    if not isinstance(value, dict) or set(value) != {'products'} or not isinstance(value['products'], list):
        raise AIProviderError('Invalid provider response')
    return value['products']
