from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs

"""BatMan App
Listen to changes in the battery state and control the charging/discharging based on energy prices and strategies.
"""


class BatMan(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        self.log(f"===================================== BatMan v{cs.VERSION} ====")
        # Keep track of active callbacks
        self.callback_handles: list[Any] = []

    def terminate(self):
        """Clean up app."""
        self.log("__Terminating BatMan...")
        # some cleanup code goes here
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("__...terminated BatMan.")

    def tell(self, message: str):
        """Log a message."""
        self.log(f"_BatMan: {message}")
