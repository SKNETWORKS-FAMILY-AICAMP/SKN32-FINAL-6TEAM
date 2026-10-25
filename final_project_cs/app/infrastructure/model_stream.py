"""Collect provider pieces under explicit first/stall/total deadlines (502da503c)."""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, Iterator

import httpx

from app.infrastructure.ollama_chat import OllamaError


class StreamStalled(OllamaError):
    def __init__(self, message: str, *, which: str) -> None:
        super().__init__(message)
        self.which = which


def _close(resource) -> None:
    try:
        resource.close()
    except Exception:
        logging.getLogger(__name__).warning('model stream cleanup failed', exc_info=True)


class StreamLifetime:
    """Cooperative cancellation; blocking transport/close may outlive the caller.

    Existing responses close on a daemon; late responses close on the producer
    before reading. No thread is forcibly interrupted.
    """
    def __init__(self):
        self.stopped = threading.Event()
        self._lock = threading.Lock()
        self._response = None

    def acquire(self, response) -> bool:
        with self._lock:
            if not self.stopped.is_set():
                self._response = response
                return True
        _close(response)
        return False

    def finish(self) -> None:
        with self._lock:
            response, self._response = self._response, None
        if response is not None:
            _close(response)

    def cancel(self) -> None:
        with self._lock:
            self.stopped.set()
            response, self._response = self._response, None
        if response is not None:
            threading.Thread(target=_close, args=(response,), name='model-stream-close', daemon=True).start()

    def iterate(self, source):
        iterator = iter(source)
        try:
            while not self.stopped.is_set():
                try:
                    value = next(iterator)
                except StopIteration:
                    return
                if self.stopped.is_set():
                    return
                yield value
        finally:
            if hasattr(iterator, 'close'):
                _close(iterator)


def collect(pieces: Callable[[], Iterator[str]], *, first_wait: float, stall: float,
            max_seconds: float, on_piece: Callable[[str], None] | None = None,
            close: Callable[[], None] | None = None,
            clock: Callable[[], float] = time.monotonic,
            lifetime: StreamLifetime | None = None) -> str:
    """Discard partial answers on timeout; bound the producer queue and stop it on exit."""
    box = queue.Queue(maxsize=1)
    lifetime = lifetime or StreamLifetime()
    stop = lifetime.stopped
    end = object()

    def put(value):
        while not stop.is_set():
            try:
                box.put(value, timeout=min(first_wait, stall, max_seconds))
                return
            except queue.Full:
                continue

    def produce():
        iterator = None
        try:
            iterator = pieces()
            for piece in lifetime.iterate(iterator):
                if stop.is_set():
                    break
                if piece:
                    put(piece)
        except BaseException as exc:
            put(exc)
        finally:
            # Signal completion before cleanup: a blocking close must not turn a complete answer into a stall.
            put(end)
            if iterator is not None and hasattr(iterator, 'close'):
                _close(iterator)
            lifetime.finish()

    started = last = clock()
    parts = []
    threading.Thread(target=produce, name='model-stream', daemon=True).start()
    try:
        while True:
            now = clock()
            which = 'first' if not parts else 'stall'
            remaining = (first_wait if not parts else stall) - (now - last)
            total = max_seconds - (now - started)
            if total <= remaining:
                which, remaining = 'max', total
            try:
                if remaining <= 0:
                    raise queue.Empty
                value = box.get(timeout=remaining)
            except queue.Empty:
                raise StreamStalled(f'model stream deadline: {which}', which=which) from httpx.ReadTimeout(which)
            if value is end:
                return ''.join(parts)
            if isinstance(value, BaseException):
                raise value
            last = clock()
            parts.append(value)
            if on_piece is not None:
                try:
                    on_piece(''.join(parts))
                except Exception:
                    logging.getLogger(__name__).warning('model stream progress callback failed')
    finally:
        lifetime.cancel()
        if close is not None:
            def cleanup():
                try:
                    close()
                except Exception:
                    logging.getLogger(__name__).warning('model stream close callback failed', exc_info=True)
            threading.Thread(target=cleanup, name='model-stream-close', daemon=True).start()
