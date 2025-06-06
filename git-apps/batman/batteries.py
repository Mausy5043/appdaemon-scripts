import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs

"""Handle energy batteries for Batman app."""


class Batteries(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        # Keep track of active callbacks
        self.callback_handles: list[Any] = []
        # Define the internal state variables
        self.soc_speed: float = 0.0  # Speed of change in SoC
        self.soc_prev: float = 0.0  # Previous SoC
        self.soc_now: float = 0.0  # Current SoC
        self.bat_state: list[float] = []
        self.soc_speeds: list[float] = []  # List of SoC speeds
        # Initialize current soc
        # and today's and tomorrow's soclist
        self.bat_list: list[str] = [cs.ENT_SOC1, cs.ENT_SOC2]
        self.log(f"===================================== Batteries v{cs.VERSION} ====")
        # when debugging & first run:
        # log everything
        _e: dict[str, Any] = self.get_state(entity_id=cs.ENT_SOC1, attribute="all")
        for _k, _v in _e.items():
            self.log(f"_1____{_k}: {_v}", level="INFO")
        _e = self.get_state(entity_id=cs.ENT_SOC2, attribute="all")
        for _k, _v in _e.items():
            self.log(f"_2___{_k}: {_v}", level="INFO")
        # Set previous SoC and current SoC to actual values
        self.soc_prev, self.bat_state = self.get_soc()
        self.soc_now = self.soc_prev
        now = dt.datetime.now()
        # get number of seconds to the next polling interval
        seconds_to_next_half_hour: int = (cs.POLL_SOC - now.minute % cs.POLL_SOC) * 60 - now.second
        self.log(f"Next update in {seconds_to_next_half_hour} seconds")
        # Update in half an hour
        self.run_in(self.update_soc_cb, dt.timedelta(seconds=seconds_to_next_half_hour))

    def terminate(self):
        """Clean up app."""
        self.log("Terminating Batteries...")
        # some cleanup code goes here
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("...terminated Batteries.")

    def get_soc(self) -> tuple[float, list[float]]:
        """Get current state of charge (SoC) for all batteries."""
        soc_list: list[float] = []
        for bat in self.bat_list:
            _soc: Any | None = self.get_state(entity_id=bat, attribute=cs.CUR_SOC_ATTR)
            if _soc is not None:
                soc_list.append(float(_soc))
            else:
                soc_list.append(0.0)
        soc_now: float = sum(soc_list) / len(soc_list) if soc_list else 0.0
        self.log(f"Total SoC    : {soc_now} % <- {soc_list} %")
        return soc_now, soc_list

    def update_soc_cb(self, **kwargs) -> None:
        """Callback to update state of charge."""
        # remember previous SoC and calculate new SoC
        self.soc_prev = self.soc_now
        self.soc_now, self.bat_state = self.get_soc()
        self.soc_speeds.append((self.soc_now - self.soc_prev) / (cs.POLL_SOC / 60))
        self.soc_speed = sum(self.soc_speeds) / len(self.soc_speeds) if self.soc_speeds else 0.0
        # Keep only the last 6 speeds
        if len(self.soc_speeds) > 6:
            self.soc_speeds.pop(0)
        self.log(f"Speed of change: {self.soc_speed:.2f} %/h")
        # Update in half an hour
        now = dt.datetime.now()
        # get number of seconds to the next polling interval
        seconds_to_next_half_hour = (cs.POLL_SOC - now.minute % cs.POLL_SOC) * 60 - now.second
        self.log(f"Next update in {seconds_to_next_half_hour} seconds")
        self.run_in(self.update_soc_cb, dt.timedelta(seconds=seconds_to_next_half_hour))
