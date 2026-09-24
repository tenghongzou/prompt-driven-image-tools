"""Running `python app.py` must never enable the Werkzeug debugger by accident."""
import runpy
from pathlib import Path

import pytest
from flask import Flask

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def run_kwargs(monkeypatch):
    """Execute app.py as __main__ with Flask.run stubbed out; return its kwargs."""
    captured = {}
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: captured.update(kwargs))

    def _run():
        runpy.run_path(APP_PATH, run_name="__main__")
        return captured

    return _run


def test_debug_off_by_default(run_kwargs, monkeypatch):
    monkeypatch.delenv("FLASK_DEBUG", raising=False)

    assert run_kwargs()["debug"] is False


def test_debug_enabled_only_by_flask_debug_env(run_kwargs, monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "1")

    assert run_kwargs()["debug"] is True
