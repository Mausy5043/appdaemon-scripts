import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import battalk as bt
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
        self.greedy_ll = cs.PRICES["nul"]
        self.greedy_hh = cs.PRICES["top"]
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
        self.steps = ut.get_steps(cs.RAMP_RATE[0])
        self.step_cnt = 0  # keep track of the number of steps it took to ramp
        self.stance_list: list[str] = ["NOM", "NOM"]  # current control stance for each battery
        # get credentials and authenticate with the batteries
        self.bat_ctrl = self.get_bats()
        for _b in self.bat_ctrl:
            self.bat_ctrl[_b]["api"] = bt.Sessy(
                url=self.bat_ctrl[_b]["url"],
                username=self.bat_ctrl[_b]["username"],
                password=self.bat_ctrl[_b]["password"],
            )

        self.set_call_backs()
        # update monitors with actual data
        self.update_price_states()

        self.log("BatMan2 is running...")
        self.starting = False

    def set_call_backs(self) -> None:
        """Set-up callbacks for price changes and watchdogs."""
        # TODO: Callback at the top of the hour to catch hours that have the same price.
        self.callback_handles.append(
            self.listen_state(
                self.price_current_cb,
                cs.PRICES["entity"],
                attribute=cs.PRICES["attr"]["now"],
                duration=10,
            )
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
        # minimum greed
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.GREED_LL))
        # maximum greed
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.GREED_HH))

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
        # TODO: directly get the actual setpoint from the batteries (faster)
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
        # update the calendar/season info
        self.datum = ut.get_these_days()
        # minimum SoC required to provide power until next morning
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
        # fmt: off
        self.log(
            f"PV actual power             = {self.pv_power:+6.0f}    W  (delta={abs(abs(self.pv_power) - (self.pv_current * self.pv_volt)):.0f})"
        )
        # fmt: on
        # check if we are greedy (price must have been updated already!)
        _any: Any = self.get_state(cs.GREED_LL)
        self.greedy_ll = float(_any)
        _any = self.get_state(cs.GREED_HH)
        self.greedy_hh = float(_any)
        self.greedy = ut.get_greedy(self.price["now"], self.greedy_ll, self.greedy_hh)
        match self.greedy:
            case -1:
                _s = "greedy to CHARGE"
            case 1:
                _s = "greedy for DISCHARGE"
            case _:
                _s = "NOT greedy"
        self.log(f"Greed                       =  {_s}  ({self.greedy_ll} / {self.greedy_hh})")
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
        # winterstand
        self.winterstand = False
        if self.get_state(cs.WINTERSTAND) == "on":
            self.winterstand = True
        if self.winterstand:
            self.log("Winterstand                 =  ENABLED")
        else:
            self.log("Winterstand                 =  DISABLED")

    def update_tibber_prices(self) -> None:
        self.tibber_prices = p2.get_pricedict(
            token=self.secrets.get_tibber_token(), url=self.secrets.get_tibber_url()
        )
        self.log(f"Updated Tibber prices: {len(self.tibber_prices)} prices received.")
        self.tibber_quarters = False
        if len(self.tibber_prices) == 96:
            self.tibber_quarters = True

    def terminate(self) -> None:
        """Clean up app."""
        self.log("__Terminating BatMan2...")
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("__...terminated BatMan2.")

    # CALLBACKS

    def price_current_cb(self, entity, attribute, old, new, **kwargs) -> None:
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
            charge_today = ut.sort_index(_p, rev=True)[-16:]
            discharge_today = ut.sort_index(_p, rev=True)[:16]
        else:
            charge_today = ut.sort_index(_p, rev=True)[-4:]
            discharge_today = ut.sort_index(_p, rev=True)[:4]
        charge_today.sort()
        discharge_today.sort()
        self.price["cheap_slot"] = charge_today
        self.price["expen_slot"] = discharge_today

        # get the price for the current timeslot
        _pt = p2.get_price(self.tibber_prices, _hr, _qr)
        self.price["now"] = _pt

        # every time the current prices are updated, we update other stuff too:
        self.update_states()

        # calculate the distance to the minimum price
        self.price_diff = _pt - self.price["stats"]["min"]
        # log the current price
        if self.debug:
            self.log(f"Current Tibber price        = {_pt:+.3f} ({self.price_diff:.3f})")
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
        self.log(f"*** Watchdog triggered by {entity} ({attribute}) change: {old} -> {new}")
        # watchdog changes are not immediate, so we callback watchdog_runin_cb() after N seconds
        # to allow the system to stabilize
        self.run_in(self.watchdog_runin_cb, 2, entity=entity, attribute=attribute, old=old, new=new)

    def watchdog_runin_cb(self, entity, attribute, old, new, **kwargs):
        # Update the current state of the system
        self.update_states()
        # determine the new stance ...
        self.calc_stance()
        # ... and set it
        self.set_stance()
        # Log the current stance
        self.log(f"Current stance              =  {self.new_stance}")

    def ramp_sp_runin_cb(self, entity, attribute, old, new, **kwargs):
        self.ramp_sp()

    # CONTROL LOGIC

    def calc_stance(self):
        """Choose the current stance based on the current price and battery state
        and determine the battery power setpoint."""
        self.log("=========================== ! ========================")
        stance: str = self.new_stance
        self.prv_stance = self.new_stance  # Keep the current stance
        self.log(f"Previous stance was: {self.prv_stance}")
        if self.ctrl_by_me is False:
            # we are switched off
            self.log("*** Control by app is disabled. No stance change! ***")
            return

        _hr: int = dt.datetime.now().hour
        # calculate the SoC needed to be able to discharge for at least a whole hour.
        _min_soc = self.bats_min_soc + (2 * cs.DISCHARGE_PWR / 100)
        _q3 = self.price["stats"]["q3"]

        if self.ev_charging:
            # automation will have switched the batteries to IDLE.
            stance = cs.IDLE
            # we overrule this only if ev_assist is true
            #   and the price is above Q3
            #   and the SoC is above bats_min_soc
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

        # if it is a sunny day, batteries will charge automatically
        # and we don't want to discharge during the expensive timeslots
        # because that would drain the batteries and negatively affect
        # solar availability for the EV charger.
        # winterstand forces behaviour of a non-sunny day when true
        if (
            (self.datum["sunny"] or not self.winterstand)
            and (self.soc > _min_soc)
            and (_hr in self.price["expen_slot"])
        ):
            # For now we use NOM to avoid locking out the EV charger.
            stance = cs.NOM
            self.log(f"Sunny day, expensive hour and  SoC > {_min_soc}%, but requesting NOM stance.")
        if (
            (not self.datum["sunny"] or self.winterstand)
            and (self.soc < self.bats_min_soc or self.prv_stance == cs.CHARGE)
            and (_hr in self.price["cheap_slot"])
        ):
            # this is supposed to charge the battery during the cheap hours in winter mimicking the ECO-mode
            self.log(
                f"Non-sunny day, cheap hour {_hr} and SoC < {self.bats_min_soc}%, so requesting CHARGE stance."
            )
            stance = cs.CHARGE

        # if prices are extremely high or low, we get greedy and switch to resp. DISCHARGE or CHARGE stance
        match self.greedy:
            case -1:
                _l = "Greedy for CHARGE. But too high SoC."
                if (self.prv_stance == cs.CHARGE and self.soc < 99.9) or (self.soc < self.bats_min_soc):
                    _l = "Greedy for CHARGE. Requesting CHARGE stance."
                    stance = cs.CHARGE
                self.log(_l)
            case 1:
                _l = "Greedy for DISCHARGE. But too low SoC."
                if (self.prv_stance == cs.DISCHARGE and self.soc > self.bats_min_soc) or (self.soc > _min_soc):
                    _l = "Greedy for DISCHARGE. Requesting DISCHARGE stance."
                    stance = cs.DISCHARGE
                self.log(_l)
            case _:
                pass  # not greedy, do nothing

        self.new_stance = stance
        self.calc_pwr_sp(self.new_stance)
        self.log("======================================================")

    def calc_pwr_sp(self, stance):
        """Calculate the power setpoints for the current stance."""
        # TODO: use different SP depending on difference in SoC between the batteries,
        #       so that at the end of the hour the SoCs are (almost) the same.
        # TODO: use "number.sessy_p1_grid_target" to control the (dis)charge power
        match stance:
            case cs.NOM:
                self.pwr_sp_list = [0, 0]
                self.log("SP: No action required. Unit is in control (NOM).")
            case cs.IDLE:
                self.pwr_sp_list = [0, 0]
                self.log("SP: No power setpoints. Unit is IDLE. ")
            case cs.CHARGE:
                self.pwr_sp_list = [cs.CHARGE_PWR, cs.CHARGE_PWR]
                self.step_cnt = self.steps
                self.log(f"SP: Power setpoints calculated for {stance} stance: {self.pwr_sp_list}")
            case cs.DISCHARGE:
                self.pwr_sp_list = [cs.DISCHARGE_PWR, cs.DISCHARGE_PWR]
                self.step_cnt = self.steps
                self.log(f"SP: Power setpoints calculated for {stance} stance: {self.pwr_sp_list}")
            case _:
                self.logf(f"SP: No power setpoints calculated for unknown stance {stance}. ")

    def adjust_pwr_sp(self):
        """Control each battery to the desired power setpoint."""
        for idx, (name, bat) in enumerate(self.bat_ctrl.items()):
            _sp: int = int(self.pwr_sp_list[idx])
            _api = bat["api"]
            # TODO: ramp to setpoint
            # ramp_sp_runin_cb
            try:
                if (self.prv_stance in ["API+", "API-"]) or (self.new_stance in ["API+", "API-"]):
                    # NOM->API; IDLE->API; API->API; API->NOM; API->IDLE
                    _s: dict | str = _api.set_setpoint(_sp)
                else:
                    _s = "IGNORED"
            except Exception as her:
                _s = f"UNSUCCESFULL: {her}"
            self.log(f"Sent {name} to {_sp:>5} .......... {_s}")

    def ramp_sp(self):
        """Change the battery setpoints in steps"""
        current_sp: list[int] = self.get_pwr_sp()  # current setpoint reported by the battery
        calc_sp: list[int] = self.pwr_sp_list  # calculated final setpoints
        _cb = False
        _s: dict = {}
        self.step_cnt -= 1
        if self.step_cnt > 0:  # prevent ramping to an unattainable SP
            for idx, bat in self.bat_ctrl.items():
                _api = self.bat_ctrl[bat]["api"]
                deadband = 0.1 * calc_sp[idx]
                # determine offset to current setpoint
                epsilon = calc_sp[idx] - current_sp[idx]
                # calculate stepsize
                step_sp = epsilon * cs.RAMP_RATE[0]
                # calculate new setpoint
                if step_sp > deadband:
                    new_sp = int(step_sp + current_sp[idx])
                    self.log(f"Ramping {bat} to {new_sp:>5} .......")
                    _s = _api.set_setpoint(new_sp)
                    self.log(f"           .................. {_s}")
                    # need to callback for next step
                    _cb = True
                else:
                    new_sp = calc_sp[idx]
                    self.log(f"Set {bat} to {new_sp:>5} ...........")
                    _s = _api.set_setpoint(new_sp)
                    self.log(f"           .................. {_s}")
        # set-up callback for next step
        if _cb:
            self.run_in(
                self.ramp_sp_runin_cb,
                cs.RAMP_RATE[1],
                entity="ramp",
                attribute="callback",
                old="",
                new="",
            )

    def set_stance(self):
        """Set the current stance based on the current state."""
        match self.new_stance:
            case cs.NOM:
                # with contextlib.suppress(Exception):
                self.adjust_pwr_sp()
                self.start_nom()
            case cs.IDLE:
                # with contextlib.suppress(Exception):
                self.adjust_pwr_sp()
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
            # for bat in cs.BAT_STANCE:
            #     self.log(f"Setting {bat} to {stance}")
            #     self.set_state(bat, stance.lower())
            for bat in self.bat_ctrl:
                _api = self.bat_ctrl[bat]["api"]
                _s = _api.set_strategy(stance.lower())
                self.log(f"Sent {bat} to {stance:>4} ........... {_s}")

    def start_idle(self):
        """Start the IDLE stance."""
        stance: str = cs.IDLE
        if self.ctrl_by_me:
            # for bat in cs.BAT_STANCE:
            #     self.log(f"Setting {bat} to {stance}")
            #     self.set_state(bat, stance.lower())
            for bat in self.bat_ctrl:
                _api = self.bat_ctrl[bat]["api"]
                _s = _api.set_strategy(stance.lower())
                self.log(f"Sent {bat} to {stance:>4} ........... {_s}")

    def start_charge(self, power: int = cs.CHARGE_PWR):
        """Start the API- stance."""
        stance: str = cs.CHARGE[:-1]
        if self.ctrl_by_me:
            # for bat in cs.BAT_STANCE:
            #     self.log(f"Setting {bat} to {stance}")
            #     self.set_state(bat, stance.lower())
            for bat in self.bat_ctrl:
                _api = self.bat_ctrl[bat]["api"]
                _s = _api.set_strategy(stance.lower())
                self.log(f"Sent {bat} to {stance:>4} ........... {_s}")
            self.adjust_pwr_sp()

    def start_discharge(self, power: int = cs.DISCHARGE_PWR):
        """Start the API+ stance."""
        stance: str = cs.DISCHARGE[:-1]
        if self.ctrl_by_me:
            # for bat in cs.BAT_STANCE:
            #     self.log(f"Setting {bat} to {stance}")
            #     self.set_state(bat, stance.lower())
            for bat in self.bat_ctrl:
                _api = self.bat_ctrl[bat]["api"]
                _s = _api.set_strategy(stance.lower())
                self.log(f"Sent {bat} to {stance:>4} ........... {_s}")
            self.adjust_pwr_sp()

    # SECRETS

    def get_tibber(self) -> tuple[str, str]:
        _scrt = self.secrets.get_tibber_token()
        _url = self.secrets.get_tibber_url()
        return _scrt, _url

    def get_bats(self):
        _auth_dict = {}
        for _b in ["bat1", "bat2"]:
            _auth_dict[_b] = self.secrets.get_sessy_secrets(_b)
        return _auth_dict


"""
sunnyday = march equinox to september equinox OR not winterstand


x EV assist when price > Q3

Default requirements:
o default stance = NOM
o sensor.bats_minimum_soc = SoC required to provide 200 W (input_number.home_baseload) until 10:00 next morning (sensor.hours_till_10am)
- battery contents is available to the home
o keep sensor.pv_kwh_meter_current <= +/- 21 A

NOM:
o|| NOM
o|| API- && SoC >= 100%
o|| API+ && SoC =< sensor.bats_minimum_soc
o|| IDLE && !EV_charging
o|| EV_charging && EV_assist


IDLE:
o|| EV_charging (automation) || !EV_assist


API- (charge) START @:
o|| greedy: price < nul
o|| (!sunnyday || winterstand) && (SoC < sensor.bats_minimum_soc) && cheap_slots


API+ (discharge) START @:
o|| greedy: price > top
o|| EV_charging && EV_assist(= price > Q3 ) && SoC > sensor.bats_minimum_soc
o|| (sunnyday && !winterstand) && (SoC > {2*17+ minsoc}) % && expen_slot

 """
