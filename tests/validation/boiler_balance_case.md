# Boiler house hand balance (T021, SC-002)

Steady state of `examples/boiler_house_only.toml` (controllers in automatic).

**(a) Oil side**: duty = ṁ_oil · [h_oil(T_outlet) − h_oil(T_return)], with h_oil the integral
of the Shell S2 c_p fit (`properties.thermal_oil`, independent of the heater model). The model's
`heat_to_oil` (sum of wall-to-oil heat in all heater nodes) must agree within 1 %.

**(b) Gas side**: with the fuel burnout B (kg dry/s) and the evaporation equal to the water fed
at steady state, the energy entering the gas is

    B·LHV_d + ṁ_fuel·[(1−w)·h_dry,wood(T_fuel) + w·h_liquid(T_fuel)] + H_air − B·ash·h_ash

and the flue gas enthalpy leaving towards the dryer is that, minus the oil duty from (a), minus
the losses reported by the model (refractory, casings). Dividing by the flue gas mass flow and
inverting the NASA-polynomial enthalpy gives the hand temperature, which must agree with
`gas_temperature_after_heater_3` within 5 K.
