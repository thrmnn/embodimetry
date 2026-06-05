"""Classical (hand-coded) control policies — the L2 rung of the ladder.

These are the classical-control reference points on Embodimetry's
Capability-Ladder Audit (L0 zero-shot eval → L1 fine-tune → **L2
classical control** → L3 world-model MPC → L4 RL). They carry no
learned weights, run on CPU with no VRAM, and dispatch through the exact
same :class:`embodimetry.eval.PolicyCallable` contract as ``no_op`` /
``random`` and the learned policies — so the success rate they produce
is scored by the *identical* env coverage/success rule, making the
comparison to ``diffusion_policy`` apples-to-apples.

The only structural difference from a learned policy is the observation
type. A vision policy (``diffusion_policy``) consumes the PushT
``pixels_agent_pos`` observation; a state-feedback classical controller
consumes the ``state`` observation (``[agent_x, agent_y, block_x,
block_y, block_angle]``). Both are the same env, the same seeds, the
same ``coverage > 0.95`` success rule — only the sensor channel differs,
which is exactly what distinguishes an L2 state-feedback controller from
an L0 vision policy.

These are intentionally *not* on the published v1 leaderboard
(``embodimetry.leaderboard_filter.V1_POLICIES``); they are
research-in-progress ladder citizens, gated off the public surfaces the
same way ``xvla_libero`` is.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

# PushT geometry constants (gym_pusht.envs.pusht.PushTEnv). The goal pose
# is hard-coded at reset and never changes across episodes, so the
# controller can treat it as a fixed target rather than read it from the
# observation (it is not in the `state` obs vector anyway).
PUSHT_GOAL_XY: tuple[float, float] = (256.0, 256.0)
PUSHT_GOAL_THETA: float = float(np.pi / 4.0)
# Action space is the target agent (pusher) position in [0, 512]^2; the
# env's internal PD loop drives the pusher toward whatever target we emit.
PUSHT_ACTION_LO: float = 0.0
PUSHT_ACTION_HI: float = 512.0
# The stand-off in px at which the pusher lines up behind the block on the
# goal-pointing contact normal. Hand-set to a sensible regime (a single
# probe over a few values), NOT swept — see the controller-quality note in
# the PR body. ~half the T's long-arm extent.
PUSHT_STANDOFF_PX: float = 35.0


class _ClassicalPushTPolicy:
    """Scripted push-behind controller for gym-pusht (L2 reference).

    Strategy (deterministic given the env seed — no internal RNG):

    1. Read the block centre ``(bx, by)``, block heading ``b_theta`` and the
       agent (pusher) position ``(ax, ay)`` from the ``state`` observation.
       The goal pose is the env's fixed ``(256, 256, π/4)``.
    2. Compute the block→goal unit direction ``û``. To translate the block
       toward the goal the pusher must bear on it from the *far side*, on
       the contact normal ``û``.
    3. **Two-phase push-behind:**

       * **APPROACH** — if the pusher is not yet lined up behind the block
         (it is goal-side, or too far off the push axis), drive to the
         stand-off point ``block − standoff·û`` to get onto the contact
         normal. A single-target "aim at the behind point" controller never
         makes contact (the env PD loop parks the pusher *at* the behind
         point and stops), so this lining-up phase is necessary.
       * **PUSH** — once lined up, aim *through* the block toward the goal
         (``block + standoff·û``) so the PD loop keeps bearing the pusher
         into the block, plus a tangential nudge proportional to the
         heading error ``π/4 − b_theta`` to torque the T toward its target
         orientation, not only translate it.

    4. Emit the resulting target pusher position, clipped to the action
       box ``[0, 512]^2``.

    This is a sensible, documented classical baseline — *not* an optimal
    controller. PushT is a contact-rich, underactuated pushing task: a
    single-contact push-behind heuristic nudges the block toward the goal
    but has no recovery when the T slips off the contact normal or rotates
    past target, and it cannot finesse the simultaneous position+orientation
    precision the ``coverage > 0.95`` success bar demands. It is here to
    anchor the L2 rung with a real, reproducible number, not to win.

    Stateless: ``reset`` is a no-op and the action is a pure function of
    the current observation, so a fixed seed reproduces the rollout
    bit-for-bit through the eval loop's seeding contract.
    """

    # Orientation gain: px of tangential (off-axis) nudge per radian of
    # block-heading error. Hand-set to a sensible regime, not swept.
    _K_THETA: float = 50.0

    def __init__(self, action_shape: tuple[int, ...]) -> None:
        # PushT action is 2-D (target pusher xy). We assert the shape so a
        # mis-wired env fails loud rather than silently broadcasting.
        if tuple(action_shape) != (2,):
            raise ValueError(
                f"_ClassicalPushTPolicy expects a 2-D action (target pusher xy), "
                f"got action_shape={action_shape!r}. This controller is PushT-specific."
            )
        self._action_shape = action_shape

    def reset(self) -> None:
        return None

    def __call__(self, obs: dict[str, Any] | NDArray[np.floating[Any]]) -> NDArray[np.float32]:
        ax, ay, bx, by, b_theta = self._read_state(obs)

        gx, gy = PUSHT_GOAL_XY

        # Block -> goal direction û (where we want the block to travel).
        dx, dy = gx - bx, gy - by
        dist = float(np.hypot(dx, dy))
        if dist < 1e-6:
            ux, uy = 0.0, 0.0
        else:
            ux, uy = dx / dist, dy / dist

        # The contact point we want to push from is *behind* the block,
        # on the side opposite the goal: behind = block - standoff*û.
        behind_x = bx - PUSHT_STANDOFF_PX * ux
        behind_y = by - PUSHT_STANDOFF_PX * uy

        # Two-phase push-behind. The single-target version (aim at the
        # behind point) never makes contact — the env's PD loop parks the
        # pusher *at* the behind point and stops. So we phase it:
        #
        #   APPROACH: if the pusher is not yet behind the block (it's off to
        #   the side or in front), drive to the behind point first so we line
        #   up on the goal-pointing contact normal.
        #   PUSH: once lined up behind, aim *through* the block toward the
        #   goal so the PD loop keeps driving the pusher into the block and
        #   the block ahead of it — block + push_dist*û past the centre.
        #
        # "Lined up" = pusher is on the far side from the goal (its
        # projection onto û is behind the behind point) AND roughly on the
        # push axis (small perpendicular offset).
        to_pusher_x, to_pusher_y = ax - bx, ay - by
        along = to_pusher_x * ux + to_pusher_y * uy  # >0 means goal-side of block
        perp_x, perp_y = -uy, ux  # unit normal to the push axis
        perp_off = abs(to_pusher_x * perp_x + to_pusher_y * perp_y)

        lined_up = along <= -0.5 * PUSHT_STANDOFF_PX and perp_off <= PUSHT_STANDOFF_PX

        if lined_up:
            # PUSH: aim a fixed distance past the block centre along û so the
            # pusher keeps bearing into the block toward the goal.
            target_x = bx + PUSHT_STANDOFF_PX * ux
            target_y = by + PUSHT_STANDOFF_PX * uy
        else:
            # APPROACH: go to the behind point to line up on the contact normal.
            target_x = behind_x
            target_y = behind_y

        # Orientation correction: signed shortest-angle error to the goal
        # heading, applied as a tangential (perpendicular-to-push) nudge so
        # the contact also torques the T toward π/4 rather than only
        # translating it. Only meaningful while pushing.
        if lined_up:
            theta_err = _wrap_to_pi(PUSHT_GOAL_THETA - b_theta)
            target_x += self._K_THETA * theta_err * perp_x
            target_y += self._K_THETA * theta_err * perp_y

        target = np.array([target_x, target_y], dtype=np.float32)
        np.clip(target, PUSHT_ACTION_LO, PUSHT_ACTION_HI, out=target)
        return target.reshape(self._action_shape)

    @staticmethod
    def _read_state(
        obs: dict[str, Any] | NDArray[np.floating[Any]],
    ) -> tuple[float, float, float, float, float]:
        """Extract ``(agent_x, agent_y, block_x, block_y, block_theta)``.

        Accepts the gym-pusht ``state`` observation: a flat 5-vector
        ``[agent_x, agent_y, block_x, block_y, block_angle]``. The bench
        wires this controller to the ``state`` obs type (see
        ``configs/envs.yaml`` ``pusht_state``), so the array path is the
        live one; a dict observation is rejected loudly because it means
        the env was wired with the wrong ``obs_type``.
        """
        if isinstance(obs, dict):
            raise RuntimeError(
                "classical_pusht expects the gym-pusht 'state' observation "
                "(flat 5-vector [agent_xy, block_xy, block_angle]); got a dict. "
                "Wire the env with gym_kwargs.obs_type='state' (see the "
                "'pusht_state' entry in configs/envs.yaml)."
            )
        arr = np.asarray(obs, dtype=np.float64).reshape(-1)
        if arr.size < 5:
            raise RuntimeError(
                f"classical_pusht needs a >=5-dim state observation "
                f"[agent_xy, block_xy, block_angle], got size {arr.size}"
            )
        return float(arr[0]), float(arr[1]), float(arr[2]), float(arr[3]), float(arr[4])


def _wrap_to_pi(angle: float) -> float:
    """Wrap a radian angle to ``(-π, π]`` for a signed shortest-angle error."""
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def load_classical_policy(
    name: str, *, action_shape: tuple[int, ...] | None
) -> _ClassicalPushTPolicy:
    """Resolve a classical-policy name to its callable.

    Mirrors the baseline dispatch in :func:`embodimetry.eval.load_policy`:
    ``action_shape`` comes from the env (not the policy spec) and is
    required. Raises ``ValueError`` for an unknown classical name so the
    registry and this dispatcher cannot silently drift.
    """
    if action_shape is None:
        raise ValueError(f"classical policy '{name}' requires action_shape (comes from the env)")
    if name == "classical_pusht":
        return _ClassicalPushTPolicy(action_shape)
    raise ValueError(f"unknown classical policy '{name}'")
