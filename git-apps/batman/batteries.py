import datetime as dt
import time
from collections import deque
from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs
import utils as ut

"""Handle energy batteries for Batman app."""


class Batteries(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        self.log(f"===================================== Batteries v{cs.VERSION} ====")
        # Keep track of active callbacks
        self.callback_handles: list[Any] = []

        self.app_ctrl = "unknown"
        self.ev_needs_pwr = "unknown"
        self.interlock = False
        self.update_time: float = 0.0
        self.keep_vote = ["NOM"]

        self.bats = cs.BATTERIES
        self.mgr = self.get_app(self.bats["manager"])
        if not self.mgr:
            self.log(f"__ERROR: {self.bats['manager']} app not found!", level="ERROR")
            return

        # when debugging & first run:
        # log everything
        for bat in self.bats["entity"]:
            _e: dict[str, Any] = self.get_state(entity_id=bat, attribute="all")
            for _k, _v in _e.items():
                self.log(f"_{bat}___{_k}: {_v}", level="DEBUG")

        # Set previous SoC and current SoC to actual values
        self.bats["soc"]["now"], self.bats["soc"]["states"] = self.get_soc()
        self.bats["soc"]["prev"] = self.bats["soc"]["now"]
        self.bats["soc"]["speeds"] = deque(maxlen=3)
        # update battery state info
        self.update_socs()
        # update switch states
        self.ev_charging_changed("", "", self.ev_needs_pwr, "new")
        self.ctrl_by_app_changed("", "", self.app_ctrl, "new")

        now = dt.datetime.now()
        run_at = ut.next_half_hour(now)
        # Update in half an hour
        self.run_at(self.update_soc_cb, run_at)

        # callback when EV charging starts or stops
        self.callback_handles.append(self.listen_state(self.ev_charging_cb, self.bats["evneedspwr"]))
        # callback when manual override changes
        self.callback_handles.append(self.listen_state(self.ctrl_by_app_cb, self.bats["ctrlbyapp"]))

    def terminate(self):
        """Clean up app."""
        self.log("__Terminating Batteries...")
        # some cleanup code goes here
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("__...terminated Batteries.")

    def get_soc(self) -> tuple[float, list[float]]:
        """Get current state of charge (SoC) for all batteries."""
        soc_list: list[float] = []
        for bat in self.bats["entity"]:
            _soc: Any | None = self.get_state(entity_id=bat, attribute=self.bats["attr"]["soc"])
            if _soc is not None:
                soc_list.append(float(_soc))
            else:
                soc_list.append(0.0)
        soc_now: float = sum(soc_list) / len(soc_list) if soc_list else 0.0
        return soc_now, soc_list

    def update_socs(self):
        if (time.time() - self.update_time) > 60:
            self.update_time = time.time()
            # remember previous SoC and calculate new SoC
            self.bats["soc"]["prev"] = self.bats["soc"]["now"]
            self.bats["soc"]["now"], self.bats["soc"]["states"] = self.get_soc()

            # calculate speed of change
            current_speed = (self.bats["soc"]["now"] - self.bats["soc"]["prev"]) / (cs.POLL_SOC / 60)
            # keep a list of recent speeds. (list automagically keeps a length of 3; deque)
            self.bats["soc"]["speeds"].append(current_speed)
            # calculate average of recent speeds
            self.bats["soc"]["speed"] = sum(self.bats["soc"]["speeds"]) / len(self.bats["soc"]["speeds"])

            self.mgr.tell(
                self.bats["name"],
                f"Current SoC = {self.bats["soc"]["now"]:.1f} % changing at {
                    self.bats["soc"]["speed"]:.2f
                } %/h",
            )
            veto = False
            required_soc = ut.hours_until_next_10am() * self.bats["baseload"]
            vote: list = self.keep_vote
            if self.bats["soc"]["now"] > self.bats["soc"]["h_limit"]:
                vote = ["API,1701"]  # DISCHARGE
            if self.bats["soc"]["now"] > self.bats["soc"]["hh_limit"]:
                vote = ["API,1702"]  # BATTERY FULL, DISCHARGE
            if self.bats["soc"]["now"] < required_soc:
                vote = ["NOM"]  # NOM to survive the night
            if self.bats["soc"]["now"] < self.bats["soc"]["l_limit"]:
                vote = ["API,-2201"]  # CHARGE
            if self.bats["soc"]["now"] < self.bats["soc"]["ll_limit"]:
                vote = ["API,-2202"]  # BATTERY EMPTY, CHARGE
            self.keep_vote = vote
            # available part of SoC allowing for minimum required SoC
            soc_avail = self.bats["soc"]["now"] - required_soc

            # number of minutes left to reaching minimum required SoC if discharging at maximum rate
            min_to_req: int = int(soc_avail / 34.0 * 60)
            self.mgr.tell(self.bats["name"], f"Need {required_soc:.1f} % to last until next morning")
            if 0 < min_to_req < 60:
                self.mgr.tell(
                    self.bats["name"], f"At full discharge rate this will be reached in {min_to_req} min"
                )
                run_at = dt.datetime.now() + dt.timedelta(minutes=min_to_req)
                self.run_at(self.minimum_soc_cb, run_at)
            self.mgr.vote(self.bats["name"], vote, veto)

    def ev_charging_changed(self, entity, attribute, old, new, **kwargs):
        self.ev_needs_pwr = self.get_state(self.bats["evneedspwr"])
        self.log(f"EV charging status changed {old} -> {self.ev_needs_pwr}")
        self.update_socs()
        if self.ev_needs_pwr == "on":
            # EV power usage forces batteries to IDLE. Activate the interlock
            self.interlock = True
        if self.ev_needs_pwr == "off":
            # EV stopped charging. Deactivate the interlock
            self.interlock = False

    def ctrl_by_app_changed(self, entity, attribute, old, new, **kwargs):
        self.app_ctrl = self.get_state(self.bats["ctrlbyapp"])
        self.log(f"App ctrl status changed {str(old)} -> {self.app_ctrl}")
        self.update_socs()

    # CALLBACKS

    def update_soc_cb(self, **kwargs) -> None:
        """Callback to update state of charge."""
        self.update_socs()
        # Update again in half an hour
        run_at = ut.next_half_hour(dt.datetime.now())
        self.run_at(self.update_soc_cb, run_at)

    def minimum_soc_cb(self, **kwargs) -> None:
        """Callback to update state of charge and take action for minimum SoC."""
        self.update_socs()
        # Do stuff to stop discharging


    def ev_charging_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for EV charging state change."""
        self.ev_charging_changed(entity, attribute, old, new, **kwargs)

    def ctrl_by_app_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for CtrlByApp state change."""
        self.ctrl_by_app_changed(entity, attribute, old, new, **kwargs)


"""
Voting:

required_soc = 2 * (hours until 09:00)

(1)
SoC > h_limit   DISCHARGE
SoC < l_limit   CHARGE

(2)
SoC < soc_limit NOM

"""
