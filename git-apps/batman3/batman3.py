import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass
import const3 as cs
import prices3 as pr
import utils3 as ut
import json

"""BatMan3 App
Listen to changes in the battery state and control the charging/discharging based on energy prices and strategies.
"""


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

        # initialize Tibber connector
        self.tibber_sensor: str = self.secrets.get_tibber_sensor()  # type: ignore[attr-defined]
        self.tb = pr.Tibber(token=self.secrets.get_tibber_token(), url=self.secrets.get_tibber_url())
        self.tibber_prices: dict = {}

        # initialize store for price related info
        self.price: dict = {
            "today": [],  # todays prices per quarter
            "tomor": [],  # tomorrows prices per quarter
            "now": 0.0,  # current price
            "slot": {
                "charge": [],  # slots to be charging (greed)
                "lo": [],  # slots with cheap prices
                "norm": [],  # slots with normal prices
                "hi": [],  # slots with high prices
                "discharge": [],  # slots to be discharging (greed)
            },
            "stats": {},  # prices statistics
        }

        # Initialize various monitors with safe defaults ...
        self.bats_min_soc: float = 0.0  # [%]
        self.ctrl_by_me: bool = False  # whether the app is allowed to control the batteries
        self.ev_charging: bool = True  # whether the EV is charging
        self.low_pv: bool = False  # wether solarpanels or batteries are supplying electricity
        # These are for the overcurrent detection:
        self.pv_current: float = 0.0  # [A]; used to monitor PV overcurrent
        self.pv_power: int = 0  # [W]; used to control PV power
        self.pv_volt: float = 0.0  # [V]; used to control PV current
        # ... and make sure we get updates when these change ...
        self.set_call_backs()
        # ... then get their actual state
        self.get_monitor_states()
        self.update_tibber_prices()

        self.log("BatMan3 is running...", level="INFO")
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
        self.tibber_prices = pr.fetch_pricedict(
            token=self.secrets.get_tibber_token(),  # type: ignore[attr-defined]
            url=self.secrets.get_tibber_url(),  # type: ignore[attr-defined]
        )
        self.tb.fetch_pricedict()
        self.log(f"*** {len(self.tibber_prices)} TIBBER prices updated ***")
        self.log(f"{json.dumps(self.tibber_prices)}", level="INFO")
        self.log(f"{json.dumps(self.tb.prices, indent=2)}", level="INFO")
        """
        2026-04-11 19:04:02.862808 INFO batman3: *** TIBBER prices updated ***
        2026-04-11 19:04:02.864258 INFO batman3: {"2026-04-11 00:00:00": 30.69, "2026-04-11 00:15:00": 29.439999999999998, "2026-04-11 00:30:00": 28.04, "2026-04-11 00:45:00": 27.04, "2026-04-11 01:00:00": 28.17, "2026-04-11 01:15:00": 27.529999999999998, "2026-04-11 01:30:00": 26.69, "2026-04-11 01:45:00": 26.1, "2026-04-11 02:00:00": 26.88, "2026-04-11 02:15:00": 26.14, "2026-04-11 02:30:00": 26.08, "2026-04-11 02:45:00": 25.77, "2026-04-11 03:00:00": 26.1, "2026-04-11 03:15:00": 25.85, "2026-04-11 03:30:00": 25.82, "2026-04-11 03:45:00": 25.4, "2026-04-11 04:00:00": 25.919999999999998, "2026-04-11 04:15:00": 25.759999999999998, "2026-04-11 04:30:00": 25.64, "2026-04-11 04:45:00": 25.19, "2026-04-11 05:00:00": 25.679999999999996, "2026-04-11 05:15:00": 25.180000000000003, "2026-04-11 05:30:00": 25.19, "2026-04-11 05:45:00": 25.11, "2026-04-11 06:00:00": 25.35, "2026-04-11 06:15:00": 25.45, "2026-04-11 06:30:00": 25.480000000000004, "2026-04-11 06:45:00": 24.63, "2026-04-11 07:00:00": 25.790000000000003, "2026-04-11 07:15:00": 25.05, "2026-04-11 07:30:00": 23.44, "2026-04-11 07:45:00": 20.84, "2026-04-11 08:00:00": 25.069999999999997, "2026-04-11 08:15:00": 23.13, "2026-04-11 08:30:00": 20.7, "2026-04-11 08:45:00": 16.37, "2026-04-11 09:00:00": 19.93, "2026-04-11 09:15:00": 16.28, "2026-04-11 09:30:00": 14.530000000000001, "2026-04-11 09:45:00": 13.569999999999999, "2026-04-11 10:00:00": 14.499999999999998, "2026-04-11 10:15:00": 13.569999999999999, "2026-04-11 10:30:00": 13.450000000000001, "2026-04-11 10:45:00": 12.7, "2026-04-11 11:00:00": 13.450000000000001, "2026-04-11 11:15:00": 13.320000000000002, "2026-04-11 11:30:00": 12.770000000000001, "2026-04-11 11:45:00": 12.389999999999999, "2026-04-11 12:00:00": 12.139999999999999, "2026-04-11 12:15:00": 11.15, "2026-04-11 12:30:00": 10.54, "2026-04-11 12:45:00": 9.92, "2026-04-11 13:00:00": 10.48, "2026-04-11 13:15:00": 9.92, "2026-04-11 13:30:00": 9.92, "2026-04-11 13:45:00": 9.92, "2026-04-11 14:00:00": 9.92, "2026-04-11 14:15:00": 10.280000000000001, "2026-04-11 14:30:00": 10.77, "2026-04-11 14:45:00": 11.5, "2026-04-11 15:00:00": 12.139999999999999, "2026-04-11 15:15:00": 12.709999999999999, "2026-04-11 15:30:00": 13.309999999999999, "2026-04-11 15:45:00": 13.320000000000002, "2026-04-11 16:00:00": 13.55, "2026-04-11 16:15:00": 14.219999999999999, "2026-04-11 16:30:00": 15.0, "2026-04-11 16:45:00": 14.280000000000001, "2026-04-11 17:00:00": 13.370000000000001, "2026-04-11 17:15:00": 13.4, "2026-04-11 17:30:00": 15.42, "2026-04-11 17:45:00": 21.42, "2026-04-11 18:00:00": 14.180000000000001, "2026-04-11 18:15:00": 20.22, "2026-04-11 18:30:00": 24.62, "2026-04-11 18:45:00": 29.12, "2026-04-11 19:00:00": 22.39, "2026-04-11 19:15:00": 23.31, "2026-04-11 19:30:00": 24.47, "2026-04-11 19:45:00": 28.1, "2026-04-11 20:00:00": 26.99, "2026-04-11 20:15:00": 26.63, "2026-04-11 20:30:00": 26.479999999999997, "2026-04-11 20:45:00": 26.06, "2026-04-11 21:00:00": 27.889999999999997, "2026-04-11 21:15:00": 26.700000000000003, "2026-04-11 21:30:00": 25.4, "2026-04-11 21:45:00": 24.099999999999998, "2026-04-11 22:00:00": 29.609999999999996, "2026-04-11 22:15:00": 30.14, "2026-04-11 22:30:00": 28.18, "2026-04-11 22:45:00": 24.37, "2026-04-11 23:00:00": 25.669999999999998, "2026-04-11 23:15:00": 23.98, "2026-04-11 23:30:00": 22.49, "2026-04-11 23:45:00": 22.0}
        """

    def get_monitor_states(self):
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

        self.log_status("get_monitor_states")

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
        self.log_status("qrtStart")

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
        self.get_monitor_states()
        # self.log("WD_runin_cb")
        # self.log(f"Current stance              =  {self.new_stance}", level="DEBUG")

    def lowpv_runin_cb(self, entity, new, **kwargs):
        """Handle low PV condition changes."""
        self.get_monitor_states()
        self.log("lowpv_runin_cb")

    # CONTROL LOGIC

    # SECRETS

    def get_bats(self):
        """Get the battery credentials from the secrets."""
        _auth_dict = {}
        for _b in ["bat1", "bat2", "p1"]:
            _auth_dict[_b] = self.secrets.get_sessy_secrets(_b)  # type: ignore[attr-defined]
        return _auth_dict

    def log_status(self, callee: str):
        """Construct a status message and log it."""
        _C = "C" if self.ctrl_by_me else "c"
        _E = "E" if self.ev_charging else "e"
        _L = "l" if self.low_pv else "L"
        _override = self.sw_override
        _O = ""
        _S = "Z" if self.datum["sunny"] else "W"
        if _override:
            _O = "!"
            _S = _S.lower()

        _p = f"p={self.price["now"]:+7.3f} (__.___)"

        self.status = " ".join([_O, _C, _E, _L, _S, _p, f"<{callee}>"])
        self.log(self.status, level="INFO")
