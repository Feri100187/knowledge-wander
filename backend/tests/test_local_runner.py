from __future__ import annotations

from pathlib import Path
from typing import Any

import run_local


def test_local_runner_uses_proactor_and_disables_reload(monkeypatch: Any) -> None:
    policy_calls: list[Any] = []
    uvicorn_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(run_local.sys, "platform", "win32")
    monkeypatch.setattr(
        run_local.asyncio,
        "WindowsProactorEventLoopPolicy",
        lambda: "proactor-policy",
        raising=False,
    )
    monkeypatch.setattr(
        run_local.asyncio,
        "set_event_loop_policy",
        lambda policy: policy_calls.append(policy),
    )
    monkeypatch.setattr(
        run_local.uvicorn,
        "run",
        lambda app, **kwargs: uvicorn_calls.append({"app": app, **kwargs}),
    )

    run_local.main()

    assert policy_calls == ["proactor-policy"]
    assert uvicorn_calls == [
        {
            "app": "app.main:app",
            "host": "127.0.0.1",
            "port": 8000,
            "reload": False,
        }
    ]


def test_local_batch_script_uses_project_python_and_pauses() -> None:
    batch_path = Path(__file__).resolve().parents[2] / "start-backend-local.bat"
    content = batch_path.read_text(encoding="utf-8")

    assert 'cd /d "%~dp0backend"' in content
    assert '".venv\\Scripts\\python.exe" run_local.py' in content
    assert "--reload" not in content
    assert "pause" in content.casefold()
