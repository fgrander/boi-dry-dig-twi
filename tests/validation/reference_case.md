# Reference case: hand balance of the steady state (T049)

**Scenario**: `examples/reference_constant.toml`. 10 t/h wet chips at 50 % wet basis and
10 °C; flue gas 8.0 kg/s at 650 °C, 101.0 kPa, wet mole fractions N₂ 70.5 %, O₂ 6.0 %,
CO₂ 10.5 %, H₂O 12.0 %, other 1.0 %; dilution air 2.0 kg/s at 10 °C, 70 % RH.

## Purpose

A mass and energy balance by hand cannot predict the outlet moisture: that depends on the
drying kinetics and residence time, which are model results. The hand calculation therefore
**fixes the product outlet moisture and product temperature at the model's steady-state
values** and derives everything a balance does determine. Independent prediction of outlet
moisture is tested with literature data in T079.

## Derivation

All enthalpies are sensible, relative to 298.15 K, from the same property functions the
model uses (`properties.gas`, `properties.water`, `properties.wood`), but evaluated here
outside the model.

1. **Feed**: dry solids F = 10 000 / 3600 × (1 − 0.5) = 1.3889 kg/s; X_in = 0.5 / 0.5 = 1.0.
2. **Flue gas**: mass fractions y = mass_fractions(x); water w = y_H2O; dry flue gas
   G_fg = 8.0 (1 − w).
3. **Dilution air**: p_w = 0.70 p_sat(283.15 K); Y_air = (M_w / M_air) p_w / (p − p_w);
   dry air G_air = 2.0 / (1 + Y_air).
4. **Inlet gas**: G = G_fg + G_air; Y_in = (8.0 w + G_air Y_air) / G;
   G H_in = 8.0 h(T_fg, y) + G_air (h_air(T_a) + Y_air h_v(T_a)) — this is also the heat
   supplied Q_in.
5. **Evaporation**: X_out = w_out / (1 − w_out); E = F (X_in − X_out).
6. **Exhaust humidity**: Y_ex = Y_in + E / G.
7. **Exhaust temperature** from the steady energy balance of the whole drum:

   G H(T_ex, Y_ex) = G H_in + F e(T_feed, X_in) − F e(T_p, X_out) − Q_loss

   with e the moist-wood enthalpy per kg dry wood and Q_loss the shell loss reported by the
   model. Solved for T_ex by bisection.
8. **Specific energy**: Q_in / E.

## Tolerances

| Quantity | Tolerance |
|---|---|
| evaporation | ±0.5 % |
| exhaust temperature | ±2 K |
| exhaust humidity | ±1 % |
| specific energy | ±2 % |

Above fibre saturation the moist-wood enthalpy is linear in X, so averaging the two solids
phases at the outlet introduces no error.
