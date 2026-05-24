"""BatMan3

High-level Home Electricity Monitoring & Management System.
"""

import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass
import battalk3 as bt3
import const3 as cs
import prices3 as pr
import utils3 as ut


class BatMan3(hass.Hass):
    def initialize(self):
        """Initialize the app."""
        self.debug: bool = cs.DEBUG
        self.log(msg=f"===================================== BatMan3 v{cs.VERSION} ====", level="INFO")
        # Keep track of active callbacks
        self.starting = True
        self.callback_handles: list[Any] = []
        self.callback_time = dt.datetime.now()

        # create internal references
        self.secrets = self.get_app("scrts")
        # self.battalk = self.get_app("battalk")

        # initialize date/time info
        self.datum: dict = ut.get_these_days()
        # avoid re-entrancy of switcheroo
        self.swoo: bool = False

        # initialize Tibber API
        self.tibber_exc_cb = cs.CB_DELAY
        self.tibber_fail = False
        self.tibber_sensor: str = self.secrets.get_tibber_sensor()  # type: ignore[attr-defined]
        _limC: Any = self.get_state(cs.GREED_C)
        _limD: Any = self.get_state(cs.GREED_D)
        self.tibber = pr.Tibber(
            token=self.secrets.get_tibber_token(),  # type: ignore[attr-defined]
            url=self.secrets.get_tibber_url(),  # type: ignore[attr-defined]
            charge_limit=float(_limC),
            discharge_limit=float(_limD),
        )

        # initialize the battery API
        self.bat_ctrl: dict[str, Any] = self.get_bats(devices=cs.BATTALK["bats"])
        for _b in self.bat_ctrl:
            self.bat_ctrl[_b]["api"] = bt3.Sessy(
                url=self.bat_ctrl[_b]["url"],
                username=self.bat_ctrl[_b]["username"],
                password=self.bat_ctrl[_b]["password"],
                taip="bat",
            )
        self.soc_avg: float = 0.0
        self.soc_diff: float = 0.0
        self.get_bats_status()
        self.p1_ctrl: dict[str, Any] = self.get_cts(devices=cs.BATTALK["cts"])
        for _c in self.p1_ctrl:
            self.p1_ctrl[_c]["api"] = bt3.Sessy(
                url=self.p1_ctrl[_c]["url"],
                username=self.p1_ctrl[_c]["username"],
                password=self.p1_ctrl[_c]["password"],
                taip="p1",
            )
        self.xom_sp = 0
        self.get_cts_status()

        # Initialize various monitors with safe defaults ...
        self.bats_min_soc: float = 0.0  # [%]
        self.ctrl_by_me: bool = False  # whether the app is allowed to control the batteries
        self.ev_charging: bool = True  # whether the EV is charging
        self.low_pv: bool = False  # whether solarpanels or batteries are supplying enough electricity
        # These are for the overcurrent detection:
        self.pv_current: float = 0.0  # [A]; used to monitor PV overcurrent
        self.pv_power: int = 0  # [W]; used to control PV power
        self.pv_volt: float = 0.0  # [V]; used to control PV current
        # ... and make sure we get updates when these change ...
        self.watchdog_active: str = "starting"  # avoid callback while starting
        self.set_call_backs()
        # ... then get their actual state
        self.get_monitor_states()

        self.log(msg="BatMan3 is running...", level="INFO")
        self.log_pricelist()
        self.log_status(caller="INIT")

        self.watchdog_active: str = ""  # allow callbacks
        self.starting = False

    def terminate(self):
        """Clean up app."""
        self.log("__Terminating BatMan3...")
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("__...terminated BatMan3.")

    def update_tibber_prices(self) -> None:
        """Update the tibber price list a midnight otherwise just update the current price."""
        # make sure we have the current limit value for greedy dis-/charging
        _lim: Any = self.get_state(cs.GREED_C)
        self.tibber.set_greed_c_limit(float(_lim))
        _lim = self.get_state(cs.GREED_D)

        if ut.is_midnight(dt.datetime.now()) or self.tibber_fail:
            try:
                self.tibber.update_prices()  # call the API for new prices
                self.tibber.create_lists()
                self.tibber.set_greed_d_limit(float(_lim))
                self.log_pricelist()
            except Exception:
                self.tibber_fail = True
            else:
                self.tibber_fail = False
                self.tibber_exc_cb = cs.CB_DELAY  # reset callback timer on success
            self.tibber.set_greed_d_limit(float(_lim))
        else:
            self.tibber.set_greed_d_limit(float(_lim))
            self.tibber.update_current_price()  # lookup the price for the new quarter

    def get_monitor_states(self, caller: str = ""):
        """Get the state of all monitored entities."""
        # update the calendar/season info
        self.datum = ut.get_these_days()
        try:
            # minimum SoC required to provide power until next morning
            _bms: Any = self.get_state(cs.BAT_MIN_SOC)
            self.bats_min_soc = float(_bms)
        except BaseException:
            self.log("*** BAT_MIN_SOC state update failed")

        try:
            # check if we are allowed to control the batteries
            _ctrl: Any = self.get_state(cs.CTRL_BY_ME)
            self.ctrl_by_me = str(_ctrl) == "on"
        except BaseException:
            self.log("*** CTRL_BY_ME state update failed")

        try:
            # check whether the EV is currently charging
            _evc: Any = self.get_state(cs.EV_REQ_PWR)
            self.ev_charging = str(_evc) == "on"
        except BaseException:
            self.log("*** EV_REQ_PWR state update failed")

        try:
            # check if PV/BAT is delivering electricity
            _lpv: Any = self.get_state(cs.LOW_PV)
            self.low_pv = str(_lpv) == "on"
        except BaseException:
            self.log("*** LOW_PV state update failed")

        try:
            # check if zomer/winter override is active
            _swo: Any = self.get_state(cs.ZOMWIN_OVERRIDE)
            self.sw_override = str(_swo) == "on"
        except BaseException:
            self.log("*** ZOMWIN_OVERRIDE state update failed")

        try:
            # set price limits for forced charging/discharging behaviour
            _gc: Any = self.get_state(cs.GREED_C)
            self.tibber.set_greed_c_limit(float(_gc))
            _gd: Any = self.get_state(cs.GREED_D)
            self.tibber.set_greed_d_limit(float(_gd))
        except BaseException:
            self.log("*** GREED_LL/_HH state update failed")

        try:
            # get PV/BAT current and power values
            _pvc: Any = self.get_state(cs.PV_CURRENT)
            self.pv_current = float(_pvc)  # [A]
            _pvv: Any = self.get_state(cs.PV_VOLTAGE)
            self.pv_volt = int(float(_pvv))  # [V]
            _pvp: Any = self.get_state(cs.PV_POWER)
            self.pv_power = int(float(_pvp))  # [W]
        except BaseException:
            self.log("*** PV meter state update failed")

        self.get_bats_status()
        self.get_cts_status()

    def set_call_backs(self) -> None:
        """Set-up callbacks for price changes and watchdogs."""
        quarter = 15  # [minutes]

        # Determine the time of the next callback for price updates.
        # (every quarter and a couple of seconds in)
        now = dt.datetime.now()
        minutes = (now.minute // quarter + 1) * quarter
        next_quarter = now.replace(minute=0, second=0, microsecond=0) + dt.timedelta(
            minutes=minutes, seconds=cs.CB_DELAY
        )

        # `run_every` callbacks can't be cancelled !
        # so this one is not added to `callback_handles`
        self.run_every(
            callback=self.quarter_started_cb,
            start=next_quarter,
            interval=cs.PRICES["update_interval"],
        )

        # Set-up callbacks for watchdog changes
        # Minimum SoC is reached
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.BAT_MIN_SOC_WD))
        # App control is allowed or prohibited
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.CTRL_BY_ME))
        # EV starts charging
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.EV_REQ_PWR))
        # Summer/Winter override
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.ZOMWIN_OVERRIDE))
        # low PV detected continuously for 60s
        _duur = dt.timedelta(seconds=60)
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.LOW_PV, duration=_duur))
        # PV overcurrent detected
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.PV_CURRENT_WD))
        # charging greed level is changed
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.GREED_C))
        # discharging greed difference is changed
        self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.GREED_D))

    # CALLBACKS

    def quarter_started_cb(self, **kwargs) -> None:
        """Callback for current price change."""
        self.callback_time = dt.datetime.now()
        self.update_tibber_prices()
        if self.tibber_fail:
            self.run_in(self.exception_cb, delay=self.tibber_exc_cb)
            self.tibber_exc_cb *= 1.4
        else:
            self.get_monitor_states()
            self.run_in(self.controller_cb, delay=1, caller="qrtr")

    def exception_cb(self, **kwargs) -> None:
        """Callback for current price change."""
        # self.callback_time = dt.datetime.now()
        self.update_tibber_prices()
        if self.tibber_fail:
            self.run_in(self.exception_cb, delay=self.tibber_exc_cb)
            self.tibber_exc_cb *= 1.4
        else:
            self.get_monitor_states()
            self.run_in(self.controller_cb, delay=1, caller="EXCEPTION")

    def watchdog_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for changes to monitored automations."""
        if not self.watchdog_active:
            self.callback_time = dt.datetime.now()
            self.watchdog_active = entity.split(".")[-1]
            # watchdog changes are not immediate, so we callback watchdog_runin_cb() after:
            _cb_delay = 2  # [s]  to allow the system to stabilize
            self.run_in(
                self.watchdog_runin_cb,
                delay=_cb_delay,
                entity=str(entity),
                attribute=attribute,
                old=old,
                new=new,
            )

    def watchdog_runin_cb(self, entity: str, attribute, old, new, **kwargs):
        """Delayed callback for watchdogs."""
        self.get_monitor_states()
        # low PV may need different actions
        if entity == cs.LOW_PV:
            self.lowpv_handler(state=str(new))

        self.run_in(self.controller_cb, delay=1, caller="wdog")

    def lowpv_handler(self, state: str):
        """Handle low PV condition changes."""
        match state:
            case "on" | "off":
                # Only update if state actually changes
                new_state = state == "on"
                if self.low_pv != new_state:
                    self.low_pv = new_state
            case _:
                self.log(msg=f"*** Invalid value for LowPV: {state}. No action taken.", level="ERROR")

    # CONTROL LOGIC

    def controller_cb(self, caller, **kwargs):
        """Controller callback."""
        # fmt: off
        _reason: str = "nix"  # no action
        _strategy: str = cs.DEFAULT_STANCE
        _setpoint: int = cs.DEFAULT_XOM_SP  # 0 W
        _soc_gt_min: bool = self.soc_avg > self.bats_min_soc  # Avg SoC is above the lower limit line

        #  low prices should not do anything...
        _cq1: bool = (self.tibber.quarter_now in self.tibber.charge_cheap
                      and not _soc_gt_min
                      )
        # ...unless we're in winter, when we charge during low price quarters upto the minimum SoC.
        _Wq1: bool = (not self.datum["sunny"]
                      or (self.sw_override and self.datum["sunny"])
                      )
        # when prices are very low we charge completely
        _gLL = self.tibber.quarter_now in self.tibber.charge_greed

        # high prices should not do anything...
        _dq3: bool = (self.tibber.quarter_now in self.tibber.disch_expen
                and _soc_gt_min
                )
        # ...unless we're in summer, when we discharge down to the minimum SoC.
        _Zq3: bool = (self.datum["sunny"]
                or (self.sw_override and not self.datum["sunny"])
                )
        # when prices are very high we discharge down to the minimum SoC
        _gHH: bool = (self.tibber.quarter_now in self.tibber.disch_greed
                and _soc_gt_min
                )

        if self.ctrl_by_me:
            _reason = "ctl"  # control by me, no action
            if not self.ev_charging:
                _reason = "x0m"  # EV not charging, XOM = 0, Q2
                _strategy = cs.NOM
                _setpoint = cs.DEFAULT_XOM_SP
                # force battery to start-up when we have low power from PV/S
                if self.low_pv:
                    _reason = "lpv"  # Low PV
                    _strategy = cs.NOM
                    _setpoint = -200

                # _cq1 & _Wq1
                if _cq1:
                    _reason = "cq1"  # Low price (<q1)
                    _strategy = cs.NOM
                    if _Wq1:
                        _reason = "Wq1"
                        _setpoint = cs.MAX_CHARGE_SP

                # first check if we're greedy, then check if price > q3
                elif _gHH:
                    _reason = "gHH"  # High price (>HH), request discharge
                    _strategy = cs.NOM
                    _setpoint = self.calc_setpoint(max=cs.MAX_DISCHARGE_SP)

                # _dq3 & _Zq3
                elif _dq3:
                    _reason = "dq3"  # High price (>q3)
                    _strategy = cs.NOM
                    if _Zq3:
                        _reason = "Zq3"
                        # TODO: discharge only if price is high enough
                        # _setpoint = int(self.calc_setpoint(max=cs.MAX_DISCHARGE_SP) * cs.ADJUST_SP)

            # if EV is charging:
            else:
                _reason = "evc"  # EV charging, IDLE
                _strategy = cs.IDLE

            # regardless of the EV charging state, if prices are extremely low we will charge
            if _gLL:
                _reason = "gLL"  # Low price (< LL), charge always, ignore EV state
                _strategy = cs.NOM
                _setpoint = cs.MAX_P1_ABS

            # _ = self.calc_setpoint()  # for debugging
            self.set_mode(strategy=_strategy, grid_target=_setpoint)
            # switcheroo the batteries regularly when on normal duty
            if not self.swoo: # and _reason not in ["gLL", "gHH"]:
                self.switcheroo()  # check battery SoC before we leave
        self.log_status(caller=f"-{caller}({_reason} {_strategy} {_setpoint})")
        self.watchdog_active = ""
        # fmt:on

    def calc_setpoint(self, max: int) -> int:
        """Calculate the setpoint for the grid target based on
        the current system state and assuming we want to discharge.
        """
        _setpoint: int = -1 * cs.MAX_P1_ABS
        _distance: float = self.soc_avg - self.bats_min_soc
        # max discharging = (2*1700W) -34%/h; -8.5%/qrtr
        # if _distance > (4*8.5=)34 we can discharge at maximum speed.
        #    Below that we have 4 quarters (1hr) left
        _distance_limit: float = -1 * max / (4 * 100) * 4  # = 34.0
        if _distance < _distance_limit:
            _setpoint = int(max * (_distance / _distance_limit))  # / 4
        if _distance < cs.APPROACH_LIM:
            # don't discharge when approaching bats_min_soc
            _setpoint = 0
        self.log(
            msg=f"*** Calculated SP : {int(_setpoint)} {max} {_distance:.1f} < {_distance_limit:.1f} ***",
            level="INFO",
        )
        return _setpoint

    def set_mode(self, strategy: str, grid_target: int) -> None:
        """Set the strategy for each battery and the gridtarget."""
        # when enabling this code, disable batman2 FIRST
        for _bat in self.bat_ctrl:
            self.bat_ctrl[_bat]["api"].set_strategy(strategy)
        for _ct in self.p1_ctrl:
            self.p1_ctrl[_ct]["api"].set_xom_setpoint(grid_target)

    def switcheroo(self) -> None:
        """Keep SoC of batteries close together.

        If difference in SoC of batteries is greater than XX, set one battery to IDLE
        """
        _cb_delay: int = 60
        _soc: list = []
        _pwr: list = []
        bat_to_stop: str = "-"
        for _bat in self.bat_ctrl:
            _soc.append(self.bat_ctrl[_bat]["api"].status["sessy"]["state_of_charge"])
            _pwr.append(int(self.bat_ctrl[_bat]["api"].pwr_sp))
        _big_diff: bool = abs(self.soc_diff) > cs.SWITCHEROO_DIFF
        if _big_diff:  # difference in SoC is too big
            # 1 battery must be busy
            _idx0 = [i for i, v in enumerate(_pwr) if v != 0]
            if _idx0 and len(_idx0) == 1:  # only one of the batteries is busy
                _sp = _pwr[_idx0[0]]  # setpoint of active battery
                _sc = _soc[_idx0[0]]  # SoC of active battery
                # if the active battery has highest SOC AND is charging
                # OR
                # if the active battery has lowest SOC AND is discharging, we put it in IDLE:
                if (_sc == max(_soc) and _sp < 0) or (_sc == min(_soc) and _sp > 0):
                    bat_to_stop = f"bat{int(_idx0[0] + 1)}"
                    for _bat in self.bat_ctrl:
                        if _bat == bat_to_stop:
                            self.bat_ctrl[_bat]["api"].set_strategy(cs.IDLE)
                        else:
                            # always make sure the other battery is in NOM
                            self.bat_ctrl[_bat]["api"].set_strategy(cs.NOM)
                        self.bat_ctrl[_bat]["api"].update_strategy()
                    # wait for one minute then reset the states
                    self.run_in(
                        self.switcheroo_cb,
                        delay=_cb_delay,
                        bat_to_stop=bat_to_stop,
                    )
                    self.swoo = True
                    # self.log_status(caller=f"-swoo {bat_to_stop} OFF")

    def switcheroo_cb(self, kwargs: dict):
        """Return to previous state before self.switcheroo was called"""
        self.callback_time = dt.datetime.now()
        self.swoo = False
        _arg = kwargs.get("bat_to_stop")
        for _bat in self.bat_ctrl:
            self.bat_ctrl[_bat]["api"].set_strategy(cs.NOM)

        self.get_monitor_states()
        self.log_status(caller=f"-swoo {_arg} ON")

    # SECRETS

    def get_bats(self, devices: list[str]) -> dict:
        """Get the battery credentials from the secrets."""
        _auth_dict = {}
        for _b in devices:
            _auth_dict[_b] = self.secrets.get_sessy_secrets(_b)  # type: ignore[attr-defined]
        return _auth_dict

    def get_cts(self, devices: list[str]) -> dict:
        """Get the P1 credentials from the secrets."""
        return self.get_bats(devices)

    def get_bats_status(self) -> None:
        """Get the battery status."""
        _soc_lst = []
        for _b in self.bat_ctrl:
            self.bat_ctrl[_b]["api"].update_status()
            # self.bat_ctrl[_b]["api"].update_strategy()
            """example: >
            {
              "status": "ok",
              "sessy": {
                "state_of_charge": 0.8899999856948853,
                "power": -2037,
                "external_power": 0,
                "pack_voltage": 55300,
                "power_setpoint": -2061,
                "system_state": "SYSTEM_STATE_RUNNING_SAFE",
                "system_state_details": "",
                "frequency": 49975,
                "inverter_current_ma": -8725,
                "strategy_overridden": false
              },
              "renewable_energy_phase1": {
                "voltage_rms": 231276,
                "current_rms": 8952,
                "power": 2078
              },
              "renewable_energy_phase2": {
                "voltage_rms": 0,
                "current_rms": 0,
                "power": 0
              },
              "renewable_energy_phase3": {
                "voltage_rms": 0,
                "current_rms": 0,
                "power": 0
              }
            }
            """
            _soc_lst.append(self.bat_ctrl[_b]["api"].status["sessy"]["state_of_charge"])
            _strat: str = self.bat_ctrl[_b]["api"].strategy
            # translate strategy
            try:
                self.bat_ctrl[_b]["strategy"] = cs.BATTALK["bat_stances"][_strat]
            except KeyError:
                self.bat_ctrl[_b]["strategy"] = "UNK"
        self.soc_avg = (sum(_soc_lst) / len(_soc_lst)) * 100  # %
        self.soc_diff = (_soc_lst[0] - _soc_lst[1]) * 100  # (+)-ve value : bat1 > bat2

    def get_cts_status(self) -> None:
        """Get the CT status."""
        for _c in self.p1_ctrl:
            self.p1_ctrl[_c]["api"].update_status()
            """example: >
                {
                  "status": "ok",
                  "state": "P1_OK",
                  "dsmr_version": 20,
                  "header_info": "KMP5 KA6U00>>censored<<",
                  "equipment_identifier": ">>censored<<",
                  "date_time": "",
                  "power_consumed_tariff1": 29417906,
                  "power_produced_tariff1": 3793024,
                  "power_consumed_tariff2": 16284334,
                  "power_produced_tariff2": 9394014,
                  "tariff_indicator": 2,
                  "power_consumed": 0,
                  "power_produced": 0,
                  "power_total": 0,
                  "power_failure_any_phase": 0,
                  "long_power_failure_any_phase": 0,
                  "voltage_sag_count_l1": 0,
                  "voltage_sag_count_l2": 0,
                  "voltage_sag_count_l3": 0,
                  "voltage_swell_count_l1": 0,
                  "voltage_swell_count_l2": 0,
                  "voltage_swell_count_l3": 0,
                  "voltage_l1": 0,
                  "voltage_l2": 0,
                  "voltage_l3": 0,
                  "current_l1": 0,
                  "current_l2": 0,
                  "current_l3": 0,
                  "power_consumed_l1": 0,
                  "power_consumed_l2": 0,
                  "power_consumed_l3": 0,
                  "power_produced_l1": 0,
                  "power_produced_l2": 0,
                  "power_produced_l3": 0,
                  "gas_meter_equipment_identifier": "",
                  "gas_meter_value_time": "",
                  "gas_meter_value": 0
                }
            """
            self.xom_sp = self.p1_ctrl[_c]["api"].pwr_sp
            """
                {
                  "status": "ok",
                  "grid_target": 0      <<<
                }
            """

    def log_status(self, caller: str):
        """Construct a status message and log it."""
        _C = "C" if self.ctrl_by_me else "."
        _E = "E" if self.ev_charging else "."
        _L = "L" if self.low_pv else "."
        _override = self.sw_override
        _O = ""
        _S = "Z" if self.datum["sunny"] else "W"
        if _override:
            _O = "!"
            _S = _S.lower()

        _pn = self.tibber.price_now  # current price
        _pd = _pn - self.tibber.stats["q1"]  # difference with price at Q1
        _p = f" p={_pn:+06.2f}/{_pd:+06.2f}"
        _qn = self.tibber.quarter_now  # current quarter
        _q = f"{_p} @{_qn:02d}/{_qn / 4:05.2f}"

        _bp: int = 0
        _bs: list = []
        _str: list = []
        _bsp: int = 0
        for _b in self.bat_ctrl:
            _bp = int(round(self.bat_ctrl[_b]["api"].status["sessy"]["state_of_charge"] * 100, 0))
            _bs.append(cs.BATTALK["bat_stances"][self.bat_ctrl[_b]["api"].strategy])
            _bsp = int(self.bat_ctrl[_b]["api"].pwr_sp)
            _strl = [f"[{_bp:03d}]"]
            if _bsp >= 0:
                _strl.append(f"{_bsp:4d}")
            else:
                _strl.insert(0, f"{abs(_bsp):4d}")
            _str.append(">".join(_strl))
        _bts = f" |{_str[0]}:{_bs[0]}|{_str[1]}:{_bs[1]}|d={self.soc_diff:.1f}"
        _wd: str = self.watchdog_active
        _time = (dt.datetime.now() - self.callback_time).total_seconds()
        self.status = "".join([_O, _C, _E, _L, _S, _q, _bts, f" <{caller}@{_time:.3f} {_wd}"])
        self.log(self.status, level="INFO")

    def log_pricelist(self, _len: int = 10):
        self.log(f"*** {len(self.tibber.prices)} TIBBER prices available ***")
        # convert to a list of formatted strings
        _fstrl = [f"{i:+06.2f}" for i in self.tibber.pricelist]
        _f = "\n  :  ".join([", ".join(_fstrl[i : i + _len]) for i in range(0, len(_fstrl), _len)])
        self.log(f"[\n  :  {_f} ]\n{self.tibber.statstext}", level="INFO")
        self.log(f"<{self.tibber.greed_c_limit:+6.2f} : {self.tibber.charge_greed}", level="INFO")
        self.log(f"< q1    : {self.tibber.charge_cheap}", level="INFO")
        self.log(f"> q3    : {self.tibber.disch_expen}", level="INFO")
        self.log(f">{self.tibber.greed_d_limit:+6.2f} : {self.tibber.disch_greed}", level="INFO")
