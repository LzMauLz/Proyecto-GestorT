"""Ports used by optional infrastructure integrations."""
from typing import Protocol


class AIProviderError(Exception):
    """Provider failures safe to handle with the manual workflow."""


class ProductProposalProvider(Protocol):
    def propose_products(self, rows: list[dict]) -> list[dict]:
        """Return proposals keyed by source_row; never persist data."""
