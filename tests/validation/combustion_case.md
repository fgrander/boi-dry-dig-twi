# Combustion reference case (T020, SC-001)

**Fuel**: default wood chips (VTT Technology 272, forest residue chips): C 51.3, H 6.1, N 0.4,
S 0.02, ash 1.3 wt% dry, O by difference (40.88). Moisture 45 % wet basis.
**Air**: 20 °C, 60 % RH, 101.3 kPa (humidity Y from IAPWS-IF97 saturation).
**Excess air**: λ such that the dry flue gas holds 7.0 vol% O₂.

Hand calculation per kg dry fuel (molar, atomic masses as in `properties.fuel`):

1. n_C = 0.513/0.012011, n_H₂ = 0.061/0.002016, n_O₂,fuel = 0.4088/0.031998,
   n_N₂,fuel = 0.004/0.028014, n_S = 0.0002/0.03206.
2. O₂,min = n_C + ½ n_H₂ + n_S − n_O₂,fuel.
3. Dry air moles A = λ·O₂,min/0.2095 (dry air: N₂ 78.08, O₂ 20.95, CO₂ 0.04, Ar 0.93 %).
4. Products: CO₂ = n_C + 0.0004 A; H₂O = n_H₂ + X/0.018015 + A·M_air·Y/0.018015 with X = w/(1−w);
   N₂ = 0.7808 A + n_N₂,fuel; O₂ = (λ − 1)·O₂,min; Ar = 0.0093 A (+ SO₂ as mass-equivalent Ar).
5. λ from 7 % dry O₂: O₂,dry = (λ−1)·O₂,min / (dry moles(λ)), linear in λ → solved exactly.
6. Flue gas mass flow = burnout × (Σ moles·M) per kg dry fuel.

The test computes these steps independently of `properties.fuel` (own formulas, same constants)
and compares with the furnace flue gas of the steady boiler house model (O₂ loop at 7 %).
Tolerances: composition ±0.1 percentage point (vol), flow ±0.1 %.
