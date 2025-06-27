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
        self.starting = True
        self.callback_handles: list[Any] = []

        # create internals
        self.debug: bool = cs.DEBUG
        self.secrets = self.get_app("scrts")
        self.greedy: int = 0  # 0 = not greedy, 1 = greedy hi price, -1 = greedy low price
        self.datum: dict = ut.get_these_days()
        self.new_stance: str = cs.DEFAULT_STANCE
        self.prv_stance: str = cs.DEFAULT_STANCE
        self.tibber_prices: dict[str, float] = {}
        self.tibber_quarters: bool = False  # whether the Tibber prices are quarterly or not
        self.price: dict = {
            "today": [],
            "tomor": [],
            "now": 0.0,
            "cheap_slot": [],
            "expen_slot": [],
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
        self.update_price_states()

        self.log("BatMan2 is running...")
        self.starting = False

    def set_call_backs(self) -> None:
        """Set-up callbacks for price changes and watchdogs."""
        # self.callback_handles.append(
        #     self.listen_state(self.price_list_cb, cs.PRICES["entity"], attribute=cs.PRICES["attr"]["list"])
        # )
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

    def update_price_states(self) -> None:
        """Get current states for prices by calling the callback directly"""
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
                print(_sp, type(_sp))
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
        self.log(f"BAT minimum SoC             = {self.bats_min_soc:8.1f}  %")
        # get current SoC
        self.soc, self.soc_list = self.get_soc()
        self.log(f"BAT current SoC             = {self.soc:8.1f}  %  <- {self.soc_list}")
        # get battery power setpoints
        self.pwr_sp_list = self.get_pwr_sp()
        _ssp = sum(self.pwr_sp_list)
        self.log(f"BAT actual setpoints        = {_ssp:+6.0f}    W  <- {self.pwr_sp_list}")
        # get battery power stances
        self.stance_list = self.get_bat_strat()
        self.log(f"BAT current stance          = {self.stance_list}")
        # get PV current and power values
        _pvc: Any = self.get_state(cs.PV_CURRENT)
        self.pv_current = float(_pvc)
        self.log(f"PV actual current           = {self.pv_current:9.2f} A")
        _pvv: Any = self.get_state(cs.PV_VOLTAGE)
        self.pv_volt = int(float(_pvv))
        self.log(f"PV actual voltage           = {self.pv_volt:9.2f} V")
        self.log(f"PV calculated power (I x U) = {(self.pv_current * self.pv_volt):8.1f}  W")
        _pvp: Any = self.get_state(cs.PV_POWER)
        self.pv_power = int(float(_pvp))
        self.log(
            f"PV actual power             = {self.pv_power:+6.0f}    W  (delta={
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
        self.tibber_prices = p2.get_pricedict(
            token=self.secrets.get_tibber_token(), url=self.secrets.get_tibber_url()
        )
        self.log(f"Updated Tibber prices: {len(self.tibber_prices)} prices received.")
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
        # update dates
        self.datum = ut.get_these_days()
        # get the prices for today
        self.update_tibber_prices()
        # lookup Tibber price for the current hour and quarter
        _hr: int = dt.datetime.now().hour
        _qr: int = 0
        if self.tibber_quarters:
            # callback will be either on the hour or on the quarter
            _qr = dt.datetime.now().minute

        # get a list of hourly (or quarterly) prices and do some basic statistics
        _p: list[float] = p2.total_price(self.tibber_prices)
        self.price["today"] = _p
        self.price["stats"] = p2.price_statistics(_p)

        # make a list of the cheap and expensive hours
        if self.tibber_quarters:
            charge_today = ut.sort_index(_p, rev=True)[-12:]
            discharge_today = ut.sort_index(_p, rev=True)[:12]
        else:
            charge_today = ut.sort_index(_p, rev=True)[-3:]
            discharge_today = ut.sort_index(_p, rev=True)[:3]
        charge_today.sort()
        discharge_today.sort()
        self.price["cheap_slot"] = charge_today
        self.price["expen_slot"] = discharge_today

        # get the price for the curren timeslot
        _pt = p2.get_price(self.tibber_prices, _hr, _qr)
        self.price["now"] = _pt

        # every time the current prices are updated, we update other stuff too:
        self.update_states()

        # log the current price
        if self.debug:
            self.log(f"Current Tibber price        = {_pt:+.3f}")
        if self.debug and ((_qr == 0 and _hr == 0) or self.starting):
            self.log(
                f"Today's pricelist           =  {
                    [f'{n:.3f}' for n in self.price['today']]
                }\n                                       : cheap slots                 = {
                    self.price['cheap_slot']
                }\n                                       : expensive slots             = {
                    self.price['expen_slot']
                }\n                                       : STATISTICS\n :                {
                    self.price['stats']['text']
                }"
            )

        # determine the new stance ...
        self.calc_stance()
        # ... and set it
        self.set_stance()

    def watchdog_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for changes to monitored automations."""
        # Update the current state of the system
        self.log(f"*** Watchdog triggered by {entity} ({attribute}) change: {old} -> {new}")
        # watchdog changes are not immediate, so we run a watchdog_runin_cb after 1 second
        # to allow the system to stabilize
        self.run_in(self.watchdog_runin_cb, 2, entity=entity, attribute=attribute, old=old, new=new)

    def watchdog_runin_cb(self, entity, attribute, old, new, **kwargs):
        self.update_states()
        # determine the new stance ...
        self.calc_stance()
        # ... and set it
        self.set_stance()
        # Log the current stance
        if self.debug:
            self.log(f"Current stance              =  {self.new_stance}")

    def ramp_sp_runin_cb(self, entity, attribute, old, new, **kwargs):
        self.ramp_sp()

    # CONTROL LOGIC

    def calc_stance(self):
        """Choose the current stance based on the current price and battery state
        and determine the battery power setpoint."""
        self.log("=========================== ! ========================")
        stance: str = self.new_stance  # Keep the current stance
        self.prv_stance = stance
        if self.ctrl_by_me is False:
            # we are switched off
            self.log("*** Control by app is disabled. No stance change! ***")
            # return

        if self.ev_charging:
            # automation will have switched the batteries to IDLE.
            stance = cs.IDLE
            # we overrule this only if ev_assist is true
            #   and the price is above Q3
            #   and the SoC is above bats_min_soc
            _q3 = self.price["stats"]["q3"]
            if self.ev_assist and self.soc > self.bats_min_soc:  # or p1_power < -200

                # stance = cs.DISCHARGE
                # EV assist is essentially not available for now.
                self.log(
                    f"EV is charging and price is above Q3 ({_q3:.3f}), but proposing to keep stance ({
                        stance
                    })."
                )
        else:
            stance = cs.NOM  # default stance is NOM

        # if prices are extremely high or low, we get greedy and switch to resp. DISCHARGE or CHARGE stance
        match self.greedy:
            case -1:
                if self.soc > self.bats_min_soc:
                    self.log("Greedy for CHARGE. Requesting CHARGE stance.")
                    stance = cs.CHARGE
            case 1:
                if self.soc < self.bats_min_soc:
                    self.log("Greedy for DISCHARGE. Requesting DISCHARGE stance.")
                    stance = cs.DISCHARGE
            case _:
                pass  # not greedy, do nothing

        # if it is a sunny day, batteries will charge automatically
        # we may want to discharge during the expensive timeslots
        # check if now().hour is in self.price["expen_slot"]
        _hr: int = dt.datetime.now().hour
        _min_soc = self.bats_min_soc + (2 * cs.DISCHARGE_PWR / 100)
        if self.datum["sunny"] and (self.soc > _min_soc) and (_hr in self.price["expen_slot"]):
            stance = cs.DISCHARGE
            self.log(f"Sunny day, expensive hour and  SoC > {_min_soc}%. Requesting DISCHARGE stance.")
        if not self.datum["sunny"] and (self.soc < self.bats_min_soc) and (_hr in self.price["cheap_slot"]):
            self.log(
                f"Non-sunny day, cheap hour {_hr} and SoC < {self.bats_min_soc}%. Requesting CHARGE stance."
            )
            stance = cs.CHARGE
        self.new_stance = stance
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
                self.logf(f"SP: No power setpoints calculated for unknown stance {stance}. ")

    def adjust_pwr_sp(self):
        # modify setpoint for testing
        setpoint = self.pwr_sp_list
        for bat, bat_sp in enumerate(cs.SETPOINTS):
            if setpoint[bat] > 0:
                setpoint[bat] = 1661
            if setpoint[bat] < 0:
                setpoint[bat] = -2112
            self.log(f"Setting {bat_sp} to {setpoint[bat]}")
            self.set_state(bat_sp, str(setpoint[bat]))
            # self.ramp_sp()

    def ramp_sp(self):
        current_sp: list[int] = self.get_pwr_sp()
        calc_sp: list[int] = self.pwr_sp_list
        _cb = False
        for idx, bat in enumerate(cs.SETPOINTS):
            epsilon = calc_sp[idx] - current_sp[idx]
            step_sp = epsilon * 0.4
            if step_sp > 190:
                new_sp = int(step_sp + current_sp[idx])
                self.log(f"ramping {bat} to {new_sp}")
                self.set_state(bat, str(new_sp))
                _cb = True
            else:
                self.log(f"finalising ramping {bat} to {calc_sp[idx]} ({step_sp})")
                self.set_state(bat, str(calc_sp))
        if _cb:
            self.run_in(
                self.ramp_sp_runin_cb,
                cs.RAMP_RATE,
                entity="ent",
                attribute="atrr",
                old="",
                new="",
            )

    def set_stance(self):
        """Set the current stance based on the current state."""
        match self.new_stance:
            case cs.NOM:
                self.start_nom()
            case cs.IDLE:
                self.start_idle()
            case cs.CHARGE:
                self.start_charge()
            case cs.DISCHARGE:
                self.start_discharge()
            case _:
                self.log(f"*** Unknown stance: {self.new_stance}. Switching to NOM.")
                self.start_nom()

    def start_nom(self):
        """Start the NOM stance."""
        stance: str = cs.NOM
        if self.ctrl_by_me:
            for bat in cs.BAT_STANCE:
                self.log(f"Setting {bat} to {stance}")
                self.set_state(bat, stance.lower())

    def start_idle(self):
        """Start the IDLE stance."""
        stance: str = cs.IDLE
        if self.ctrl_by_me:
            for bat in cs.BAT_STANCE:
                self.log(f"Setting {bat} to {stance}")
                self.set_state(bat, stance.lower())

    def start_charge(self, power: int = cs.CHARGE_PWR):
        """Start the API- stance."""
        stance: str = cs.CHARGE[:-1]
        if self.ctrl_by_me:
            for bat in cs.BAT_STANCE:
                self.log(f"Setting {bat} to {stance}")
                self.set_state(bat, stance.lower())
            self.adjust_pwr_sp()

    def start_discharge(self, power: int = cs.DISCHARGE_PWR):
        """Start the API+ stance."""
        stance: str = cs.DISCHARGE[:-1]
        if self.ctrl_by_me:
            for bat in cs.BAT_STANCE:
                self.log(f"Setting {bat} to {stance}")
                self.set_state(bat, stance.lower())
            self.adjust_pwr_sp()

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
o|| !sunnyday && SoC < sensor.bats_minimum_soc && cheap_slots
STOP @ SoC = 100%

API+ (discharge) START @:
o|| greedy: price > top
o|| EV_charging && EV_assist(= price > Q3 ) && SoC > sensor.bats_minimum_soc
o|| sunnyday && SoC > {2*17+ minsoc} % && expen_slot
STOP @ SoC = sensor.bats_minimum_soc

 """
