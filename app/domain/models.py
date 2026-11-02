from __future__ import annotations

from dataclasses import dataclass

REPAIR_STATUSES = (
    'Recibido',
    'En diagnóstico',
    'Esperando aprobación',
    'En reparación',
    'Listo para entregar',
    'Entregado',
    'Cancelado',
)

TRANSITIONS = {
    'Recibido': {'En diagnóstico', 'Cancelado'},
    'En diagnóstico': {'Esperando aprobación', 'En reparación', 'Cancelado'},
    'Esperando aprobación': {'En reparación', 'Cancelado'},
    'En reparación': {'Listo para entregar', 'Cancelado'},
    'Listo para entregar': {'En reparación', 'Entregado'},
    'Entregado': set(),
    'Cancelado': set(),
}

@dataclass(frozen=True)
class DomainError(Exception):
    message: str
    status_code: int = 400

@dataclass(frozen=True)
class User:
    id: int
    name: str
    email: str
    role: str

