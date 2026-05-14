"""Cooperative VRAM mutex between train_worker (exclusive) and generate_worker (shared).

Two files in `settings.vram_lock_dir`:
- `vram.lock` — fcntl flock. train takes LOCK_EX, generate takes LOCK_SH.
- `train.want` — touched by train at job start, removed at job end. Generate polls
  this file every second and yields the GPU when it appears.
"""
from __future__ import annotations

import fcntl
import gc
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

import structlog

from core.config import get_settings

log = structlog.get_logger(__name__)


def _paths() -> tuple[Path, Path]:
    base = get_settings().vram_lock_dir
    return base / "vram.lock", base / "train.want"


class YieldRequested(Exception):
    """Raised inside a diffusers callback when train_worker wants the GPU."""


@contextmanager
def TrainLock() -> Iterator[None]:
    lock_path, want_path = _paths()
    want_path.touch()
    log.info("train_lock_requesting")
    fh = lock_path.open("w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX)
        log.info("train_lock_acquired")
        yield
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()
        want_path.unlink(missing_ok=True)
        log.info("train_lock_released")


class GenerateGuard:
    """Holds a shared lock on the VRAM file and watches for train_worker signals.

    Usage from generate_worker:
        guard = GenerateGuard()
        pipe = guard.ensure_loaded(pipe_ref, builder)
        ... pipe(prompt=..., callback_on_step_end=guard.step_callback) ...
        # if YieldRequested raised, catch in handler -> guard.yield_vram(pipe) -> nack
    """

    def __init__(self) -> None:
        self._lock_path, self._want_path = _paths()
        self._fh = None
        self._yield_event = threading.Event()
        self._stop = threading.Event()
        self._watcher: threading.Thread | None = None

    def _start_watcher(self) -> None:
        if self._watcher and self._watcher.is_alive():
            return
        self._yield_event.clear()
        self._stop.clear()

        def loop() -> None:
            while not self._stop.is_set():
                if self._want_path.exists():
                    log.info("train_want_observed_yielding")
                    self._yield_event.set()
                    return
                time.sleep(1.0)

        self._watcher = threading.Thread(target=loop, name="train-watcher", daemon=True)
        self._watcher.start()

    def _stop_watcher(self) -> None:
        self._stop.set()
        if self._watcher is not None:
            self._watcher.join(timeout=2.0)
        self._watcher = None

    def _acquire_shared(self) -> None:
        # Block while train_worker holds LOCK_EX.
        self._fh = self._lock_path.open("w")
        fcntl.flock(self._fh, fcntl.LOCK_SH)
        log.info("generate_shared_lock_acquired")

    def _release_shared(self) -> None:
        if self._fh is None:
            return
        try:
            fcntl.flock(self._fh, fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None
        log.info("generate_shared_lock_released")

    def ensure_loaded(self, pipe, builder: Callable):
        """Return a live pipeline, blocking while train holds the lock and rebuilding if needed."""
        # If train is currently requesting/holding the GPU, wait it out before (re)building.
        while self._want_path.exists():
            time.sleep(1.0)
        if self._fh is None:
            self._acquire_shared()
        if pipe is None:
            log.info("building_pipeline")
            pipe = builder()
        self._start_watcher()
        return pipe

    def step_callback(self, pipeline, step: int, timestep, callback_kwargs):
        """Pass as `callback_on_step_end=` to a diffusers pipeline call."""
        if self._yield_event.is_set():
            raise YieldRequested()
        return callback_kwargs

    def yield_vram(self, pipe):
        """Tear down the in-VRAM pipeline so train can take LOCK_EX."""
        import torch

        log.info("yielding_vram")
        self._stop_watcher()
        try:
            if pipe is not None:
                try:
                    pipe.to("cpu")
                except Exception:
                    pass
                del pipe
        finally:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self._release_shared()
        log.info("vram_released")

    def yield_requested(self) -> bool:
        return self._yield_event.is_set()
