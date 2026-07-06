"""Unit tests for the canonical v1 leaderboard policy gate.

``filter_to_v1_policies`` is the single source of truth both public
surfaces (Space + dashboard) call right after parquet load. The parity
suite (``test_leaderboard_filter_parity.py``) only proves the two
surfaces stay equal; these tests pin the function's own keep/drop
semantics so a regression in the gate itself is caught directly.

Dependency-light by design: ``pandas`` only, mirroring the module.
"""

from __future__ import annotations

import pandas as pd

from embodimetry.leaderboard_filter import V1_POLICIES, filter_to_v1_policies


def _df(policies: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"policy": policies, "value": list(range(len(policies)))})


def test_keeps_all_v1_policies() -> None:
    df = _df(list(V1_POLICIES))
    out = filter_to_v1_policies(df)
    assert sorted(out["policy"]) == sorted(V1_POLICIES)
    assert len(out) == len(V1_POLICIES)


def test_drops_non_v1_policies() -> None:
    """xvla_libero (deferred to v1.1, PR #76) must be dropped."""
    df = _df(["act", "xvla_libero", "no_op"])
    out = filter_to_v1_policies(df)
    assert list(out["policy"]) == ["act", "no_op"]
    assert "xvla_libero" not in set(out["policy"])


def test_drops_unknown_policy() -> None:
    df = _df(["act", "some_future_policy"])
    out = filter_to_v1_policies(df)
    assert list(out["policy"]) == ["act"]


def test_resets_index_after_drop() -> None:
    """Downstream positional access relies on a clean RangeIndex."""
    df = _df(["xvla_libero", "act", "xvla_libero", "random"])
    out = filter_to_v1_policies(df)
    assert list(out.index) == [0, 1]
    assert list(out["policy"]) == ["act", "random"]


def test_does_not_mutate_input() -> None:
    df = _df(["act", "xvla_libero"])
    filter_to_v1_policies(df)
    assert list(df["policy"]) == ["act", "xvla_libero"]


def test_empty_frame_passes_through_unchanged() -> None:
    """Cold-start empty frame is returned as-is, not raised on."""
    df = pd.DataFrame()
    out = filter_to_v1_policies(df)
    assert out is df


def test_frame_without_policy_column_passes_through_unchanged() -> None:
    """A partially-written parquet missing ``policy`` passes through."""
    df = pd.DataFrame({"env": ["pusht"], "value": [1]})
    out = filter_to_v1_policies(df)
    assert out is df


def test_all_rows_dropped_yields_empty_v1_frame() -> None:
    df = _df(["xvla_libero", "another_non_v1"])
    out = filter_to_v1_policies(df)
    assert len(out) == 0
    assert "policy" in out.columns
