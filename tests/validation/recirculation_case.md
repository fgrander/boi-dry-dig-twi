# Validation case: mixing the returned exhaust at the drum inlet (feature 004, SC-002)

Scenario: `examples/dryer_recirculation.toml` (reference dryer, constant flue gas, mixing
chamber at −200 Pa), steady state, last output sample.

## Fresh gas (inputs of the scenario)

| Stream | Value |
|---|---|
| flue gas | 8.0 kg/s wet, 650 °C, wet mole fractions N₂ 70.5 %, O₂ 6.0 %, CO₂ 10.5 %, H₂O 12.0 %, other 1.0 % |
| dilution air | 2.0 kg/s wet, ambient 10 °C, 70 % r.h., 101.3 kPa |

Per stream, on a dry gas basis:

- flue gas: mass fractions y from the mole fractions; water w = y_H₂O; dry gas
  8.0 (1 − w); water 8.0 w; enthalpy 8.0 · h(650 °C, y);
- air: humidity Y_air = 0.622-type ratio M_w/M_air · p_w / (p − p_w) with
  p_w = 0.7 p_sat(10 °C); dry gas 2.0 / (1 + Y_air); enthalpy per kg dry air
  h_air(10 °C) + Y_air h_w(10 °C).

## Returned gas (taken from the run's own results)

From the last results row: `recirculation_mass_flow` m_rec (wet), `exhaust_humidity` Y_out,
`exhaust_temperature` T_out (the returned gas has the drum outlet state; adiabatic duct):
G_rec = m_rec / (1 + Y_out); enthalpy per kg dry gas h_dry(T_out) + Y_out h_w(T_out), with
the dry composition of the fresh mix.

## Mix (the hand calculation)

    G = G_in + G_rec
    Y = (water_in + G_rec Y_out) / G
    H = (H_in + G_rec h_rec) / G
    T: h(T, Y) = H, by bisection
    x_O2 = n_O2 / (n_dry + n_H2O)   with n from the dry mass fractions and Y

Enthalpies: the species sensible enthalpies of `boidrytwin.properties.gas` (NASA 7-term
polynomials, McBride et al. 2002; relative to 25 °C), the same table the model uses; the
check is of the mixing and inversion, not of the property data.

## Acceptance (SC-002)

| Quantity | Tolerance |
|---|---|
| drum inlet temperature | 0.5 K |
| drum inlet humidity | 1 % relative |
| drum inlet O₂ mole fraction | 1 % relative |

Also: the mixing chamber pressure from a hand solve of the gas path (stack resistance, fan
curve, drum path resistance) at the run's damper position and flows is within 1 Pa of the
result (research R2), and it lies within 50 Pa of the −200 Pa set point.
