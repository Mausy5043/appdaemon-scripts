import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const2 as cs
import prices2 as p2
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
        self.secrets = self.get_app("scrts")
        self.greedy: int = 0  # 0 = not greedy, 1 = greedy hi price, -1 = greedy low price
        self.datum: dict = ut.get_these_days()
        self.stance: str = cs.DEFAULT_STANCE
        self.tibber_prices: list[dict] = []
        self.tibber_quarters: bool = False  # whether the Tibber prices are quarterly or not
        self.price: dict = {
            "today": [],
            "tomor": [],
            "now": 0.0,
            "cheap_hour": [],
            "expen_hour": [],
            "stats": {},
        }
        # initialise various monitors
        self.ev_assist = cs.EV_ASSIST
        self.ev_charging: bool = False
        self.ctrl_by_me: bool = True  # whether the app is allowed to control the batteries
        self.bats_min_soc: float = 0.0
        self.pv_current: float = 0.0  # A; used to monitor PV overcurrent
        self.pv_volt: float = 0.0  # V; used to control PV current
        self.pv_power: int = 0  # W
        self.soc: float = 0.0  # % average state of charge
        self.soc_list: list[float] = [0.0, 0.0]  # %; state of charge for each battery
        self.pwr_sp_list: list[int] = [0, 0]  # W; power setpoints of batteries
        self.stance_list: list[str] = ["NOM", "NOM"]  # current control stance for each battery

        self.set_call_backs()
        # update monitors with actual data
        self.get_price_states()

        self.log("BatMan2 is running...")

    def set_call_backs(self):
        """Set-up callbacks for price changes and watchdogs."""
        self.callback_handles.append(
            self.listen_state(self.price_list_cb, cs.PRICES["entity"], attribute=cs.PRICES["attr"]["list"])
        )
        self.callback_handles.append(
            self.listen_state(self.price_current_cb, cs.PRICES["entity"], attribute=cs.PRICES["attr"]["now"])
        )
        # Set-up callbacks for watchdog changes
        # EV starts charging
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.EV_REQ_PWR))
        # App control is allowed or prohibited
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.CTRL_BY_ME))
        # Minimum SoC is reached
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.BAT_MIN_SOC_WD))
        # PV overcurrent detected
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.PV_CURRENT_WD))

    def get_price_states(self):
        """Get current states for prices by calling the callbacks directly"""
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
        soc_now: float = sum(soc_list) / len(soc_list)
        return soc_now, soc_list

    def get_pwr_sp(self) -> list[int]:
        """Get current power setpoints for all batteries."""
        pwr_list: list[int] = []
        for bat in cs.SETPOINTS:
            _sp: Any | None = self.get_state(entity_id=bat, attribute="state")
            if _sp is not None:
                pwr_list.append(int(_sp))
            else:
                pwr_list.append(0)
        return pwr_list

    def get_bat_strat(self) -> list[str]:
        """Get current control stance for all batteries."""
        bat_list: list[str] = []
        for bat in cs.BAT_STANCE:
            _sp: Any | None = self.get_state(entity_id=bat, attribute="state")
            if _sp is not None:
                bat_list.append(str(_sp))
            else:
                bat_list.append("NOM")
        return bat_list

    def update_states(self):
        """Update internal states based on current conditions."""
        self.log("---------------------------   ------------------------")
        # update the current date
        self.datum = ut.get_these_days()
        # minimum SoC required to provide power until 10:00 next morning
        _bms: Any = self.get_state(cs.BAT_MIN_SOC)
        self.bats_min_soc = float(_bms)
        self.log(f"BAT minimum SoC             =  {self.bats_min_soc:.1f} %")
        # get current SoC
        self.soc, self.soc_list = self.get_soc()
        self.log(f"BAT current SoC             =  {self.soc:.1f} %  <- {self.soc_list}")
        # get battery power setpoints
        self.pwr_sp_list = self.get_pwr_sp()
        _ssp = sum(self.pwr_sp_list)
        self.log(f"BAT actual setpoints        = {_ssp:+} W  <- {self.pwr_sp_list}")
        # get battery power stances
        self.stance_list = self.get_bat_strat()
        self.log(f"BAT current stance          =  {self.stance_list}")
        # get PV current and power values
        _pvc: Any = self.get_state(cs.PV_CURRENT)
        self.pv_current = float(_pvc)
        self.log(f"PV actual current           =  {self.pv_current:.2f} A")
        _pvv: Any = self.get_state(cs.PV_VOLTAGE)
        self.pv_volt = int(float(_pvv))
        self.log(f"PV actual voltage           =  {self.pv_volt:.2f} V")
        self.log(f"PV calculated power (I x U) =  {(self.pv_current * self.pv_volt):.1f} W")
        _pvp: Any = self.get_state(cs.PV_POWER)
        self.pv_power = int(float(_pvp))
        self.log(
            f"PV actual power             = {self.pv_power:+} W  (delta={
                abs(abs(self.pv_power) - (self.pv_current * self.pv_volt)):.0f
            })"
        )
        # check if we are greedy (price must have been updated already!)
        self.greedy = ut.get_greedy(self.price["now"])
        match self.greedy:
            case -1:
                _s = "greedy to CHARGE"
            case 1:
                _s = "greedy for DISCHARGE"
            case _:
                _s = "NOT greedy"
        self.log(f"Greed                       =  {_s}")
        # check whether the EV is currently charging
        _evc: Any = self.get_state(cs.EV_REQ_PWR)
        self.ev_charging = False
        if str(_evc) == "on":
            self.ev_charging = True
        self.log(f"EV charging                 =  {str(_evc).upper()}")
        # check if we are going to assist the EV
        self.ev_assist = cs.EV_ASSIST
        if self.price["now"] > self.price["stats"]["q3"]:
            self.ev_assist = True
            self.log("EV assist                   =  ENABLED")
        else:
            self.log("EV assist                   =  DISABLED")
        # check if we are allowed to control the batteries
        _ctrl: Any = self.get_state(cs.CTRL_BY_ME)
        self.ctrl_by_me = False
        if str(_ctrl) == "on":
            self.ctrl_by_me = True
            self.log("Control by app              =  ENABLED")
        else:
            self.log("Control by app              =  DISABLED")
        # self.log("---------------------------   ------------------------")

    def update_tibber_prices(self):
        self.tibber_prices = p2.get_pricelist(
            token=self.secrets.get_tibber_token(), url=self.secrets.get_tibber_url()
        )
        self.tibber_quarters = False
        if len(self.tibber_prices) == 96:
            self.tibber_quarters = True

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

        self.update_tibber_prices()
        # lookup Tibber price for the current hour and quarter
        _hr = dt.datetime.now().hour
        _qr = 0
        if self.tibber_quarters:
            _qr = dt.datetime.now().minute
        _pt = p2.get_price(self.tibber_prices, _hr, _qr)
        self.price["now"] = _pt
        # self.tibber_prices = _pt
        # every time the current price changes, we update other stuff too:
        self.update_states()
        # log the current price
        if self.debug:
            self.log(f"Current Sessy  price        = {_p:+.3f}")
            self.log(f"Current Tibber price        = {_pt:+.3f}")
        self.calc_stance()
        self.set_stance()

    def price_list_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for price list change."""
        # update dates
        self.datum = ut.get_these_days()
        # update tibber prices
        self.update_tibber_prices()
        # update prices
        _p = ut.total_price(new[self.datum["today"].strftime("%Y-%m-%d")])  # -legacy
        self.price["today"] = _p  # -legacy
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

    def watchdog_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for changes to monitored automations."""
        # Update the current state of the system
        self.log(f"*** Watchdog triggered by {entity} ({attribute}) change: {old} -> {new}")
        # watchdog changes are not immediate, so we run a watchdog_runin_cb after 1 second
        # to allow the system to stabilize
        self.run_in(self.watchdog_runin_cb, 2, entity=entity, attribute=attribute, old=old, new=new)

    def watchdog_runin_cb(self, entity, attribute, old, new, **kwargs):
        self.update_states()
        # Decide stance based on the current state
        self.calc_stance()
        # Log the current stance
        if self.debug:
            self.log(f"Current stance             = {self.stance}")

    # CONTROL LOGIC

    def calc_stance(self):
        """Choose the current stance based on the current price and battery state
        and determine the battery power setpoint."""

        self.log("=========================== ! ========================")
        stance: str = self.stance  # Keep the current stance
        if self.ctrl_by_me is False:
            # we are switched off
            self.log("*** Control by app is disabled. No stance change! ***")
            return

        if self.ev_charging:
            # automation will have switched the batteries to IDLE.
            stance = cs.IDLE
            # we overrule this only if ev_assist is true
            #   and the price is above Q3
            #   and the SoC is above bats_min_soc
            _q3 = self.price["stats"]["q3"]
            if self.ev_assist and self.soc > self.bats_min_soc:  # or p1_power < -200
                self.log(f"EV is charging but price is above {_q3:.3f}. Switching to DISCHARGE stance.")
                stance = cs.DISCHARGE
        else:
            stance = cs.NOM  # default stance is NOM

        # if prices are extremelly high or low, we get greedy and switch to resp. DISCHARGE or CHARGE stance
        match self.greedy:
            case -1:
                self.log("Greedy for CHARGE. Switching to CHARGE stance.")
                stance = cs.CHARGE
            case 1:
                self.log("Greedy for DISCHARGE. Switching to CHARGE stance.")
                stance = cs.DISCHARGE
            case _:
                pass  # not greedy, do nothing

        # if it is a sunny day, batteries will charge automatically
        # we may want to discharge during the expensive hours
        # check if now().hour is in self.price["expen_hour"]
        _hr: int = dt.datetime.now().hour
        _min_soc = self.bats_min_soc + (2 * cs.DISCHARGE_PWR / 100)
        if self.datum["sunny"] and (self.soc > _min_soc) and (_hr in self.price["expen_hour"]):
            self.log(
                f"Sunny day, expensive hours and enough SoC (> {_min_soc}%). Switching to DISCHARGE stance."
            )
            stance = cs.DISCHARGE
        if not self.datum["sunny"] and (self.soc < self.bats_min_soc) and (_hr in self.price["cheap_hour"]):
            self.log(
                f"Not a sunny day, hour is cheap and SoC below {
                    self.bats_min_soc
                }%. Switching to CHARGE stance."
            )
            stance = cs.CHARGE
        self.stance = stance
        self.log(f"Current stance set to: {self.stance}")
        self.calc_pwr_sp(stance)
        self.log("======================================================")

    def calc_pwr_sp(self, stance):
        """Calculate the power setpoints for the current stance."""
        match stance:
            case cs.NOM:
                self.pwr_sp_list = [0, 0]
                self.log("SP: No action required. Unit is in control (NOM).")
            case cs.IDLE:
                self.pwr_sp_list = [0, 0]
                self.log("SP: No power setpoints. Unit is IDLE. ")
            case cs.CHARGE:
                self.pwr_sp_list = [cs.CHARGE_PWR, cs.CHARGE_PWR]
                self.log(f"SP: Power setpoints calculated for {stance} stance: {self.pwr_sp_list}")
            case cs.DISCHARGE:
                self.pwr_sp_list = [cs.DISCHARGE_PWR, cs.DISCHARGE_PWR]
                self.log(f"SP: Power setpoints calculated for {stance} stance: {self.pwr_sp_list}")
            case _:
                self.logf("SP: No power setpoints calculated for unknown stance {stance}. ")

    def set_stance(self):
        """Set the current stance based on the current state."""
        match self.stance:
            case cs.NOM:
                self.start_nom()
            case cs.IDLE:
                self.start_idle()
            case cs.CHARGE:
                self.start_charge()
            case cs.DISCHARGE:
                self.start_discharge()
            case _:
                self.log(f"Unknown stance: {self.stance}. Switching to NOM.")

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

    # SECRETS
    def get_tibber(self) -> tuple[str, str]:
        _scrt = self.secrets.get_tibber_token()
        _url = self.secrets.get_tibber_url()
        return _scrt, _url


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
o EV_charging (automation)

API- (charge) START @:
o|| greedy: price < nul
o|| !sunnyday && SoC < sensor.bats_minimum_soc && cheap_hours
STOP @ SoC = 100%

API+ (discharge) START @:
o|| greedy: price > top
o|| EV_charging && EV_assist(= price > Q3 ) && SoC > sensor.bats_minimum_soc
o|| sunnyday && SoC > {2*17+ minsoc} % && expen_hours
STOP @ SoC = sensor.bats_minimum_soc

 """
