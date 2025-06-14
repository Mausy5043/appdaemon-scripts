import datetime as dt
from typing import Any
import utils as ut

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs

"""Handle energy batteries for Batman app."""


class Batteries(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        self.log(f"===================================== Batteries v{cs.VERSION} ====")
        # Keep track of active callbacks
        self.callback_handles: list[Any] = []

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
        self.update_socs()

        now = dt.datetime.now()
        run_at = ut.next_half_hour(now)
        # Update in half an hour
        self.callback_handles.append(self.run_at(self.update_soc_cb, run_at))

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
        self.mgr.tell(self.bats["name"], f"Total SoC = {soc_now} % <- {soc_list} %")
        return soc_now, soc_list

    def update_socs(self):
        # remember previous SoC and calculate new SoC
        self.bats["soc"]["prev"] = self.bats["soc"]["now"]
        self.bats["soc"]["now"], self.bats["soc"]["states"] = self.get_soc()

        # calculate speed of change
        self.bats["soc"]["speeds"].append(
            (self.bats["soc"]["now"] - self.bats["soc"]["prev"]) / (cs.POLL_SOC / 60)
        )
        self.bats["soc"]["speed"] = (
            sum(self.bats["soc"]["speeds"]) / len(self.bats["soc"]["speeds"])
            if self.bats["soc"]["speeds"]
            else 0.0
        )
        # Keep only a few speeds to avoid too much influence on prediction
        if len(self.bats["soc"]["speeds"]) > 3:
            self.bats["soc"]["speeds"].pop(0)
        self.mgr.tell(self.bats["name"], f"Speed of change = {self.bats["soc"]["speed"]:.2f} %/h")
        veto = False
        vote = "NOM"
        if self.bats["soc"]["now"] > self.bats["soc"]["h_limit"]:
            vote = "API(1700)"   # DISCHARGE
        if self.bats["soc"]["now"] > self.bats["soc"]["hh_limit"]:
            vote = "API(1700)"   # BATTERY FULL
        if self.bats["soc"]["now"] < self.bats["soc"]["l_limit"]:
            vote = "API(-2200)"  # CHARGE
        if self.bats["soc"]["now"] < self.bats["soc"]["ll_limit"]:
            vote = "NOM"  # BATTERY EMPTY
        self.mgr.vote(self.bats["name"], vote, veto)

    # CALLBACKS

    def update_soc_cb(self, **kwargs) -> None:
        """Callback to update state of charge."""
        self.update_socs()
        # Update again in half an hour
        now = dt.datetime.now()
        run_at = ut.next_half_hour(now)
        self.callback_handles.append(self.run_at(self.update_soc_cb, run_at))


"""
Voting:

soc_limit = (speed of discharge) * (hours until 09:00)

SoC > soc_limit     DISCHARGE
SoC < soc_limit     NOM

"""
