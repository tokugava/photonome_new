#!/usr/bin/env python3
"""Invoke a worker's handler once against a JSON payload, bypassing Pub/Sub.

Usage:
    python scripts/smoke_local.py --worker edit --message tests/edit.json
    python scripts/smoke_local.py --worker generate --message tests/generate.json
    python scripts/smoke_local.py --worker train --message tests/train.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _fake_message() -> SimpleNamespace:
    return SimpleNamespace(ack=lambda: None, nack=lambda: None)


def run_edit(payload: dict) -> None:
    from core import firebase
    from core.config import get_settings
    from core.models import edit_pipeline
    from edit_worker import _handle_factory

    settings = get_settings()
    firebase.init_app()
    pipe = edit_pipeline.build(settings.flux_kontext_model_id)
    _handle_factory(settings, pipe)(payload, _fake_message())


def run_train(payload: dict) -> None:
    from core import firebase
    from train_worker import _handle

    firebase.init_app()
    _handle(payload, _fake_message())


def run_generate(payload: dict) -> None:
    from core import firebase
    from core.config import get_settings
    from core.vram_lock import GenerateGuard
    from generate_worker import _State, _handle_factory

    settings = get_settings()
    firebase.init_app()
    guard = GenerateGuard()
    state = _State()
    _handle_factory(settings, guard, state)(payload, _fake_message())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", required=True, choices=["edit", "train", "generate"])
    ap.add_argument("--message", required=True, type=Path, help="JSON file with the message body")
    args = ap.parse_args()

    payload = json.loads(args.message.read_text())
    {"edit": run_edit, "train": run_train, "generate": run_generate}[args.worker](payload)


if __name__ == "__main__":
    main()
