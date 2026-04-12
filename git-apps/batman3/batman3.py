"""BatMan3 App
Listen to changes in the battery state and control the charging/discharging based on energy prices and strategies.
"""

import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass
import const3 as cs
import prices3 as pr
import utils3 as ut


class BatMan3(hass.Hass):
    def initialize(self):
        """Initialize the app."""
        self.debug: bool = cs.DEBUG
        self.log(f"===================================== BatMan3 v{cs.VERSION} ====", level="INFO")
        # Keep track of active callbacks
        self.starting = True
        self.callback_handles: list[Any] = []

        # create internal references
        self.secrets = self.get_app("scrts")
        self.battalk = self.get_app("battalk")

        # initialize date/time info
        self.datum: dict = ut.get_these_days()

        # initialize Tibber API
        self.tibber_sensor: str = self.secrets.get_tibber_sensor()  # type: ignore[attr-defined]
        self.tibber = pr.Tibber(
            token=self.secrets.get_tibber_token(),  # type: ignore[attr-defined]
            url=self.secrets.get_tibber_url(),  # type: ignore[attr-defined]
        )
        # Initialize various monitors with safe defaults ...
        self.bats_min_soc: float = 0.0  # [%]
        self.ctrl_by_me: bool = False  # whether the app is allowed to control the batteries
        self.ev_charging: bool = True  # whether the EV is charging
        self.low_pv: bool = False  # wether solarpanels or batteries are supplying electricity
        # these are for the overcurrent detection:
        self.pv_current: float = 0.0  # [A]; used to monitor PV overcurrent
        self.pv_power: int = 0  # [W]; used to control PV power
        self.pv_volt: float = 0.0  # [V]; used to control PV current
        # greed settings:
        self.greed_c: float = 0.00
        self.greed_d: float = 100.00
        # ... then get their actual state
        self.update_monitor_states()
        self.update_tibber_prices([self.greed_c, self.greed_d])
        # ... and finally make sure we get updates when these change ...
        self.set_call_backs()

        self.log("BatMan3 is running...", level="INFO")
        self.log_pricelist()
        self.log_status()
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
        if ut.is_midnight(dt.datetime.now()):
            self.tibber.update_prices([self.greed_c, self.greed_d]) # requires update_monitor_states() to have executed
            self.log_pricelist()
        else:
            self.tibber.update_current_price()

    def log_pricelist(self, _len=10):
        self.log(f"*** {len(self.tibber.prices)} TIBBER prices available ***")
        # convert to a list of formatted strings
        _fstrl = [f"{i:+06.2f}" for i in self.tibber.pricelist]
        _f = "\n".join([", ".join(_fstrl[i : i + _len]) for i in range(0, len(_fstrl), _len)])
        self.log(f"[ \n{_f} ]\n{self.tibber.statstext}", level="INFO")
        # self.log(f"{self.tibber.stats["Q1"]}")
        # self.log(f"{self.tibber.stats["Q2"]}")
        # self.log(f"{self.tibber.stats["Q3"]}")
        # self.log(f"{self.tibber.stats["Q4"]}")

    def update_monitor_states(self, caller: str = ""):
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
            # check if PV/BAT is delivering electricity
            _swo: Any = self.get_state(cs.ZOMWIN_OVERRIDE)
            self.sw_override = str(_swo) == "on"
        except BaseException:
            self.log("*** ZOMWIN_OVERRIDE state update failed")

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

        try:
            # get the greed settings
            _gc: Any = self.get_state(cs.GREED_C)
            self.greed_c = float(_gc)
            _gd: Any = self.get_state(cs.GREED_D)
            self.greed_d = float(_gd)
        except BaseException:
            self.log("*** GREED_C/D state update failed")

        msg = "gms"
        if caller:
            msg = f"{msg} by {caller}"
        # self.log_status(caller=msg)

    def set_call_backs(self) -> None:
        """Set-up callbacks for price changes and watchdogs."""
        quarter = 15  # [minutes]

        # Determine the time of the next callback for price updates.
        # (every quarter, 20 seconds in)
        now = dt.datetime.now()
        minutes = (now.minute // quarter + 1) * quarter
        next_quarter = now.replace(minute=0, second=0, microsecond=0) + dt.timedelta(
            minutes=minutes, seconds=20
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
        caller = "qrtStart"
        self.update_monitor_states(caller=caller)
        self.update_tibber_prices()
        self.log_status(caller=caller)

    def watchdog_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for changes to monitored automations."""
        self.log(f"*** Watchdog triggered by {entity} ({attribute}) changed: {old} -> {new}", level="INFO")
        # watchdog changes are not immediate, so we callback watchdog_runin_cb() after:
        _cb_delay = 2  # [s]  to allow the system to stabilize
        # low PV is a special case, because it needs different actions
        if entity == cs.LOW_PV:
            self.run_in(self.lowpv_runin_cb, delay=_cb_delay, entity=entity, new=new)
        else:
            self.run_in(
                self.watchdog_runin_cb, delay=_cb_delay, entity=entity, attribute=attribute, old=old, new=new
            )

    def watchdog_runin_cb(self, entity, attribute, old, new, **kwargs):
        """Delayed callback for watchdogs."""
        self.update_monitor_states(caller="WD_runin_cb")

    def lowpv_runin_cb(self, entity, new, **kwargs):
        """Handle low PV condition changes."""
        self.update_monitor_states(caller="lowpv_runin_cb")

    # CONTROL LOGIC

    # SECRETS

    def get_bats(self):
        """Get the battery credentials from the secrets."""
        _auth_dict = {}
        for _b in ["bat1", "bat2", "p1"]:
            _auth_dict[_b] = self.secrets.get_sessy_secrets(_b)  # type: ignore[attr-defined]
        return _auth_dict

    def log_status(self, caller: str):
        """Construct a status message and log it."""
        _C = "C" if self.ctrl_by_me else "c"
        _E = "E" if self.ev_charging else "e"
        _L = "L" if self.low_pv else "l"
        _override = self.sw_override
        _O = ""
        _S = "Z" if self.datum["sunny"] else "W"
        if _override:
            _O = "!"
            _S = _S.lower()

        _pn = self.tibber.price_now  # current price
        _pd = _pn - self.tibber.stats["q1"]  # difference with price at Q1
        _p = f"p={_pn:+06.2f} ({_pd:+06.2f})"
        _qn = self.tibber.quarter_now  # current quarter
        _q = f"{_p} @{_qn:02d} ({_qn / 4:05.2f})"

        self.status = " ".join([_O, _C, _E, _L, _S, _q, f"<{caller}>"])
        self.log(self.status, level="INFO")
