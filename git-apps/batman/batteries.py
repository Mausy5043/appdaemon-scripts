import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs

"""Handle energy batteries for Batman app."""


class Batteries(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        self.log(f"===================================== Batteries v{cs.VERSION} ====")
        # Keep track of active callbacks
        self.callback_handles: list[Any] = []

        self.batteries = cs.BATTERIES
        self.mgr = self.get_app(self.batteries["manager"])
        if not self.mgr:
            self.log(f"__ERROR: {self.batteries['manager']} app not found!", level="ERROR")
            return

        # when debugging & first run:
        # log everything
        for bat in self.batteries["entitys"]:
            _e: dict[str, Any] = self.get_state(entity_id=bat, attribute="all")
            for _k, _v in _e.items():
                self.log(f"_{bat}___{_k}: {_v}", level="INFO")

        # Set previous SoC and current SoC to actual values
        self.soc_prev, self.bat_state = self.get_soc()
        self.soc_now: float = self.soc_prev

        now = dt.datetime.now()
        # get number of seconds to the next polling interval
        seconds_to_next_half_hour: int = (cs.POLL_SOC - now.minute % cs.POLL_SOC) * 60 - now.second
        # Update in half an hour
        self.run_in(self.update_soc_cb, dt.timedelta(seconds=seconds_to_next_half_hour))


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
        for bat in self.batteries["entity"]:
            _soc: Any | None = self.get_state(entity_id=bat, attribute=cs.CUR_SOC_ATTR)
            if _soc is not None:
                soc_list.append(float(_soc))
            else:
                soc_list.append(0.0)
        soc_now: float = sum(soc_list) / len(soc_list) if soc_list else 0.0
        self.log(f"__Total SoC = {soc_now} % <- {soc_list} %")
        return soc_now, soc_list

    def update_soc_cb(self, **kwargs) -> None:
        """Callback to update state of charge."""
        # remember previous SoC and calculate new SoC
        self.soc_prev = self.soc_now
        self.soc_now, self.bat_state = self.get_soc()

        # calculate speed of change
        self.soc_speeds.append((self.soc_now - self.soc_prev) / (cs.POLL_SOC / 60))
        self.soc_speed = sum(self.soc_speeds) / len(self.soc_speeds) if self.soc_speeds else 0.0
        # Keep only a few speeds to avoid too much influence on prediction
        if len(self.soc_speeds) > 3:
            self.soc_speeds.pop(0)
        self.log(f"__Speed of change = {self.soc_speed:.2f} %/h")

        # Update again in half an hour
        now = dt.datetime.now()
        # get number of seconds to the next polling interval
        seconds_to_next_half_hour = (cs.POLL_SOC - now.minute % cs.POLL_SOC) * 60 - now.second
        self.run_in(self.update_soc_cb, dt.timedelta(seconds=seconds_to_next_half_hour))
