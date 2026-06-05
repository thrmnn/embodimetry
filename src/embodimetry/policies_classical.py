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

# ------------------------------------------------------------------------- #
# PushT geometry (gym_pusht.envs.pusht.PushTEnv).                            #
# ------------------------------------------------------------------------- #
# The goal pose is hard-coded at reset and never changes across episodes, so
# the controller treats it as a fixed target (it is not in the `state` obs
# vector). Goal: place the block body origin at (256, 256) with heading π/4.
PUSHT_GOAL_XY: tuple[float, float] = (256.0, 256.0)
PUSHT_GOAL_THETA: float = float(np.pi / 4.0)

# Action space is the target agent (pusher) position in [0, 512]^2; the env's
# internal PD loop drives the pusher toward whatever target we emit.
PUSHT_ACTION_LO: float = 0.0
PUSHT_ACTION_HI: float = 512.0

# Agent (pusher) radius in px — needed to stand the pusher *just off* a block
# face rather than inside it (gym_pusht adds a circle of radius 15).
PUSHT_AGENT_RADIUS: float = 15.0

# The T-block (scale=30): a 120×30 horizontal bar with a 30×90 vertical stem
# hanging below it. The body origin reported in the obs is the centre of the
# bar's top edge; the centre of gravity — which pymunk rotates the block about
# — sits at local (0, 45). Knowing the COG (not the body origin) is what lets
# the controller push *through* the rotation centre to translate cleanly and
# torque about it to rotate. Local frame: +y points down the stem.
PUSHT_COG_LOCAL: NDArray[np.float64] = np.array([0.0, 45.0], dtype=np.float64)

# The four pushable faces of the T as (local contact point, local outward
# normal). To translate the block we bear on whichever face's outward normal
# best opposes the desired travel direction — a flat-face contact is far more
# stable than driving a circle into the centroid, which squirts the T sideways.
#   - bar back edge (y=0, normal -y): the long flat back of the top bar
#   - stem tip (y=120, normal +y): the bottom end of the stem
#   - bar right / left ends (x=±60, normal ±x)
_PUSHT_FACES: tuple[tuple[NDArray[np.float64], NDArray[np.float64]], ...] = (
    (np.array([0.0, 0.0]), np.array([0.0, -1.0])),
    (np.array([0.0, 120.0]), np.array([0.0, 1.0])),
    (np.array([60.0, 7.5]), np.array([1.0, 0.0])),
    (np.array([-60.0, 7.5]), np.array([-1.0, 0.0])),
)

# The rotation lever: the stem tip, local (0, 120). It is the point on the T
# furthest from the COG, so a tangential push there produces the most torque
# per unit of (unavoidable) translation a single circular pusher imparts.
_PUSHT_ROT_LEVER_LOCAL: NDArray[np.float64] = np.array([0.0, 120.0], dtype=np.float64)


def _rot(theta: float) -> NDArray[np.float64]:
    """2×2 rotation matrix (block-local → world)."""
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s], [s, c]], dtype=np.float64)


