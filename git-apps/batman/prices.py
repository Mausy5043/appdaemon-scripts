import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs

"""Handle energy prices for Batman app."""


class Prices(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        # Define the entities and attributes to listen to
        self.entity_prices: str = cs.ENT_PRICE
        self.attr_state: str = cs.CUR_PRICE_ATTR
        self.attr_prices: str = cs.LST_PRICE_ATTR
        # when debugging & first run: log everything
        _e: dict[str, Any] = self.get_state(entity_id=self.entity_prices, attribute="all")
        for _k, _v in _e.items():
            self.log(f"____{_k}: {_v}", level="INFO")
        # Initialize today's and tomorrow's prices
        self.prices_changed("prices", "", "none", "new", None)
        _p = self.get_state(entity_id=self.entity_prices, attribute=self.attr_state)
        self.price_changed("price", self.attr_state, "none", _p, None)

    def price_changed(self, entity, attribute, old, new, kwargs):
        """Log change of current price."""
        try:
            old = f"{float(old):.5f}"
            new = f"{float(new):.5f}"
        except (ValueError, TypeError):
            pass
        self.log(f"State changed for {entity} ({attribute}): {old} -> {new}")
        _p: list[float] = [float(new)]
        self.now_price = self.total_price(_p)[0]
        self.log(f"New price = {self.now_price}")

    def prices_changed(self, entity, attribute, old, new, kwargs):
        """Handle changes in the energy prices."""
        self.log(f"Prices changed: {old} -> {new}")
        # Update today's and tomorrow's prices
        today = dt.date.today()
        tomorrow = today + dt.timedelta(days=1)
        self.todays_prices = self.get_prices(today)
        self.log(f"Today's prices:\n{self.todays_prices}")
        self.tomorrows_prices = self.get_prices(tomorrow)
        self.log(f"Tomorrow's prices:\n{self.tomorrows_prices}\n .")

    def get_prices(self, date) -> list[float]:
        """Get the energy prices for a specific date."""
        no_prices: list[float] = [0.0] * 24
        _p: list[float] = no_prices
        if isinstance(date, dt.date):
            date_str: str = date.strftime("%Y-%m-%d")
            attr: dict = self.get_state(entity_id=self.entity_prices, attribute=self.attr_prices)
            _p = attr.get(date_str, no_prices)
        else:
            self.log(f"Invalid date: {date}", level="ERROR")
        return self.total_price(pricelist=_p)

    def total_price(self, pricelist: list[float]) -> list[float]:
        """Convert a given list of raw prices."""
        # cents to Euro
        _p: list[float] = [i * 100 for i in pricelist]
        # add costs and taxes
        _p = [i + (cs.PRICE_HIKE + cs.PRICE_XTRA + cs.PRICE_TAXS) for i in _p]
        # add BTW
        _p = [round(i * cs.PRICE_BTW, 5) for i in _p]
        return _p
