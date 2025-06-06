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
        # Define the entities and attributes to listen to
        #
        # Initialize current soc and today's and tomorrow's soclist
        self.bat_list: list[str] = [cs.ENT_SOC1, cs.ENT_SOC2]
        self.log(f"===================================== Batteries v{cs.VERSION} ====")
        # when debugging & first run: log everything
        _e: dict[str, Any] = self.get_state(entity_id=cs.ENT_SOC1, attribute="all")
        for _k, _v in _e.items():
            self.log(f"1____{_k}: {_v}", level="INFO")
        _e: dict[str, Any] = self.get_state(entity_id=cs.ENT_SOC2, attribute="all")
        for _k, _v in _e.items():
            self.log(f"2____{_k}: {_v}", level="INFO")
        # Set previous SoC and current SoC to actual values
        self.soc_prev, self.bat_state = self.get_soc()
        self.soc_now: float = self.soc_prev.copy()
        # self.batteries_changed("batteries", "", "none", "new")
        _s1 = self.get_state(entity_id=cs.ENT_SOC1, attribute=cs.CUR_SOC_ATTR)
        # Update in half an hour
        self.run_in(self.get_soc, dt.timedelta(seconds=cs.POLL_SOC))

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
        self.log(f"Current SoCs : {soc_list} %")
        soc_now: float = sum(soc_list) / len(soc_list) if soc_list else 0.0
        self.log(f"Total SoC    : {self.soc_now} %")
        return soc_now, soc_list

    def get_soc_cb(self, entity: str, attribute: str, old: Any, new: Any, kwargs: dict[str, Any] | None = None):
        """Callback for state of charge changes."""
        self.log(f"get_soc_cb called with entity={entity}, attribute={attribute}, old={old}, new={new}")
        self.soc_now, self.bat_state = self.get_soc()
        # Update in half an hour
        self.run_in(self.get_soc, dt.timedelta(seconds=cs.POLL_SOC))
