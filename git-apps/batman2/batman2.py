import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const2 as cs
import utils2 as ut

"""BatMan2 App
Listen to changes in the battery state and control the charging/discharging based on energy prices and strategies.
"""


class BatMan2(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        self.log(f"===================================== BatMan2 v{cs.VERSION} ====")
        # Keep track of active callbacks
        self.callback_handles: list[Any] = []

        # create internals
        self.debug = cs.DEBUG
        self.datum = {
            "today": dt.date.today(),
            "tomor": dt.date.today() + dt.timedelta(days=1),
            "sunny": ut.is_sunny_day(dt.date.today()),
        }
        self.price = {
            "today": [],
            "tomor": [],
            "now": 0.0,
        }
        self.stance = cs.DEFAULT_STANCE
        self.get_states()
        self.set_call_backs()

    def set_call_backs(self):
        # Set-up callbacks for price changes
        self.callback_handles.append(
            self.listen_state(self.price_list_cb, cs.PRICES["entity"], attribute=cs.PRICES["attr"]["list"])
        )
        self.callback_handles.append(
            self.listen_state(self.price_current_cb, cs.PRICES["entity"], attribute=cs.PRICES["attr"]["now"])
        )

    def get_states(self):
        # Get current states for prices
        self.price_list_cb(
            "entity", "list", "none", self.get_state(cs.PRICES["entity"], attribute=cs.PRICES["attr"]["list"])
        )
        self.price_current_cb(
            "entity", "list", "none", self.get_state(cs.PRICES["entity"], attribute=cs.PRICES["attr"]["now"])
        )

    def terminate(self):
        """Clean up app."""
        self.log("__Terminating BatMan2...")
        # some cleanup code goes here
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("__...terminated BatMan2.")

    # CALLBACKS

    def price_current_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for current price change."""
        self.price["now"] = ut.total_price([float(new)])[0]
        if self.debug:
            self.log(f"New price = {self.price['now']:.5f}")

    def price_list_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for price list change."""
        # update dates
        self.datum = {
            "today": dt.date.today(),
            "tomor": dt.date.today() + dt.timedelta(days=1),
            "sunny": ut.is_sunny_day(dt.date.today()),
        }
        # update prices
        self.price["today"] = ut.total_price(new[self.datum["today"].strftime("%Y-%m-%d")])
        self.price["tomor"] = ut.total_price(new[self.datum["tomor"].strftime("%Y-%m-%d")])
        if self.debug:
            self.log(f"New pricelist for today    = {self.price["today"]}")
            self.log(f"New pricelist for tomorrow = {self.price["tomor"]}")


"""
SoC > 75% || sunnyday |-> = discharge to 25%
SoC < __% || !sunnyday |-> = charge to 100%

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
