from __future__ import annotations

from typing import Any

import run_local


def test_local_runner_starts_uvicorn_without_reload(monkeypatch: Any) -> None:
    uvicorn_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        run_local.uvicorn,
        "run",
        lambda app, **kwargs: uvicorn_calls.append({"app": app, **kwargs}),
    )

    run_local.main()

    assert uvicorn_calls == [
        {
            "app": "app.main:app",
            "host": "127.0.0.1",
            "port": 8000,
            "reload": False,
        }
    ]
