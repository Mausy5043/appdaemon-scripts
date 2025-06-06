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
        self.now_soc1: float = cs.ENT_SOC1
        self.now_soc2: float = cs.ENT_SOC2
        self.log(f"===================================== Batteries v{cs.VERSION} ====")
        # when debugging & first run: log everything
        _e: dict[str, Any] = self.get_state(entity_id=cs.ENT_SOC1, attribute="all")
        for _k, _v in _e.items():
            self.log(f"1____{_k}: {_v}", level="INFO")
        _e: dict[str, Any] = self.get_state(entity_id=cs.ENT_SOC2, attribute="all")
        for _k, _v in _e.items():
            self.log(f"2____{_k}: {_v}", level="INFO")
        # Update today's and tomorrow's batteries
        # self.batteries_changed("batteries", "", "none", "new")
        # _p = self.get_state(entity_id=cs.ENT_SOC1, attribute=cs.CUR_SOC_ATTR)
        # self.soc_changed("soc", cs.CUR_PRICE_ATTR, "none", _p)
        # # Set-up callbacks for soc changes
        # self.callback_handles.append(
        #     self.listen_state(self.soc_list_cb, cs.ENT_PRICE, attribute=cs.LST_PRICE_ATTR)
        # )
        # self.callback_handles.append(
        #     self.listen_state(self.soc_current_cb, cs.ENT_PRICE, attribute=cs.CUR_PRICE_ATTR)
        #)

    def terminate(self):
        """Clean up app."""
        self.log("Terminating Batteries...")
        # some cleanup code goes here
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("...terminated Batteries.")
