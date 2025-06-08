import datetime as dt
from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs

from statistics import quantiles

"""Handle energy prices for Batman app."""


class Prices(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        # Keep track of active callbacks
        self.callback_handles: list[Any] = []
        # Define the entities and attributes to listen to
        #
        # Initialize current price and today's and tomorrow's pricelist
        self.now_price: float = cs.ACT_PRICE
        self.todays_prices: list[float] = []
        self.tomorrows_prices: list[float] = []
        self.log(f"===================================== Prices v{cs.VERSION} ====")
        # when debugging & first run: log everything
        _e: dict[str, Any] = self.get_state(entity_id=cs.ENT_PRICE, attribute="all")
        for _k, _v in _e.items():
            self.log(f"____{_k}: {_v}", level="INFO")
        # Update today's and tomorrow's prices
        self.prices_changed("prices", "", "none", "new")
        _p = self.get_state(entity_id=cs.ENT_PRICE, attribute=cs.CUR_PRICE_ATTR)
        self.price_changed("price", cs.CUR_PRICE_ATTR, "none", _p)
        # Set-up callbacks for price changes
        self.callback_handles.append(
            self.listen_state(self.price_list_cb, cs.ENT_PRICE, attribute=cs.LST_PRICE_ATTR)
        )
        self.callback_handles.append(
            self.listen_state(self.price_current_cb, cs.ENT_PRICE, attribute=cs.CUR_PRICE_ATTR)
        )

    def terminate(self):
        """Clean up app."""
        self.log("_____Terminating Prices...")
        # some cleanup code goes here
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("_____...terminated Prices.")

    def price_changed(self, entity, attribute, old, new, **kwargs):
        """Log change of current price."""
        try:
            old = f"{float(old):.5f}"
            new = f"{float(new):.5f}"
        except (ValueError, TypeError):
            pass
        # self.log(f"State changed for {entity} ({attribute}): {old} -> {new}")
        _p: list[float] = [float(new)]
        self.now_price = self.total_price(_p)[0]
        self.log(f"_____New price = {self.now_price}")

    def prices_changed(self, entity, attribute, old, new, **kwargs):
        """Handle changes in the energy prices."""
        # self.log(f"Prices changed: {old} -> {new}")
        # Update today's and tomorrow's prices
        today = dt.date.today()
        tomorrow = today + dt.timedelta(days=1)
        # update list of prices for today
        self.todays_prices = self.get_prices(today)
        _q = [round(q, 3) for q in quantiles(self.todays_prices, n=4, method="inclusive")]
        self.todays_mean = sum(self.todays_prices) / len(self.todays_prices) if self.todays_prices else 0.0
        self.todays_diff: list = [
            round(x - y,3) for x, y in zip(self.todays_prices, [self.todays_mean] * len(self.todays_prices), strict=True)
        ]
        self.log(f"_____Today's prices    :\n{self.todays_prices}\n {self.todays_mean:.3f}\n.")
        self.log(f"_____Diff              :\n{self.todays_diff}")
        self.log(f"_____Max diff          : {max(self.todays_diff):.3f}")
        self.log(f"_____Min diff          : {min(self.todays_diff):.3f}")
        self.log(f"_____Quartiles         : {', '.join(map(str, _q))}")
        # update list of prices for tomorrow
        self.tomorrows_prices = self.get_prices(tomorrow)
        _q = [round(q, 3) for q in quantiles(self.tomorrows_prices, n=4, method="inclusive")]
        self.tomorrows_mean = (
            sum(self.tomorrows_prices) / len(self.tomorrows_prices) if self.tomorrows_prices else 0.0
        )
        self.tomorrows_diff: list = [
            round(x - y,3) for x, y in zip(self.tomorrows_prices, [self.tomorrows_mean] * len(self.tomorrows_prices), strict=True)
        ]
        self.log(f"_____Tomorrow's prices :\n{self.tomorrows_prices}\n {self.tomorrows_mean:.3f}\n .")

        self.log(f"_____Diff              :\n{self.tomorrows_diff}")
        self.log(f"_____Max diff          : {max(self.tomorrows_diff):.3f}")
        self.log(f"_____Min diff          : {min(self.tomorrows_diff):.3f}")
        self.log(f"_____Quartiles         : {', '.join(map(str, _q))}")

    def get_prices(self, date) -> list[float]:
        """Get the energy prices for a specific date."""
        no_prices: list[float] = [0.0] * 24
        _p: list[float] = no_prices
        if isinstance(date, dt.date):
            date_str: str = date.strftime("%Y-%m-%d")
            attr: dict = self.get_state(entity_id=cs.ENT_PRICE, attribute=cs.LST_PRICE_ATTR)
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

    # CALLBACKS

    def price_current_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for current price change."""
        self.price_changed(entity, attribute, old, new, **kwargs)

    def price_list_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for price list change."""
        self.prices_changed(entity, attribute, old, new, **kwargs)
