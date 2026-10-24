"""Continuous PI controller with back-calculation anti-windup (T005; research.md R8)."""

import math

import numpy as np
import pytest
from pydantic import ValidationError

from boidrytwin.control.pi import PIController, PISettings, not_reached_mask, smooth_clip


def _pi(**kw: object) -> PIController:
    base: dict[str, object] = {
        "gain": 2.0,
        "integral_time": 100.0,
        "output_min": 0.0,
        "output_max": 10.0,
        "not_reached_band": 1.0,
        "not_reached_hold": 60.0,
    }
    base.update(kw)
    return PIController(PISettings(**base))  # type: ignore[arg-type]


def test_settings_rules() -> None:
    for bad in ({"gain": 0.0}, {"integral_time": -1.0}, {"output_min": 5.0, "output_max": 5.0},
                {"manual_output": 20.0}, {"tracking_time": 0.0}):  # fmt: skip
        with pytest.raises(ValidationError):
            _pi(**bad)
    assert _pi().settings.effective_tracking_time == 100.0  # defaults to the integral time


def test_proportional_and_integral_action() -> None:
    pi = _pi()
    v, u = pi.output(setpoint=10.0, measurement=9.0, integral=3.0)
    assert v == pytest.approx(2.0 * 1.0 + 3.0) and u == pytest.approx(v, abs=1e-6)
    # unsaturated: dI/dt = Kc/Ti * e
    assert pi.integral_rate(10.0, 9.0, 3.0) == pytest.approx(2.0 / 100.0 * 1.0, rel=1e-6)


def test_direct_action() -> None:
    pi = _pi(action="direct")
    v, _ = pi.output(setpoint=10.0, measurement=11.0, integral=0.0)
    assert v == pytest.approx(2.0)


def test_smooth_saturation_bounds_and_bias() -> None:
    lo, hi, eps = 0.0, 10.0, 0.005
    v = np.linspace(-50, 60, 1001)
    u = smooth_clip(v, lo, hi, eps)
    assert np.all(u >= lo - 1e-12) and np.all(u <= hi + 1e-12)
    assert smooth_clip(hi, lo, hi, eps) == pytest.approx(
        hi - eps * (hi - lo) * math.log(2), rel=1e-9
    )
    assert smooth_clip(5.0, lo, hi, eps) == pytest.approx(5.0, abs=1e-9)


def test_exact_saturation_mode() -> None:
    pi = _pi(exact=True)
    _, u = pi.output(setpoint=100.0, measurement=0.0, integral=0.0)
    assert u == 10.0


def test_no_windup_after_long_saturation() -> None:
    pi = _pi()
    integral, dt = 0.0, 1.0
    # large positive error for a long time: output saturates at the maximum
    for _ in range(5000):
        integral += dt * pi.integral_rate(100.0, 0.0, integral)
    v, u = pi.output(100.0, 0.0, integral)
    assert u == pytest.approx(10.0, abs=0.1)
    assert v < 10.0 + 2.0 * 100.0 + 50.0  # integral did not grow without bound
    # error changes sign: the output leaves the limit within about one tracking time
    for _step in range(int(1.5 * 100)):
        integral += dt * pi.integral_rate(0.0, 1.0, integral)
    _, u_after = pi.output(0.0, 1.0, integral)
    assert u_after < 9.9


def test_manual_mode_tracks_and_switch_is_bumpless() -> None:
    pi = _pi(mode="manual", manual_output=4.0)
    integral, dt = 0.0, 1.0
    for _ in range(3000):
        integral += dt * pi.integral_rate(10.0, 8.0, integral)
    _, u_manual = pi.output(10.0, 8.0, integral)
    assert u_manual == pytest.approx(4.0)
    auto = _pi(mode="automatic")
    _, u_auto = auto.output(10.0, 8.0, integral)
    assert u_auto == pytest.approx(4.0, abs=0.01)  # no bump at the switch


def test_steady_state_initialisation() -> None:
    pi = _pi()
    integral = pi.initial_integral(output=6.0, setpoint=10.0, measurement=9.5)
    assert integral == pytest.approx(6.0 - 2.0 * 0.5)
    assert pi.output(10.0, 9.5, integral)[1] == pytest.approx(6.0, abs=1e-6)


def test_not_reached_mask_needs_hold_time() -> None:
    t = np.arange(0.0, 300.0, 10.0)
    error = np.where((t >= 50) & (t < 200), 2.0, 0.0)  # outside the 1.0 band for 150 s
    mask = not_reached_mask(t, error, band=1.0, hold=60.0)
    assert not mask[t < 110].any()  # not yet held for 60 s
    assert mask[(t >= 110) & (t < 200)].all()
    assert not mask[t >= 200].any()  # cleared when back inside the band
