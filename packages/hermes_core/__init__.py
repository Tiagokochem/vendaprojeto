"""Hermes core — motor multi-tenant (scaffold).

No lab (../vendas) a lógica vive em scripts/hermes.py.
Aqui será o pacote compartilhado do produto: outbound, inbound, playbooks.
"""

__version__ = "0.1.0"


def health() -> dict:
    return {"ok": True, "package": "hermes_core", "version": __version__}
