from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs

"""Handle battery charge/discharge strategies for Batman app."""


class Strategies(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        self.log(f"================================= Strategies v{cs.VERSION} ====")
        # Keep track of active callbacks
        self.callback_handles: list[Any] = []

        self.strat = cs.STRATEGIES
        self.mgr = self.get_app(self.strat["manager"])
        if not self.mgr:
            self.log(f"__ERROR: {self.strat['manager']} app not found!", level="ERROR")
            return

        # when debugging & first run:
        # log everything
        for bat in self.strat["entity"]:
            _e: dict[str, Any] = self.get_state(entity_id=bat, attribute="all")
            for _k, _v in _e.items():
                self.log(f"_{bat}___{_k}: {_v}", level="DEBUG")

        self.strat["strategies"] = self.get_strategy_list()

        # activate callbacks
        for bat in self.strat["entity"]:
            self.callback_handles.append(
            self.listen_state(self.strategy_current_cb, bat, attribute=self.strat["attr"]["current"])
        )

    def terminate(self):
        """Clean up app."""
        self.log("_Terminating Strategies...")
        # some cleanup code goes here
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("_...terminated Strategies.")

    def strategy_changed(self, entity, attribute, old, new, **kwargs):
        """Log change of current strategy."""
        # update strategy for both batteries when one of them changes
        self.strat["strategies"] = self.get_strategy_list()

        # voting logic will be called here
        # ...
        # ...
        self.mgr.vote(self.strat["name"], self.strat["strategies"])

    def get_strategy_list(self) -> list[str]:
        """Get current strategy for all batteries."""
        strat_list = []
        for bat in self.strat["entity"]:
            _s: Any | None = self.get_state(entity_id=bat, attribute=self.strat["attr"]["current"])
            if _s is not None:
                strat_list.append(_s.upper())
            else:
                # If status is unknown we report IDLE
                strat_list.append("IDLE")
        self.mgr.tell(self.strat["name"], f"Current strategies = {strat_list}")
        return strat_list

    # CALLBACKS

    def strategy_current_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for current strategy change."""
        self.strategy_changed(entity, attribute, old, new, **kwargs)


# strategy
#  0 = nom
#  (+)  || SoC > 75% || summerday |-> = discharge to 25%
#  (-)  || SoC < 32% || winterday |-> = charge to 100%
# definition of summerday is

#  summerday = 1st of May to 30th of September
# sensors that detect summerday or winterday:
#  - sensor.batman_summerday
#  - sensor.batman_winterday
#  - sensor.batman_tommorow_summerday
#  - sensor.batman_tommorow_winterday
#  winterday = 1st of October to 30th of April
