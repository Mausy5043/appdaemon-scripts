import appdaemon.plugins.hass.hassapi as hass  # pyright: ignore[reportMissingImports]

import const as cs
import utils as ut

# goto = "nom"
# self.log(f"\nset battery to {goto}\n")
# self.set_state(cs.ENT_BAT1_STRATEGY, f"{goto}")
# self.set_state(cs.ENT_BAT2_STRATEGY, f"{goto}")


def ramp(haas, s):
    haas.log(s)
    haas.run_in(haas.batteries.ramp, 60)