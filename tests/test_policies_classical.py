"""Tests for the L2 classical-control rung (``embodimetry.policies_classical``).

These cover the load + action-shape contract (the cheap, torch-free part)
and the registry/config wiring that makes ``classical_pusht`` dispatch
through the same ``PolicyCallable`` path as the baselines. The actual
rollout success number is produced by a real eval (see the PR body), not
asserted here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from embodimetry.eval import load_policy
from embodimetry.policies import PolicyRegistry
from embodimetry.policies_classical import (
    _ClassicalPushTPolicy,
    load_classical_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICIES_YAML = REPO_ROOT / "configs" / "policies.yaml"

# A representative gym-pusht `state` observation:
# [agent_x, agent_y, block_x, block_y, block_angle].
_PUSHT_STATE_OBS = np.array([85.0, 359.0, 330.0, 304.0, 2.25], dtype=np.float64)


def test_classical_pusht_returns_valid_action_shape() -> None:
    """The controller maps a PushT state obs to a (2,) float32 action in [0, 512]."""
    policy = _ClassicalPushTPolicy(action_shape=(2,))
    action = policy(_PUSHT_STATE_OBS)
    assert action.shape == (2,)
    assert action.dtype == np.float32
    assert np.all(action >= 0.0) and np.all(action <= 512.0)


def test_classical_pusht_is_deterministic() -> None:
    """Same observation in -> identical action out (no internal RNG)."""
    policy = _ClassicalPushTPolicy(action_shape=(2,))
    a1 = policy(_PUSHT_STATE_OBS)
    policy.reset()
    a2 = policy(_PUSHT_STATE_OBS)
    np.testing.assert_array_equal(a1, a2)


def test_classical_pusht_rejects_non_pusht_action_shape() -> None:
    with pytest.raises(ValueError, match="expects a 2-D action"):
        _ClassicalPushTPolicy(action_shape=(14,))


def test_classical_pusht_rejects_dict_obs() -> None:
    """A dict obs means the env was wired with the wrong obs_type — fail loud."""
    policy = _ClassicalPushTPolicy(action_shape=(2,))
    with pytest.raises(RuntimeError, match="expects the gym-pusht 'state' observation"):
        policy({"pixels": np.zeros((96, 96, 3)), "agent_pos": np.zeros(2)})


def test_classical_pusht_rejects_short_state() -> None:
    policy = _ClassicalPushTPolicy(action_shape=(2,))
    with pytest.raises(RuntimeError, match=">=5-dim state observation"):
        policy(np.array([1.0, 2.0, 3.0]))


def test_load_classical_policy_requires_action_shape() -> None:
    with pytest.raises(ValueError, match="requires action_shape"):
        load_classical_policy("classical_pusht", action_shape=None)


def test_load_classical_policy_unknown_name() -> None:
    with pytest.raises(ValueError, match="unknown classical policy"):
        load_classical_policy("classical_nonexistent", action_shape=(2,))


# --------------------------------------------------------------------- #
# Registry + dispatch wiring (same contract as the baselines)           #
# --------------------------------------------------------------------- #


def test_classical_pusht_registered_as_weightless_baseline() -> None:
    """It dispatches like no_op/random: is_baseline, no weights, runnable, CPU."""
    spec = PolicyRegistry.from_yaml(DEFAULT_POLICIES_YAML).get("classical_pusht")
    assert spec.is_baseline is True
    assert spec.repo_id is None
    assert spec.revision_sha is None
    assert spec.is_runnable() is True
    assert spec.env_compat == ("pusht_state",)


def test_classical_pusht_dispatches_through_load_policy() -> None:
    """load_policy (the shared dispatch) resolves it to the scripted controller."""
    spec = PolicyRegistry.from_yaml(DEFAULT_POLICIES_YAML).get("classical_pusht")
    policy = load_policy(spec, action_shape=(2,), device="cpu")
    action = policy(_PUSHT_STATE_OBS)
    assert action.shape == (2,)
    assert action.dtype == np.float32


def test_classical_pusht_gated_off_v1_leaderboard() -> None:
    """It must NOT be on the published v1 set — gated like xvla_libero."""
    from embodimetry.leaderboard_filter import V1_POLICIES

    assert "classical_pusht" not in V1_POLICIES