class _ClassicalPushTPolicy:
    """Scripted translate-then-rotate controller for gym-pusht (L2 reference).

    PushT asks for a *simultaneous* position and orientation match: the
    ``coverage > 0.95`` success bar is only met when the T's footprint
    overlaps the goal-pose footprint almost perfectly, which needs both the
    centroid within a few px *and* the heading within a few degrees of π/4. A
    single circular pusher cannot apply a pure torque, so every rotation drags
    the centroid and every translation perturbs the heading — the two
    objectives fight. A competent classical controller therefore *sequences*
    them rather than chasing both at once.

    Strategy (deterministic given the env seed — no internal RNG):

    1. Read the agent ``(ax, ay)``, block body origin ``(bx, by)`` and block
       heading ``b_theta`` from the ``state`` obs. Reconstruct the block's
       **centre of gravity** in world coords (the point pymunk rotates about):
       ``cog = block_origin + R(b_theta) · (0, 45)``. The goal centroid is the
       same offset applied to the fixed goal pose.

    2. **Contact model — pick which face of the T to push.** This is the key
       upgrade over a naive push-behind. The T has four flat faces; bearing on
       a flat face is stable, whereas driving the circular pusher at the
       centroid squirts the block sideways. For translation we choose the face
       whose outward normal most opposes the desired travel direction, stand
       the pusher just off it, then press in along the inward normal — a clean
       push through the COG.

    3. **Translate-then-rotate sub-goal sequencing** (re-evaluated every step,
       so the dominant-error axis can flip and the controller re-sequences):

       * **TRANSLATE** (coarse) — while the centroid is far from the goal
         centroid, push the chosen face to drive the COG toward the goal.
       * **ROTATE** — once the centroid is close, correct the heading by
         pushing the *stem tip* (the longest lever) tangentially, in the
         direction that reduces the signed shortest-angle error. The pusher
         **lines up off the lever before it presses** (it never cuts across
         the block in transit, which would knock it away), and the press
         magnitude scales with the remaining angle error so a nearly-aligned
         block gets a feather-tap, not a shove that flings it out of place.
       * **FINE TRANSLATE** — after the rotation inevitably nudges the
         centroid, a gentle low-press re-centre brings it back before settling.
       * **SETTLE** — when both errors are inside tolerance, hold position and
         let the block come to rest.

    4. Emit the resulting target pusher position, clipped to ``[0, 512]^2``.

    This is a sensible, documented classical baseline — *not* an optimal
    controller. Pushing is genuinely hard: it is non-prehensile, underactuated
    and contact-unstable, and a single pusher cannot decouple translation from
    rotation. On a held-out 5-seed × 50-ep eval this controller drives the
    block to within a few percent of the bar on its best episodes (per-episode
    max coverage tops out around ~0.92) but cannot reliably clear the strict
    ``coverage > 0.95`` window — see the measured max-coverage distribution in
    the PR body. That near-miss plateau *is* the honest L2 number: it shows how
    close a competent scripted controller gets without a learned policy, which
    is exactly what makes the cross-rung comparison legible rather than a
    strawman.

    Stateless: ``reset`` is a no-op and the action is a pure function of the
    current observation, so a fixed seed reproduces the rollout bit-for-bit
    through the eval loop's seeding contract.
    """

    # Sub-goal switch thresholds. Hand-set to a sensible regime from a short
    # development sweep (1-seed × 20-ep loops), NOT exhaustively optimised.
    _POS_TOL_PX: float = 10.0  # centroid within this → stop coarse translating
    _POS_FINE_TOL_PX: float = 4.0  # centroid within this → stop fine-translating
    _THETA_TOL_RAD: float = float(np.radians(2.0))  # heading within this → settle
    # Press depth (how far past the contact face to aim, in px) by phase. A
    # deeper aim drives the pusher in harder; the fine/rotate phases are gentle.
    _PRESS_COARSE_FAR_PX: float = 12.0
    _PRESS_COARSE_NEAR_PX: float = 8.0
    _PRESS_FINE_PX: float = 5.0
    _PRESS_RAMP_PX: float = 22.0  # centroid distance below which coarse press eases off
    # Rotation press scales with |angle error|, clamped to this band so a
    # near-aligned block is feathered and a badly-rotated one is driven.
    _ROT_PRESS_GAIN: float = 30.0
    _ROT_PRESS_MIN_PX: float = 2.5
    _ROT_PRESS_MAX_PX: float = 9.0
    # "Lined up" tolerances for committing to a press without a transit knock.
    _STANDOFF_MARGIN_PX: float = 5.0  # extra gap beyond the agent radius
    _ALONG_SLACK_PX: float = 6.0  # how far past the standoff counts as lined-up
    _PERP_TOL_COARSE_PX: float = 26.0
    _PERP_TOL_FINE_PX: float = 20.0

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
        agent = np.array([ax, ay], dtype=np.float64)
        origin = np.array([bx, by], dtype=np.float64)
        R = _rot(b_theta)

        cog = origin + R @ PUSHT_COG_LOCAL
        goal_cog = (
            np.array(PUSHT_GOAL_XY, dtype=np.float64) + _rot(PUSHT_GOAL_THETA) @ PUSHT_COG_LOCAL
        )
        pos_err = goal_cog - cog
        pos_dist = float(np.linalg.norm(pos_err))
        theta_err = _wrap_to_pi(PUSHT_GOAL_THETA - b_theta)
        push_dir = pos_err / (pos_dist + 1e-9)

        if pos_dist > self._POS_TOL_PX:
            # COARSE TRANSLATE: drive the centroid toward the goal centroid.
            target = self._translate_target(agent, origin, R, push_dir, pos_dist, fine=False)
        elif abs(theta_err) > self._THETA_TOL_RAD:
            # ROTATE: torque the T toward the goal heading about its COG.
            target = self._rotate_target(agent, origin, R, cog, theta_err)
        elif pos_dist > self._POS_FINE_TOL_PX:
            # FINE TRANSLATE: re-centre after the rotation nudged the centroid.
            target = self._translate_target(agent, origin, R, push_dir, pos_dist, fine=True)
        else:
            # SETTLE: both errors inside tolerance — hold and let the block rest.
            target = agent

        out = target.astype(np.float32)
        np.clip(out, PUSHT_ACTION_LO, PUSHT_ACTION_HI, out=out)
        return out.reshape(self._action_shape)

    def _translate_target(
        self,
        agent: NDArray[np.float64],
        origin: NDArray[np.float64],
        R: NDArray[np.float64],
        push_dir: NDArray[np.float64],
        pos_dist: float,
        *,
        fine: bool,
    ) -> NDArray[np.float64]:
        """Pick the best face to push and return the pusher target.

        Chooses the T face whose outward normal most opposes ``push_dir`` (the
        most stable face to bear on for travel in that direction), stands off
        it if not yet lined up, else presses in along the inward normal. The
        coarse press ramps down as the centroid nears the goal so the pusher
        eases off rather than overshooting; the fine phase is gentler still.
        """
        face_center, face_normal = self._best_translate_face(origin, R, push_dir)
        standoff = face_center + face_normal * (PUSHT_AGENT_RADIUS + self._STANDOFF_MARGIN_PX)
        tangent = np.array([-face_normal[1], face_normal[0]])
        perp_off = abs(float((agent - face_center) @ tangent))
        along = float((agent - standoff) @ (-face_normal))  # >0 = on the push side
        perp_tol = self._PERP_TOL_FINE_PX if fine else self._PERP_TOL_COARSE_PX

        if along < -self._ALONG_SLACK_PX or perp_off > perp_tol:
            return standoff  # line up behind the face first
        if fine:
            press = self._PRESS_FINE_PX
        elif pos_dist > self._PRESS_RAMP_PX:
            press = self._PRESS_COARSE_FAR_PX
        else:
            press = self._PRESS_COARSE_NEAR_PX
        return face_center - face_normal * press

    def _best_translate_face(
        self,
        origin: NDArray[np.float64],
        R: NDArray[np.float64],
        push_dir: NDArray[np.float64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """The face whose world outward normal best opposes ``push_dir``."""
        best_score = -np.inf
        best: tuple[NDArray[np.float64], NDArray[np.float64]] | None = None
        for center_local, normal_local in _PUSHT_FACES:
            fc = origin + R @ center_local
            fn = R @ normal_local
            score = float(fn @ (-push_dir))
            if score > best_score:
                best_score = score
                best = (fc, fn)
        assert best is not None
        return best

    def _rotate_target(
        self,
        agent: NDArray[np.float64],
        origin: NDArray[np.float64],
        R: NDArray[np.float64],
        cog: NDArray[np.float64],
        theta_err: float,
    ) -> NDArray[np.float64]:
        """Push the stem tip tangentially to torque the T toward the goal heading.

        Lines the pusher up off the lever before committing to a press (so it
        never cuts across the block in transit), then presses tangentially with
        a magnitude that scales with the remaining angle error.
        """
        sign = 1.0 if theta_err > 0 else -1.0
        lever = origin + R @ _PUSHT_ROT_LEVER_LOCAL
        radial = lever - cog
        radial_norm = float(np.linalg.norm(radial)) + 1e-9
        radial_hat = radial / radial_norm
        tangent = np.array([-radial[1], radial[0]]) / radial_norm * sign
        standoff = lever - tangent * (PUSHT_AGENT_RADIUS + self._STANDOFF_MARGIN_PX)
        perp_off = abs(float((agent - lever) @ radial_hat))
        along = float((agent - standoff) @ tangent)
        lined_up = along >= -self._ALONG_SLACK_PX and perp_off <= self._PERP_TOL_FINE_PX

        if not lined_up:
            return standoff  # line up off the lever first — no transit knock
        press = float(
            np.clip(
                abs(theta_err) * self._ROT_PRESS_GAIN,
                self._ROT_PRESS_MIN_PX,
                self._ROT_PRESS_MAX_PX,
            )
        )
        return lever + tangent * press

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
