import datetime as dt
from logging import DEBUG
from typing import Any

import appdaemon.plugins.hass.hassapi as hass
import const3 as cs
import prices3 as pr
import utils3 as ut

"""BatMan3 App
Listen to changes in the battery state and control the charging/discharging based on energy prices and strategies.
"""


class BatMan3(hass.Hass):
    def initialize(self):
        """Initialize the app."""
        self.log(f"===================================== BatMan3 v{cs.VERSION} ====", level="INFO")
        # Keep track of active callbacks
        self.starting = True
        self.callback_handles: list[Any] = []

        # create internals
        self.debug: bool = cs.DEBUG
        self.secrets = self.get_app("scrts")
        self.battalk = self.get_app("battalk")

        self.datum: dict = ut.get_these_days()
        self.tibber_sensor: str = self.secrets.get_tibber_sensor()  # type: ignore[attr-defined]
        self.price: dict = {
            "today": [],
            "tomor": [],
            "now": 0.0,
            "cheap_slot": [],
            "expen_slot": [],
            "stats": {},
        }
        # initialise various monitors
        self.ev_charging: bool = False
        self.ctrl_by_me: bool = True  # whether the app is allowed to control the batteries
        self.bats_min_soc: float = 0.0
        self.pv_current: float = 0.0  # A; used to monitor PV overcurrent
        self.pv_volt: float = 0.0  # V; used to control PV current
        self.pv_power: int = 0  # W
        self.low_pv = self.get_state(cs.LOW_PV) == "on"

        self.set_call_backs()
        # update monitors with actual data
        #self.update_price_states()

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

    def set_call_backs(self) -> None:
        """Set-up callbacks for price changes and watchdogs."""
        quarter = 15

        # Determine the time of the next callback for price updates.
        now = dt.datetime.now()
        minutes = (now.minute // quarter + 1) * quarter
        next_quarter = now.replace(minute=0, second=0, microsecond=0) + dt.timedelta(
            minutes=minutes, seconds=20
        )
        # run_every callbacks can't be cancelled !
        # so this one is not added to calback_handles
        self.run_every(
            callback=self.quarter_started_cb,
            start=next_quarter,
            interval=cs.PRICES["update_interval"],
        )

        # Set-up callbacks for watchdog changes
        # #EV starts charging
        # self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.EV_REQ_PWR))
        # # App control is allowed or prohibited
        # self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.CTRL_BY_ME))
        # # Minimum SoC is reached
        # self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.BAT_MIN_SOC_WD))
        # # PV overcurrent detected
        # self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.PV_CURRENT_WD))
        # # charging greed level is changed
        # self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.GREED_LL))
        # # discharging greed difference is changed
        # self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.GREED_HH))
        # # low PV detected continuously for 60s
        # _duur = dt.timedelta(seconds=60)
        # self.callback_handles.append(self.listen_state(self.watchdog_cb, cs.LOW_PV, duration=_duur))

    # CALLBACKS

    def quarter_started_cb(self, **kwargs) -> None:
        """Callback for current price change."""
        self.log("*** Quarter started.", level="INFO")

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
        #self.update_states()
        # determine the new stance ...
        #self.calc_stance()
        # ... and set it
        #self.set_stance()
        # Log the current stance
        self.log("*** watchdog_runin_cb", level="INFO")
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


    # SECRETS

    def get_bats(self):
        """Get the battery credentials from the secrets."""
        _auth_dict = {}
        for _b in ["bat1", "bat2", "p1"]:
            _auth_dict[_b] = self.secrets.get_sessy_secrets(_b)  # type: ignore[attr-defined]
        return _auth_dict
