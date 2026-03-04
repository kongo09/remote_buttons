"""Shared fixtures for Remote Buttons tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def remote_entity_id() -> str:
    """Return a test remote entity ID."""
    return "remote.living_room"
