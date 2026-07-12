"""Tests du Connector Manager."""
import pytest
from omniagent.connectors.manager import connector_manager
from omniagent.core.registry.connector_registry import ConnectorSpec, connector_registry
from omniagent.connectors.bootstrap import register_all


def test_bootstrap_registers_all():
    register_all()
    cats = {}
    for spec in connector_registry._connectors.values():
        cats.setdefault(spec.category, []).append(spec.name)
    assert "pennylane" in cats["comptabilite"]
    assert "stripe" in cats["comptabilite"]
    assert "whatsapp" in cats["messagerie"]
    assert "twilio_sms" in cats["messagerie"]
    assert "vapi" in cats["messagerie"]
    assert "hunter" in cats["plateformes"]