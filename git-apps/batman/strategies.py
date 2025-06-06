import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs
import utils as ut

"""Handle battery charge/discharge strategies for Batman app."""


class Strategies(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        # Keep track of active callbacks
        self.callback_handles: list[Any] = []
        # Define the entities and attributes to listen to
        #
        # Initialize current strategy and today's and tomorrow's list of strategies
        self.now_strategy: int = cs.ACT_STRATEGY
        self.todays_strategies: list[int] = []
        self.tomorrows_strategies: list[int] = []
        self.log(f"================================= Strategies v{cs.VERSION} ====")
        # when debugging & first run: log everything
        _e: dict[str, Any] = self.get_state(entity_id=cs.ENT_STRATEGY, attribute="all")
        for _k, _v in _e.items():
            self.log(f"____{_k}: {_v}", level="INFO")
        # Initialize today's and tomorrow's strategies
        self.strategies_changed("strategies", "", "none", "new")
        _s = self.get_state(entity_id=cs.ENT_STRATEGY, attribute=cs.CUR_STRATEGY_ATTR)
        self.strategy_changed("strategy", cs.CUR_STRATEGY_ATTR, "none", _s)

        self.callback_handles.append(
            self.listen_state(self.strategy_current_cb, cs.ENT_STRATEGY, attribute=cs.CUR_STRATEGY_ATTR)
        )
        self.callback_handles.append(
            self.listen_state(self.strategy_list_cb, cs.ENT_STRATEGY, attribute=cs.LST_STRATEGY_ATTR)
        )

    def terminate(self):
        """Clean up app."""
        self.log("Terminating Strategies...")
        # some cleanup code goes here
        # -
        self.log("...terminated Strategies.")

    def strategy_changed(self, entity, attribute, old, new, **kwargs):
        """Log change of current strategy."""
        try:
            old = f"{int(old)}"
            new = f"{int(new)}"
        except (ValueError, TypeError):
            pass
        self.log(f"State changed for {entity} ({attribute}): {old} -> {new}")
        self.now_strategy = int(new)
        self.log(f"New strategy = {self.now_strategy}")

    def strategies_changed(self, entity, attribute, old, new, **kwargs):
        """Handle changes in the energy strategies."""
        self.log(f"Strategies changed: {old} -> {new}")
        # Update today's and tomorrow's strategies
        today = dt.date.today()
        tomorrow = today + dt.timedelta(days=1)
        self.todays_strategies = self.get_strategies(today)
        self.tomorrows_strategies = self.get_strategies(tomorrow)
        charge_today = ut.sort_index(self.todays_strategies)[-3:]
        discharge_today = ut.sort_index(self.todays_strategies)[:3]
        charge_tomorrow = ut.sort_index(self.tomorrows_strategies)[-3:]
        discharge_tomorrow = ut.sort_index(self.tomorrows_strategies)[:3]
        self.log(f"Today's strategies:\n{self.todays_strategies} \n : {charge_today} {discharge_today}.")
        self.log(
            f"Tomorrow's strategies:\n{self.tomorrows_strategies} \n : {charge_tomorrow} {discharge_tomorrow}."
        )

    def get_strategies(self, date) -> list[int]:
        """Get the energy strategies for a specific date."""
        no_strategies: list[int] = [0] * 24
        _s: list[int] = no_strategies
        if isinstance(date, dt.date):
            date_str: str = date.strftime("%Y-%m-%d")
            attr: dict = self.get_state(entity_id=cs.ENT_STRATEGY, attribute=cs.LST_STRATEGY_ATTR)
            _s = attr.get(date_str, no_strategies)
        else:
            self.log(f"Invalid date: {date}", level="ERROR")
        return _s

    # CALLBACKS

    def strategy_current_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for current strategy change."""
        self.strategy_changed(entity, attribute, old, new, **kwargs)

    def strategy_list_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for strategy list change."""
        self.strategies_changed(entity, attribute, old, new, **kwargs)


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
