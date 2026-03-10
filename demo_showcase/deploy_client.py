"""Intentionally unsafe deployment client for demo-review screenshots."""

from __future__ import annotations

import subprocess

import requests


def deploy(service_url: str, command: str, payload: dict[str, object]) -> str:
    requests.post(f"{service_url}/deploy", json=payload, verify=False)
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        return result.stdout
    return "ok"
