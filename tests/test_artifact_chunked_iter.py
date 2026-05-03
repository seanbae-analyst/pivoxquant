"""Unit tests for services.artifacts.iter_users_chunked.

Guards the B18 fix: every PDF cron must yield items in original order
while forcing a `gc.collect()` pass after every chunk so WeasyPrint
memory is released on small dynos. The progress callback must fire
exactly once per chunk with (chunk_index, total_chunks, items_in_chunk).
"""
from __future__ import annotations

import gc
import os
from unittest.mock import patch

import pytest

from services.artifacts import iter_users_chunked


class TestIterUsersChunked:
    def test_preserves_order_and_yields_all(self):
        users = [f"u{i}" for i in range(7)]
        out = list(iter_users_chunked(users, label="t.preserve"))
        assert out == users

    def test_empty_input_yields_nothing(self):
        out = list(iter_users_chunked([], label="t.empty"))
        assert out == []

    def test_calls_gc_collect_between_chunks(self):
        users = list(range(7))  # 3 + 3 + 1 → 3 chunks → 3 gc.collect() calls
        with patch("services.artifacts.gc.collect") as mock_gc:
            list(iter_users_chunked(users, label="t.gc", chunk_size=3))
        assert mock_gc.call_count == 3

    def test_chunk_size_one_collects_per_user(self):
        users = list(range(4))
        with patch("services.artifacts.gc.collect") as mock_gc:
            list(iter_users_chunked(users, label="t.cs1", chunk_size=1))
        assert mock_gc.call_count == 4

    def test_progress_callback_fires_once_per_chunk(self):
        users = list(range(7))  # 3 + 3 + 1
        events: list[tuple[int, int, int]] = []
        list(iter_users_chunked(
            users, label="t.cb", chunk_size=3,
            on_chunk_done=lambda i, t, n: events.append((i, t, n)),
        ))
        assert events == [(1, 3, 3), (2, 3, 3), (3, 3, 1)]

    def test_callback_exception_does_not_break_iteration(self):
        users = list(range(5))
        def bad(*_a, **_k):
            raise RuntimeError("ignored")
        out = list(iter_users_chunked(
            users, label="t.bad_cb", chunk_size=2, on_chunk_done=bad,
        ))
        assert out == users

    def test_explicit_chunk_size_overrides_env(self, monkeypatch):
        monkeypatch.setenv("ARTIFACT_PDF_CHUNK_SIZE", "10")
        users = list(range(6))
        with patch("services.artifacts.gc.collect") as mock_gc:
            list(iter_users_chunked(users, label="t.override", chunk_size=2))
        # explicit chunk_size=2 → 3 chunks → 3 gc.collect()
        assert mock_gc.call_count == 3

    def test_env_chunk_size_used_when_no_override(self, monkeypatch):
        monkeypatch.setenv("ARTIFACT_PDF_CHUNK_SIZE", "5")
        users = list(range(10))
        with patch("services.artifacts.gc.collect") as mock_gc:
            list(iter_users_chunked(users, label="t.env"))
        # env chunk_size=5 → 2 chunks → 2 gc.collect()
        assert mock_gc.call_count == 2

    def test_invalid_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("ARTIFACT_PDF_CHUNK_SIZE", "not-a-number")
        users = list(range(7))
        with patch("services.artifacts.gc.collect") as mock_gc:
            list(iter_users_chunked(users, label="t.bad_env"))
        # default chunk_size=3 → 3 chunks
        assert mock_gc.call_count == 3

    def test_iterable_input_not_just_list(self):
        users = (f"u{i}" for i in range(5))  # generator
        out = list(iter_users_chunked(users, label="t.gen", chunk_size=2))
        assert out == [f"u{i}" for i in range(5)]
