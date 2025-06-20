
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
        self.debug: bool = cs.DEBUG
        self.greedy: int = 0  # 0 = not greedy, 1 = greedy hi price, -1 = greedy low price
        self.datum: dict = ut.get_these_days()
        self.price: dict = {
            "today": [],
            "tomor": [],
            "now": 0.0,
            "cheap_hour": [],
            "expen_hour": [],
            "stats": {},
        }
        self.stance: str = cs.DEFAULT_STANCE
        self.get_price_states()
        self.set_call_backs()
        self.ev_assist = cs.EV_ASSIST

    def set_call_backs(self):
        # Set-up callbacks for price changes
        self.callback_handles.append(
            self.listen_state(self.price_list_cb, cs.PRICES["entity"], attribute=cs.PRICES["attr"]["list"])
        )
        self.callback_handles.append(
            self.listen_state(self.price_current_cb, cs.PRICES["entity"], attribute=cs.PRICES["attr"]["now"])
        )

    def get_price_states(self):
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
        _p = ut.total_price([float(new)])[0]
        self.price["now"] = _p
        # every time the current price changes, we update other stuff too:
        self.datum = ut.get_these_days()

        # check if we are greedy
        self.greedy = ut.get_greedy(_p)
        _s = "greedy for low price" if self.greedy == -1 else "greedy for high price" if self.greedy == 1 else "not greedy"
        # check if we are going to assist the EV
        if _p > self.price["stats"]["Q3"]:
            self.ev_assist = True
        else:
            self.ev_assist = cs.EV_ASSIST
        # log the current price
        if self.debug:
            self.log(f"New current price          = {_p:.3f} ({_s})")
            if self.ev_assist:
                self.log("EV assist                   = ENABLED")

    def price_list_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for price list change."""
        # update dates
        self.datum = ut.get_these_days()
        # update prices
        _p = ut.total_price(new[self.datum["today"].strftime("%Y-%m-%d")])
        self.price["today"] = _p
        self.price["stats"] = ut.price_statistics(_p)
        # make a list of cheap and expensive hours
        charge_today = ut.sort_index(_p, rev=True)[-3:]
        charge_today.sort()
        discharge_today = ut.sort_index(_p, rev=True)[:3]
        discharge_today.sort()
        self.price["cheap_hour"] = charge_today
        self.price["expen_hour"] = discharge_today
        
        # update tomorrow's prices
        self.price["tomor"] = ut.total_price(new[self.datum["tomor"].strftime("%Y-%m-%d")])
        if self.debug:
            self.log(
                f"New pricelist for today    = {self.price["today"]}\n :   cheap hours     = {
                    self.price['cheap_hour']
                }\n :   expensive hours = {self.price['expen_hour']}\n :   STATISTICS\n :     {self.price['stats']['text']}"
            )
            self.log(f"New pricelist for tomorrow = {self.price["tomor"]}")

    # CONTROL LOGIC

    def start_nom(self):
        """Start the NOM stance."""
        self.stance = cs.NOM
        self.log(f"Starting BatMan2 in {self.stance} stance.")

    def start_idle(self):
        """Start the IDLE stance."""
        self.stance = cs.IDLE
        self.log(f"Starting BatMan2 in {self.stance} stance.")

    def start_charge(self, power: int = cs.CHARGE_PWR):
        """Start the API- stance."""
        self.stance = cs.CHARGE
        self.log(f"Starting BatMan2 in {self.stance} stance.")

    def start_discharge(self, power: int = cs.DISCHARGE_PWR):
        """Start the API+ stance."""
        self.stance = cs.DISCHARGE
        self.log(f"Starting BatMan2 in {self.stance} stance.")


"""
sunnyday = march equinox to september equinox

sensor.pv_kwh_meter_current <= +/-21 A
sensor.pv_kwh_meter_power <= +/-5000 W

EV assist when price > Q3

Default requirements:
- default stance = NOM
- sensor.bats_minimum_soc = SoC required to provide 200 W (input_number.home_baseload) until 10:00 next morning (sensor.hours_till_10am)
- battery contents is available to the home
- only when surplus is high, battery contents may be offloaded

NOM:
default stance

IDLE:
- EV_charging (automation)

API- (charge) START @:
|| greedy: price < nul
|| !sunnyday && SoC < sensor.bats_minimum_soc && cheap_hours
STOP @ SoC = 100%

API+ (discharge) START @:
|| greedy: price > top
|| EV_charging && EV_assist && price > Q3 && SoC > sensor.bats_minimum_soc
|| sunnyday && SoC > __ % && expen_hours
STOP @ SoC = sensor.bats_minimum_soc

 """
