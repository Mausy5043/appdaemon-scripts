import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass
import const3 as cs
import utils3 as ut

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

        # update monitors with actual data
        # self.update_price_states()

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

    def get_monitor_states(self):
        """Get the state of all monitored entities."""
        # update the calendar/season info
        self.datum = ut.get_these_days()
        # minimum SoC required to provide power until next morning
        _bms: Any = self.get_state(cs.BAT_MIN_SOC)
        self.bats_min_soc = float(_bms)

        # check if we are allowed to control the batteries
        _ctrl: Any = self.get_state(cs.CTRL_BY_ME)
        self.ctrl_by_me = str(_ctrl) == "on"
        # check whether the EV is currently charging
        _evc: Any = self.get_state(cs.EV_REQ_PWR)
        self.ev_charging = str(_evc) == "on"
        # check if PV/BAT is delivering electricity
        _lpv: Any = self.get_state(cs.LOW_PV)
        self.low_pv = str(_lpv) == "on"

        # get PV/BAT current and power values
        _pvc: Any = self.get_state(cs.PV_CURRENT)
        self.pv_current = float(_pvc)  # [A]
        _pvv: Any = self.get_state(cs.PV_VOLTAGE)
        self.pv_volt = int(float(_pvv))  # [V]
        _pvp: Any = self.get_state(cs.PV_POWER)
        self.pv_power = int(float(_pvp))  # [W]
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
        self.log("WD_runin_cb")
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

        _C = "C" if self.ctrl_by_me else "c"
        _E = "E" if self.ev_charging else "e"
        _L = "l" if self.low_pv else "L"
        _override = False
        _S = "Z" if self.datum["sunny"] else "W"
        if _override:
            _S = _S.lower()

        _p = f"p={self.price["now"]:+7.3f} (__.___)"
        self.status = " ".join([_C, _E, _L, _S, _p, f"<{callee}>"])
        self.log(self.status, level="INFO")
