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
        self.stance: str = cs.DEFAULT_STANCE
        self.price: dict = {
            "today": [],
            "tomor": [],
            "now": 0.0,
            "cheap_hour": [],
            "expen_hour": [],
            "stats": {},
        }
        self.get_price_states()
        # various monitors
        self.ev_assist = cs.EV_ASSIST
        self.ev_charging: bool = False
        self.ctrl_by_me: bool = True  # whether the app is allowed to control the batteries
        self.bats_min_soc: float = 0.0
        self.pv_current: float = 0.0  # A
        self.pv_power: int = 0  # W
        self.soc: float = 0.0  # % average state of charge
        self.soc_list: list[float] = []  # % state of charge for each battery
        self.update_states()

        self.set_call_backs()

        # start in NOM stance
        self.start_nom()

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

    def get_soc(self) -> tuple[float, list[float]]:
        """Get current state of charge (SoC) for all batteries."""
        soc_list: list[float] = []
        for bat in cs.BATTERIES:
            _soc: Any | None = self.get_state(entity_id=bat, attribute="state")
            if _soc is not None:
                soc_list.append(float(_soc))
            else:
                soc_list.append(0.0)
        soc_now: float = sum(soc_list) / len(soc_list) if soc_list else 0.0
        return soc_now, soc_list

    def update_states(self):
        """Update internal states based on current conditions."""
        self.log("--------------------------- v ------------------------")
        # update the current date
        self.datum = ut.get_these_days()
        # minimum SoC required to provide power until 10:00 next morning
        _bms: Any = self.get_state(cs.BAT_MIN_SOC)
        self.bats_min_soc =  float(_bms)
        self.log(f"BAT minimum SoC             = {self.bats_min_soc:.1f} %")
        # get current SoC
        self.soc, self.soc_list = self.get_soc()
        self.log(f"BAT current SoC             = {self.soc:.1f} %. <- {self.soc_list}")
        # get PV current and power values
        _pvc: Any = self.get_state(cs.PV_CURRENT)
        self.pv_current = float(_pvc)
        self.log(f"PV actual current           = {self.pv_current:.1f} A")
        _pvp: Any = self.get_state(cs.PV_POWER)
        self.pv_power = float(_pvp)
        self.log(f"PV actual power             = {self.pv_power:.1f} W")
        # check if we are greedy (price must have been updated already!)
        self.greedy = ut.get_greedy(self.price["now"])
        match self.greedy:
            case -1:
                _s = "greedy to charge"
            case 1:
                _s = "greedy for discharge"
            case _:
                _s = "not greedy"
        self.log(f"Greed                       = {_s}")
        # check whether the EV is currently charging
        _evc: Any = self.get_state(cs.EV_REQ_PWR)
        self.ev_charging = False
        if str(_evc) == "on":
            self.ev_charging = True
        if self.ev_charging:
            self.log(f"EV charging                 = {str(_evc).upper()}")
        # check if we are going to assist the EV
        self.ev_assist = cs.EV_ASSIST
        if self.price["now"] > self.price["stats"]["q3"]:
            self.ev_assist = True
        if self.ev_assist:
            self.log("EV assist                   = ENABLED")
        _ctrl: Any = self.get_state(cs.CTRL_BY_ME)
        self.ctrl_by_me = False
        if str(_ctrl) == "on":
            self.ctrl_by_me = True
        if self.ctrl_by_me:
            self.log("Control by app              = ENABLED")
        else:
            self.log("Control by app              = DISABLED")
        self.log("--------------------------- ^ ------------------------")

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
        self.update_states()
        # log the current price
        if self.debug:
            self.log(f"New current price           = {_p:.3f}")

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
                }\n :   expensive hours = {self.price['expen_hour']}\n :   STATISTICS\n :     {
                    self.price['stats']['text']
                }"
            )
            self.log(f"New pricelist for tomorrow = {self.price["tomor"]}")

    # CONTROL LOGIC

    def choose_stance(self):
        """Choose the current stance based on the current price and battery state."""
        # Get the current state of the battery
        # soc = self.get_state(cs.BATTERY["entity"], attribute=cs.BATTERY["attr"]["soc"])
        # soc = float(soc) if soc else 0.0

        # Decide stance based on price and SoC
        # if self.stance == cs.NOM:
        #     if self.greedy == -1 or (self.price["now"] < self.price["stats"]["nul"] and soc < cs.BAT_MIN_SOC):
        #         self.start_charge()
        #     elif self.greedy == 1 or (
        #         self.ev_assist and self.price["now"] > self.price["stats"]["q3"] and soc > cs.BAT_MIN_SOC
        #     ):
        #         self.start_discharge()
        #     else:
        #         self.start_idle()
        # elif self.stance == cs.IDLE:
        #     if self.greedy == -1 or (self.price["now"] < self.price["stats"]["nul"] and soc < cs.BAT_MIN_SOC):
        #         self.start_charge()
        #     elif self.greedy == 1 or (self.ev_assist and self.price["now"] > cs.PRICE_Q3 and soc > cs.BAT_MIN_SOC):
        #         self.start_discharge()
        #     else:
        #         pass

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

o sensor.pv_kwh_meter_current <= +/-21 A
o sensor.pv_kwh_meter_power <= +/-5000 W

EV assist when price > Q3

Default requirements:
o default stance = NOM
o sensor.bats_minimum_soc = SoC required to provide 200 W (input_number.home_baseload) until 10:00 next morning (sensor.hours_till_10am)
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
