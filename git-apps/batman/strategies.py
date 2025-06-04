import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs

"""Handle battery charge/discharge strategies for Batman app."""


class Strategies(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        # Define the entities and attributes to listen to
        self.entity_strategies: str = cs.ENT_STRATEGY
        self.attr_state: str = cs.CUR_STRATEGY_ATTR
        self.attr_strategies: str = cs.LST_STRATEGY_ATTR
        # when debugging & first run: log everything
        _e: dict[str, Any] = self.get_state(entity_id=self.entity_strategies, attribute="all")
        for _k, _v in _e.items():
            self.log(f"____{_k}: {_v}", level="INFO")
        # Initialize today's and tomorrow's strategies
        self.strategies_changed("strategies", "", "none", "new", None)
        self.strategy_changed(
            "strategy",
            self.attr_state,
            "none",
            self.get_state(entity_id=self.entity_strategies, attribute=self.attr_state),
            None,
        )

    def strategy_changed(self, entity, attribute, old, new, kwargs):
        """Log change of current strategy."""
        try:
            old = f"{int(old)}"
            new = f"{int(new)}"
        except (ValueError, TypeError):
            pass
        self.log(f"State changed for {entity} ({attribute}): {old} -> {new}")
        self.now_strategy = int(new)
        self.log(f"New strategy = {self.now_strategy}")

    def strategies_changed(self, entity, attribute, old, new, kwargs):
        """Handle changes in the energy strategies."""
        self.log(f"strategies changed: {old} -> {new}")
        # Update today's and tomorrow's strategies
        today = dt.date.today()
        tomorrow = today + dt.timedelta(days=1)
        self.todays_strategies = self.get_strategies(today)
        self.log(f"Today's strategies:\n{self.todays_strategies}")
        self.tomorrows_strategies = self.get_strategies(tomorrow)
        self.log(f"Tomorrow's strategies:\n{self.tomorrows_strategies}\n .")

    def get_strategies(self, date) -> list[int]:
        """Get the energy strategies for a specific date."""
        no_strategies: list[float] = [0] * 24
        _s: list[int] = no_strategies
        if isinstance(date, dt.date):
            date_str: str = date.strftime("%Y-%m-%d")
            attr: dict = self.get_state(entity_id=self.entity_strategies, attribute=self.attr_strategies)
            _s = attr.get(date_str, no_strategies)
        else:
            self.log(f"Invalid date: {date}", level="ERROR")
        return _s
