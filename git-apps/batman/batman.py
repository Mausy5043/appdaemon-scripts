from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs

"""BatMan App
Listen to changes in the battery state and control the charging/discharging based on energy prices and strategies.
"""


class BatMan(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        self.log(f"===================================== BatMan v{cs.VERSION} ====")
        # Keep track of active callbacks
        self.callback_handles: list[Any] = []
        self.votes: dict[str, list] = {}

    def terminate(self):
        """Clean up app."""
        self.log("__Terminating BatMan...")
        # some cleanup code goes here
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("__...terminated BatMan.")

    def tell(self, caller: str, message: str):
        """Log a message."""
        self.log(f"_BatMan: {caller} said {message}")

    def vote(self, caller: str, vote: list[str], veto: bool = False):
        self.log(f"_BatMan: {caller} voted \t\t\t : {vote}")
        self.votes[caller] = vote

        self.log("_BatMan:  votes sofar:")
        for _k, _v in self.votes.items():
            self.log(f"_______: \t{_k}:\t{_v}")
        # do this via a callback:
        self.judge()

    def judge(self):
        tally: dict[str, int] = cs.TALLY.copy()
        for _k, votes in self.votes.items():
            for vote in votes:
                if "API" in vote:
                    vote = self.api_pos_or_neg(vote.split(",")[1])
                tally[vote] += 1
        self.log(f"{tally} => {max(tally, key=lambda k: tally[k])}")

    def api_pos_or_neg(self, reqpwr: str):
        pon = "NOM"
        try:
            pwr = int(reqpwr)
            if pwr < 0:
                pon = "API-"
            if pwr > 0:
                pon = "API+"
        except ValueError:
            pass
        return pon


"""
SoC > 75% || summerday |-> = discharge to 25%
SoC < __% || winterday |-> = charge to 100%

definition of summerday = 1st of May to 30th of September
 winterday = 1st of October to 30th of April

sensor.pv_kwh_meter_current <= +/-21 A
sensor.pv_kwh_meter_power <= +/-5000 W

EV assist while charging when price > Q3

Default requirements:
- default stance = NOM
- sensor.bats_minimum_soc = SoC required to provide 200 W (input_number.home_baseload) until 10:00 next morning (sensor.hours_till_10am)
- battery contents is available to the home
- only when surplus is high, battery contents may be offloaded

NOM:
default stance

API- (charge)
- greedy: price < nul
- winter: cheap hours & SoC < sensor.bats_minimum_soc

API+ (discharge)
- greedy: price > top
- EV is charging & price > Q3 & SoC > sensor.bats_minimum_soc

IDLE:
- EV is charging

 """
