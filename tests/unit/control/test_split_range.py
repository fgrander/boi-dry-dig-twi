"""Split range bypass/dilution (T006; research.md R8)."""

import numpy as np
import pytest

from boidrytwin.control.split_range import split


def test_low_output_opens_the_bypass() -> None:
    bypass, dilution = split(0.1, s=0.5, max_dilution=6.0)
    assert bypass == pytest.approx((0.5 - 0.1) / 0.5)
    assert dilution == 0.0


def test_high_output_opens_dilution() -> None:
    bypass, dilution = split(0.8, s=0.5, max_dilution=6.0)
    assert bypass == 0.0
    assert dilution == pytest.approx((0.8 - 0.5) / 0.5 * 6.0)


def test_never_both_open_and_continuous() -> None:
    u = np.linspace(0.0, 1.0, 2001)
    bypass, dilution = split(u, s=0.3, max_dilution=4.0)
    assert not np.any((bypass > 0) & (dilution > 0))
    assert split(0.3, s=0.3, max_dilution=4.0) == (0.0, 0.0)
    assert bypass[0] == pytest.approx(1.0) and dilution[-1] == pytest.approx(4.0)


@pytest.mark.parametrize("s", [0.0, 1.0, -0.2])
def test_split_value_must_be_inside(s: float) -> None:
    with pytest.raises(ValueError, match="0 < s < 1"):
        split(0.5, s=s, max_dilution=1.0)
