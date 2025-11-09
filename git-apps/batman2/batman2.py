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
        self.log(f"===================================== BatMan2 v{cs.VERSION} ====", level="INFO")
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
        self.tibber_sensor: str = self.secrets.get_tibber_sensor()
        self.tibber_quarters: bool = True  # whether the Tibber prices are quarterly or not
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
        self.low_pv = self.get_state(cs.LOW_PV) == "on"
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

        self.log("BatMan2 is running...", level="INFO")
        self.starting = False

    def set_call_backs(self) -> None:
        """Set-up callbacks for price changes and watchdogs."""
        # Set-up callback for 10s after a price change
        # self.callback_handles.append(
        #     self.listen_state(
        #         callback=self.price_current_cb,
        #         entity_id=self.tibber_sensor,
        #         attribute=cs.PRICES["attr"]["now"],
        #         duration=10,
        #     )
        # )
        # Callback at the top of the slot to catch slots that have the same price.
        now = dt.datetime.now()
        quarter = 15
        minutes = (now.minute // quarter + 1) * quarter
        next_quarter = now.replace(minute=0, second=0, microsecond=0) + dt.timedelta(
            minutes=minutes, seconds=20
        )
        self.log(f"Next quarter callback       =  {next_quarter.strftime("%Y-%m-%d %H:%M:%S")}", level="INFO")
        # run_every callbacks can't be cancelled
        self.run_every(
            callback=self.price_current_cb,
            start=next_quarter,
            interval=cs.PRICES["update_interval"],
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
        # low PV continuously for 60s
        self.callback_handles.append(
            self.listen_state(self.watchdog_cb, cs.LOW_PV, duration=dt.timedelta(seconds=60))
        )

    def update_price_states(self) -> None:
        """Get current states for prices by calling the callback directly"""
        self.price_current_cb()
        # "entity", "list", "none", self.get_state(cs.PRICES["entity"], attribute=cs.PRICES["attr"]["now"]) )

    def get_soc(self) -> tuple[float, list[float]]:
        """Get current state of charge (SoC) for all batteries."""
        soc_list: list[float] = []
        for bat in cs.BATTERIES:
            _s: Any = self.get_state(entity_id=bat, attribute="state")
            try:
                _soc = float(_s)
            except ValueError:
                self.log(f"*** Invalid SoC value for {bat}: {_s}. Setting to 0.0", level="ERROR")
                _soc = 0.0
            soc_list.append(_soc)
        soc_now: float = sum(soc_list) / len(soc_list)
        return soc_now, soc_list

    def get_pwr_sp(self) -> list[int]:
        """Get current power setpoints for all batteries."""
        # TODO: directly get the actual setpoint from the batteries (faster)
        pwr_list: list[int] = []
        for bat in cs.SETPOINTS:
            _sp: Any = self.get_state(entity_id=bat, attribute="state")
            try:
                _setpoint = int(_sp)
            except ValueError:
                self.log(f"*** Invalid setpoint value for {bat}: {_sp}. Setting to 0", level="ERROR")
                _setpoint = 0
            pwr_list.append(_setpoint)

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
        self.log("---------------------------   ------------------------", level="DEBUG")
        # update the calendar/season info
        self.datum = ut.get_these_days()
        # minimum SoC required to provide power until next morning
        _bms: Any = self.get_state(cs.BAT_MIN_SOC)
        self.bats_min_soc = float(_bms)
        self.log(f"BAT minimum SoC             = {self.bats_min_soc:8.1f}  %", level="DEBUG")
        # get current SoC
        self.soc, self.soc_list = self.get_soc()
        self.log(f"BAT current SoC             = {self.soc:8.1f}  %  <- {self.soc_list}", level="DEBUG")
        # get battery power setpoints
        self.pwr_sp_list = self.get_pwr_sp()
        _ssp = sum(self.pwr_sp_list)
        self.log(f"BAT actual setpoints        = {_ssp:+6.0f}    W  <- {self.pwr_sp_list}", level="DEBUG")
        # get battery power stances
        self.stance_list = self.get_bat_strat()
        self.log(f"BAT current stance          = {self.stance_list}", level="DEBUG")
        # get PV current and power values
        _pvc: Any = self.get_state(cs.PV_CURRENT)
        self.pv_current = float(_pvc)
        self.log(f"PV actual current           = {self.pv_current:9.2f} A", level="DEBUG")
        _pvv: Any = self.get_state(cs.PV_VOLTAGE)
        self.pv_volt = int(float(_pvv))
        self.log(f"PV actual voltage           = {self.pv_volt:9.2f} V", level="DEBUG")
        self.log(f"PV calculated power (I x U) = {(self.pv_current * self.pv_volt):8.1f}  W", level="DEBUG")
        _pvp: Any = self.get_state(cs.PV_POWER)
        self.pv_power = int(float(_pvp))
        # fmt: off
        self.log(
            f"PV actual power             = {self.pv_power:+6.0f}    W  (delta={abs(abs(self.pv_power) - (self.pv_current * self.pv_volt)):.0f})", level="DEBUG"
        )
        # fmt: on
        # winterstand
        self.winterstand = False
        if self.get_state(cs.WINTERSTAND) == "on":
            self.winterstand = True
        # check if we are greedy (price must have been updated already!)
        _any: Any = self.get_state(cs.GREED_LL)
        self.greedy_ll = float(_any)
        _any = self.get_state(cs.GREED_HH)
        self.greedy_hh = float(_any)
        price_diff: float = self.price["now"] - self.price["stats"]["min"]
        self.greedy = ut.get_greedy(
            self.price["now"],
            price_diff,
            self.greedy_ll,
            self.greedy_hh,
            self.datum["sunny"] and not self.winterstand,
        )
        match self.greedy:
            case -1:
                _s = "greedy to CHARGE"
            case 1:
                _s = "greedy for DISCHARGE"
            case _:
                _s = "NOT greedy"
        self.log(
            f"Greed                       =  {_s}  ({self.greedy_ll:.1f} / {self.greedy_hh:.1f})", level="DEBUG"
        )
        # check whether the EV is currently charging
        _evc: Any = self.get_state(cs.EV_REQ_PWR)
        self.ev_charging = False
        if str(_evc) == "on":
            self.ev_charging = True
        self.log(f"EV charging                 =  {str(_evc).upper()}", level="DEBUG")
        # check if we are going to assist the EV
        self.ev_assist = cs.EV_ASSIST
        if self.price["now"] > self.price["stats"]["q3"]:
            self.ev_assist = True
            self.log("EV assist                   =  ENABLED", level="INFO")
        else:
            self.log("EV assist                   =  DISABLED", level="DEBUG")
        # check if we are allowed to control the batteries
        _ctrl: Any = self.get_state(cs.CTRL_BY_ME)
        self.ctrl_by_me = False
        if str(_ctrl) == "on":
            self.ctrl_by_me = True
            self.log("Control by app              =  ENABLED", level="DEBUG")
        else:
            self.log("Control by app              =  DISABLED", level="INFO")
        if self.winterstand:
            self.log("Winterstand                 =  ENABLED", level="INFO")
        else:
            self.log("Winterstand                 =  DISABLED", level="DEBUG")

    def update_tibber_prices(self) -> None:
        self.tibber_prices = p2.get_pricedict(
            token=self.secrets.get_tibber_token(),
            url=self.secrets.get_tibber_url(),
        )
        self.log(f"Updated Tibber prices: {len(self.tibber_prices)} prices received.", level="DEBUG")
        self.tibber_quarters = False
        if len(self.tibber_prices) == 96:
            self.tibber_quarters = True

    def update_price_slots(self, prices: list[float]) -> None:
        """Update the cheap and expensive price slots.

        Args:
            prices (list[float]): list of prices for today

        Returns:
            None
        """
        self.log(f"I think the SoC is now {self.soc} %") # TODO: can we calculate the number of charge slots?
        _cslot = cs.SLOTS[0] * -1
        _dslot = cs.SLOTS[1]
        # allow for hourly prices
        _div = 1 if self.tibber_quarters else 4
        # in case of hourly prices we need to make sure we get int(hours)
        _cslot = int(_cslot/_div)
        _dslot = int(_dslot/_div)
        # Get the average price for comparison
        avg_price = self.price["stats"]["avg"]
        # Get sorted indices
        sorted_indices = ut.sort_index(prices, rev=True)
        # Get the N cheapest slots indices
        all_cheap = sorted_indices[_cslot:]
        # Filter cheap slots to only those below average
        charge_today = [idx for idx in all_cheap if prices[idx] < avg_price]
        charge_today.sort()
        # Get the N most expensive slots indices and filter to above average
        all_expensive = sorted_indices[:_dslot]
        discharge_today = [idx for idx in all_expensive if prices[idx] > avg_price]
        discharge_today.sort()
        self.price["cheap_slot"] = charge_today
        self.price["expen_slot"] = discharge_today

    def terminate(self) -> None:
        """Clean up app."""
        self.log("__Terminating BatMan2...", level="INFO")
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("__...terminated BatMan2.", level="INFO")

    # CALLBACKS

    def price_current_cb(self, **kwargs) -> None:
        """Callback for current price change."""
        # get current hour, quarter and slot
        _hr: int = dt.datetime.now().hour
        _qr: int = 0
        _slot: int = self.get_slot()
        if _slot == 0 or self.starting:
            # update dates
            self.datum = ut.get_these_days()
            # get the prices for today
            self.update_tibber_prices()
            # get a list of hourly (or quarterly) prices and do some basic statistics
            _p: list[float] = p2.total_price(self.tibber_prices)
            self.price["today"] = _p
            self.price["stats"] = p2.price_statistics(prices=_p)
            self.update_price_slots(prices=_p)

        if self.tibber_quarters:
            # callback will be either on the hour or on the quarter
            _qr = dt.datetime.now().minute
        # get the price for the current timeslot
        _pn = self.price["today"][_slot]
        # lookup Tibber price for the current hour and quarter
        # _pt = p2.get_price(self.tibber_prices, _hr, _qr)
        self.price["now"] = _pn

        # every time the current prices are updated, we update other stuff too:
        self.update_states()

        # calculate the distance to the minimum price
        self.price_diff = _pn - self.price["stats"]["min"]
        # log the current price
        if self.debug:
            self.log(
                f"Current Tibber price        = {_pn:+.3f} ({self.price_diff:.3f})",
                level="INFO",
            )
            self.log(
                f"Current time slot           =  {_slot:.0f} ({_slot / 4:.2f})",
                level="INFO",
            )
        if self.debug and ((_qr == 0 and _hr == 0) or self.starting):
            self.log(
                f"Today's pricelist           =  {
                    [f'{n:.3f}' for n in self.price['today']]
                }\n               : cheap slots                 = [{
                    ', '.join(f'{v / 4:.2f}' for v in self.price['cheap_slot'])
                }]\n               : expensive slots             = [{
                    ', '.join(f'{v / 4:.2f}' for v in self.price['expen_slot'])
                }]\n               : STATISTICS\n :                {self.price['stats']['text']}",
                level="INFO",
            )

        # determine the new stance ...
        self.calc_stance()
        # ... and set it
        self.set_stance()

    def watchdog_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for changes to monitored automations."""
        self.log(f"*** Watchdog triggered by {entity} ({attribute}) change: {old} -> {new}", level="INFO")
        # watchdog changes are not immediate, so we callback watchdog_runin_cb() after N seconds
        # to allow the system to stabilize
        # low PV is a special case, because it needs different actions
        if entity == cs.LOW_PV:
            self.run_in(self.lowpv_runin_cb, 2, entity=entity, new=new)
        else:
            self.run_in(self.watchdog_runin_cb, 2, entity=entity, attribute=attribute, old=old, new=new)

    def watchdog_runin_cb(self, entity, attribute, old, new, **kwargs):
        # Update the current state of the system
        self.update_states()
        # determine the new stance ...
        self.calc_stance()
        # ... and set it
        self.set_stance()
        # Log the current stance
        self.log(f"Current stance              =  {self.new_stance}", level="DEBUG")

    def lowpv_runin_cb(self, entity, new, **kwargs):
        """Handle low PV condition changes."""
        match str(new):
            case "on" | "off":
                # Only update if state actually changes
                new_state = new == "on"
                if new_state != self.low_pv:
                    self.log(f"*** Activity triggered by {entity} -> {new}", level="INFO")
                    self.low_pv = new_state
                    if self.ctrl_by_me:
                        # Set power based on state: 100W each when low PV, 0W when normal
                        if abs(self.pwr_sp_list[0]) < 110:  # avoid overwriting a CHARGE or DISCHARGE stance
                            self.pwr_sp_list = [100, 100] if self.low_pv else [0, 0]
                            self.adjust_pwr_sp()
                    else:
                        self.log("*** Activity canceled. App is not in control.", level="WARNING")
            case _:
                self.log(f"*** Invalid value for {entity}: {new}. No action taken.", level="ERROR")

    # CONTROL LOGIC

    def calc_stance(self):
        """Choose the current stance based on the current price and battery state
        and determine the battery power setpoint."""
        self.log("=========================== ! ========================", level="DEBUG")
        stance: str = self.new_stance
        self.prv_stance = self.new_stance  # Keep the current stance
        self.log(f"Previous stance was: {self.prv_stance}", level="DEBUG")
        if self.ctrl_by_me is False:
            # we are switched off
            self.log("*** Control by app is disabled. No stance change! ***", level="WARNING")
            return

        # calculate the SoC needed to be able to discharge for at least a whole hour.
        _min_soc: float = self.bats_min_soc + (1 * cs.MIN_DISCHARGE / 100)
        # calculate the power needed to discharge to the minimum SoC in an hour
        _min_pwr: float = (self.soc - self.bats_min_soc) * 100
        if _min_pwr < cs.MIN_DISCHARGE:
            _min_pwr = 0
        _q3 = self.price["stats"]["q3"]
        _slot = self.get_slot()

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
                    }).",
                    level="DEBUG",
                )
        else:
            stance = cs.NOM  # default stance is NOM

        # if it is a sunny day, batteries will charge automatically
        # and we don't want to discharge during the expensive timeslots
        # because that would drain the batteries and negatively affect
        # solar availability for the EV charger.
        # winterstand forces behaviour to a non-sunny day when true
        _sunny_day: bool = self.datum["sunny"] and not self.winterstand
        if _sunny_day and (self.soc > _min_soc) and (self.is_expensive(self.get_slot())):
            # For now we use NOM to avoid locking out the EV charger during "Grid Rewards".
            stance = cs.NOM
            self.log(
                f"Sunny day, expensive slot {(self.get_slot() / 4):.2f} and  SoC > {_min_soc:.2f}%, but requesting NOM stance.",
                level="INFO",
            )

        # this is supposed to charge the battery during the cheap hours in winter mimicking the ECO-mode
        # using ABC-concept (Always Be Charging) and ignore SoC or prv_stance,
        #       and charging *always* during the cheap slots.
        if not _sunny_day and (self.is_cheap(_slot)):
            self.log(
                f"Non-sunny day and cheap slot {(_slot / 4):.2f}, so requesting CHARGE stance.",
                level="INFO",
            )
            stance = cs.CHARGE

        # if prices are extremely high or low, we get greedy and switch to resp. DISCHARGE or CHARGE stance
        # on non-sunny days however we suppress the greedy feeling, knowing not what tomorrow might bring...
        match self.greedy:
            case -1:
                _l = f"Greedy for CHARGE. But too high SoC ({self.soc:.1f} %)."
                if (self.prv_stance == cs.CHARGE and self.soc < 99.9) or (self.soc < self.bats_min_soc):
                    _l = "Greedy for CHARGE. Requesting CHARGE stance."
                    stance = cs.CHARGE
                self.log(_l)
            case 1:
                _l = "Greedy for DISCHARGE. But unfavourable conditions."
                if (self.prv_stance == cs.DISCHARGE and self.soc > self.bats_min_soc) or (
                    _min_pwr > cs.MIN_DISCHARGE
                ):
                    # or (self.soc > _min_soc):
                    _l = f"Greedy for DISCHARGE. Requesting DISCHARGE stance. {_min_pwr:.0f} Wh available."
                    stance = cs.DISCHARGE
                self.log(_l)
            case _:
                pass  # not greedy, do nothing

        self.new_stance = stance
        self.calc_pwr_sp(self.new_stance)
        self.log("======================================================", level="DEBUG")

    def calc_pwr_sp(self, stance):
        """Calculate the power setpoints for the current stance."""
        match stance:
            case cs.NOM:
                self.pwr_sp_list = [0, 0]
                self.log("SP: No action required. Unit is in control (NOM).", level="DEBUG")
                if self.low_pv:
                    self.pwr_sp_list = [100, 100]
                    self.log("SP: Low PV detected, keeping setpoint.", level="INFO")
            case cs.IDLE:
                # self.pwr_sp_list = [0, 0]
                self.log("SP: No power setpoints. Unit is IDLE. ", level="DEBUG")
            case cs.CHARGE:
                _cp = int((100 - self.soc) * 100 / -2) * 4  # 2 batteries; 4 quarters
                _chrgpwr = max(cs.CHARGE_PWR, _cp)
                self.pwr_sp_list = [_chrgpwr, _chrgpwr]
                if self.ev_charging:
                    # EV charges at 5200 W
                    # limit battery charging to below 8000 W
                    # (allows for 2kW loads in the house)
                    # SP on P1 (grid target) = 5200 + 2690 = 7890 W
                    # SP on each battery = (7890 / -2) -3945 W
                    self.pwr_sp_list = [-3945, -3945]
                    self.log("SP: Reduced power setpoints because EV is charging. ", level="INFO")
                # self.step_cnt = self.steps
                self.log(
                    f"SP: Power setpoints calculated for {stance} stance: {self.pwr_sp_list} W",
                    level="INFO",
                )
            case cs.DISCHARGE:
                _dp = int((self.bats_min_soc - self.soc) * 100 / -2)  # * 4  # 2 batteries; 4 quarters
                _discpwr = min(cs.DISCHARGE_PWR, _dp)
                self.pwr_sp_list = [_discpwr, _discpwr]
                # self.step_cnt = self.steps
                self.log(
                    f"SP: Power setpoints calculated for {stance} stance: {self.pwr_sp_list} W",
                    level="INFO",
                )
            case _:
                self.logf(f"SP: No power setpoints calculated for unknown stance {stance}. ", level="ERROR")

    def adjust_pwr_sp(self):
        """Control each battery to the desired power setpoint."""
        xom_sp: int = 0
        for idx, (_n, _b) in enumerate(self.bat_ctrl.items()):
            if _n != "p1":
                _sp: int = int(self.pwr_sp_list[idx])
                xom_sp += _sp * -1  # invert the setpoint for the P1 meter
            # # not used when using XOM SP
            # _api = _b["api"]
            # try:
            #     if (self.prv_stance in ["API+", "API-"]) or (self.new_stance in ["API+", "API-"]):
            #         # NOM->API; IDLE->API; API->API; API->NOM; API->IDLE
            #         # _s: dict | str = _api.set_setpoint(_sp)
            #     else:
            #         _s = "IGNORED"
            # except Exception as her:
            #     _s = f"UNSUCCESFULL: {her}"
            if _n == "p1":
                _api = _b["api"]
                try:
                    _s: dict | str = _api.set_xom_setpoint(xom_sp)
                except Exception as her:
                    _s = f"UNSUCCESFULL: {her}"
                self.log(
                    f"Set XOM SP to ............... {xom_sp:+.0f} W  {_s} / {self.new_stance}", level="INFO"
                )

    def set_stance(self):
        """Set the current stance based on the current state."""
        match self.new_stance:
            case cs.NOM:
                # with contextlib.suppress(Exception):
                if self.ctrl_by_me:
                    self.adjust_pwr_sp()
                self.start_nom()
            case cs.IDLE:
                # with contextlib.suppress(Exception):
                if self.ctrl_by_me:
                    self.adjust_pwr_sp()
                self.start_idle()
            case cs.CHARGE:
                self.start_charge()
            case cs.DISCHARGE:
                self.start_discharge()
            case _:
                self.log(f"*** Unknown stance: {self.new_stance}. Switching to NOM.", level="ERROR")
                self.start_nom()

    def start_nom(self):
        """Start the NOM stance."""
        stance: str = cs.NOM
        if self.ctrl_by_me:
            # for bat in cs.BAT_STANCE:
            #     self.log(f"Setting {bat} to {stance}")
            #     self.set_state(bat, stance.lower())
            for bat in self.bat_ctrl:
                if bat != "p1":
                    _api = self.bat_ctrl[bat]["api"]
                    _s = _api.set_strategy(stance.lower())
                    self.log(f"Sent {bat} to {stance:>4} ........... {_s}", level="DEBUG")

    def start_idle(self):
        """Start the IDLE stance."""
        stance: str = cs.IDLE
        if self.ctrl_by_me:
            # for bat in cs.BAT_STANCE:
            #     self.log(f"Setting {bat} to {stance}")
            #     self.set_state(bat, stance.lower())
            for bat in self.bat_ctrl:
                if bat != "p1":
                    _api = self.bat_ctrl[bat]["api"]
                    _s = _api.set_strategy(stance.lower())
                    self.log(f"Sent {bat} to {stance:>4} ........... {_s}", level="DEBUG")

    def start_charge(self, power: int = cs.CHARGE_PWR):
        """Start the API- stance."""
        # stance: str = cs.CHARGE[:-1]
        # _s: dict = {"status": "skipped"}
        if self.ctrl_by_me:
            # # not used when using XOM SP
            # for bat in self.bat_ctrl:
            #     _api = self.bat_ctrl[bat]["api"]
            #     _s = _api.set_strategy(stance.lower())
            #     self.log(f"Sent {bat} to {stance:>4} ........... {_s}")
            if self.greedy != 0 or self.ev_charging:
                # override IDLE stance when prices are very low or EV is charging
                self.start_nom()
            self.adjust_pwr_sp()

    def start_discharge(self, power: int = cs.DISCHARGE_PWR):
        """Start the API+ stance."""
        # stance: str = cs.DISCHARGE[:-1]
        # _s: dict = {"status": "skipped"}
        if self.ctrl_by_me:
            # # not used when using XOM SP
            # for bat in self.bat_ctrl:
            #     _api = self.bat_ctrl[bat]["api"]
            #     _s = _api.set_strategy(stance.lower())
            #     self.log(f"Sent {bat} to {stance:>4} ........... {_s}")
            if self.greedy != 0:
                self.start_nom()
            self.adjust_pwr_sp()

    def get_slot(self) -> int:
        """Get the current slot."""
        _hr: int = dt.datetime.now().hour
        _mn: int = dt.datetime.now().minute
        _qrtr: int = 0
        _mul: int = 1
        if self.tibber_quarters:
            # callback will be either on the hour or on the quarter
            _mul = 4
            _qrtr = int(_mn // 15) * 15
        return int((_hr + _qrtr / 60) * _mul)

    def is_expensive(self, slot: float) -> bool:
        """Check if the current slot is in the list of expensive slots."""
        return slot in self.price["expen_slot"]

    def is_cheap(self, slot: float) -> bool:
        """Check if the current slot is in the list of cheap slots."""
        return slot in self.price["cheap_slot"]

    # SECRETS

    # def get_tibber(self) -> tuple[str, str]:
    #     """Get the Tibber token and URL from the secrets."""
    #     _scrt = self.secrets.get_tibber_token()
    #     _url = self.secrets.get_tibber_url()
    #     return _scrt, _url

    def get_bats(self):
        """Get the battery credentials from the secrets."""
        _auth_dict = {}
        for _b in ["bat1", "bat2", "p1"]:
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
