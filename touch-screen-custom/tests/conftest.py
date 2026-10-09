import pytest


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    """Tests must never read the desktop user's real configuration."""
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path/'config'))
