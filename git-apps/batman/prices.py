import datetime as dt
from statistics import quantiles
from typing import Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import const as cs
import utils as ut

"""Handle energy prices for Batman app."""


class Prices(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        self.log(f"===================================== Prices v{cs.VERSION} ====")
        # Keep track of active callbacks
        self.callback_handles: list[Any] = []

        self.price = cs.PRICES
        self.mgr = self.get_app(self.price["manager"])
        if not self.mgr:
            self.log(f"__ERROR: {self.price['manager']} app not found!", level="ERROR")
            return
        # when debugging & first run: log everything
        _e: dict[str, Any] = self.get_state(entity_id=self.price["entity"], attribute="all")
        for _k, _v in _e.items():
            self.log(f"____{_k}: {_v}", level="DEBUG")
        # Update today's and tomorrow's prices
        self.prices_changed("prices", "", "none", "new")
        _p = self.get_state(entity_id=self.price["entity"], attribute=self.price["attr"]["current"])
        self.price_changed("price", self.price["attr"]["current"], "none", _p)

        # Set-up callbacks for price changes
        self.callback_handles.append(
            self.listen_state(self.price_list_cb, self.price["entity"], attribute=self.price["attr"]["list"])
        )
        self.callback_handles.append(
            self.listen_state(
                self.price_current_cb, self.price["entity"], attribute=self.price["attr"]["current"]
            )
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
        _p: list[float] = [float(new)]
        self.price["actual"] = self.total_price(_p)[0]
        # self.mgr.tell(self.price["name"], f"New price = {self.price['actual']:.3f} cents/kWh")
        self.eval_price()

    def eval_price(self):
        """Evaluate the current price and inform manager."""
        _t = ""
        _v = ["NOM"]
        # Check if the current price is below the threshold
        if self.price["actual"] < self.price["today"]["q1"]:
            _t = f"Current price is below Q1 ({self.price['today']['q1']:.3f}): {self.price['actual']:.3f}"
            _v = ["API(-2200)"]  # CHARGE
        if self.price["actual"] > self.price["today"]["q3"]:
            _t = f"Current price is above Q3 ({self.price['today']['q3']:.3f}): {self.price['actual']:.3f}"
            _v = ["API(1700)"]  # DISCHARGE
        if self.price["today"]["q1"] < self.price["actual"] < self.price["today"]["q3"]:
            _t = f"Current price is between Q1 ({self.price['today']['q1']:.3f}) and Q3 ({
                self.price['today']['q3']:.3f
            }): {self.price['actual']:.3f}"
            _v = ["NOM"]

        now_hour = dt.datetime.now().hour
        if now_hour in self.price["cheap_hour"]:
            _v += ["API(1700)"]
        if now_hour in self.price["expen_hour"]:
            _v += ["API(-2200)"]

        if _t:
            self.mgr.tell(self.price["name"], _t)
        self.mgr.vote(self.price["name"], _v)

    def prices_changed(self, entity, attribute, old, new, **kwargs):
        """Handle changes in the energy prices."""
        # Update today's and tomorrow's prices
        today = dt.date.today()
        tomorrow = today + dt.timedelta(days=1)
        # update list of prices for today
        _p = self.get_prices(today)
        self.price["today"]["list"] = _p
        self.price["today"]["min"] = min(_p)
        self.price["today"]["q1"] = quantiles(_p, n=4, method="inclusive")[0]
        self.price["today"]["med"] = quantiles(_p, n=4, method="inclusive")[1]
        self.price["today"]["avg"] = sum(_p) / len(_p)
        self.price["today"]["q3"] = quantiles(_p, n=4, method="inclusive")[2]
        self.price["today"]["max"] = max(_p)

        charge_today = ut.sort_index(_p, rev=True)[-3:]
        charge_today.sort()
        discharge_today = ut.sort_index(_p, rev=True)[:3]
        discharge_today.sort()

        self.price["cheap_hour"] = charge_today
        self.price["expen_hour"] = discharge_today

        _s = self.format_price_statistics(self.price["today"])
        self.mgr.tell(
            self.price["name"], f"Today's prices    :\n{_p}\n {_s} : {charge_today} {discharge_today}."
        )

        # update list of prices for tomorrow
        _p = self.get_prices(tomorrow)
        self.price["tomor"]["list"] = _p
        self.price["tomor"]["min"] = min(_p)
        self.price["tomor"]["q1"] = quantiles(_p, n=4, method="inclusive")[0]
        self.price["tomor"]["med"] = quantiles(_p, n=4, method="inclusive")[1]
        self.price["tomor"]["avg"] = sum(_p) / len(_p)
        self.price["tomor"]["q3"] = quantiles(_p, n=4, method="inclusive")[2]
        self.price["tomor"]["max"] = max(_p)

        if min(_p) < max(_p):
            # only communicate prices for tomorrow if they are known (minimum is not maximum)
            charge_tomor = ut.sort_index(_p, rev=True)[-3:]
            charge_tomor.sort()
            discharge_tomor = ut.sort_index(_p, rev=True)[:3]
            discharge_tomor.sort()

            _s = self.format_price_statistics(self.price["tomor"])
            self.mgr.tell(
                self.price["name"], f"Tomorrow's prices :\n{_p}\n {_s} : {charge_tomor} {discharge_tomor}."
            )

    @staticmethod
    def format_price_statistics(price: dict) -> str:
        """Return a string with price statistics."""
        return (
            f"Min: {price.get('min', 'N/A'):.3f}, "
            f"Q1: {price.get('q1', 'N/A'):.3f}, "
            f"Med: {price.get('med', 'N/A'):.3f}, "
            f"Avg: {price.get('avg', 'N/A'):.3f}, "
            f"Q3: {price.get('q3', 'N/A'):.3f}, "
            f"Max: {price.get('max', 'N/A'):.3f}"
        )

    def get_prices(self, date) -> list[float]:
        """Get the energy prices for a specific date."""
        no_prices: list[float] = [0.0] * 24
        _p: list[float] = no_prices
        if isinstance(date, dt.date):
            date_str: str = date.strftime("%Y-%m-%d")
            attr: dict = self.get_state(entity_id=self.price["entity"], attribute=self.price["attr"]["list"])
            _p = attr.get(date_str, no_prices)
        else:
            self.log(f"Invalid date: {date}", level="ERROR")
        return self.total_price(pricelist=_p)

    def total_price(self, pricelist: list[float]) -> list[float]:
        """Convert a given list of raw prices."""
        # cents to Euro
        _p: list[float] = [i * 100 for i in pricelist]
        # add costs and taxes
        _p = [
            i + (self.price["adjust"]["hike"] + self.price["adjust"]["extra"] + self.price["adjust"]["taxes"])
            for i in _p
        ]
        # add BTW
        _p = [round(i * self.price["adjust"]["btw"], 5) for i in _p]
        return _p

    # CALLBACKS

    def price_current_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for current price change."""
        self.price_changed(entity, attribute, old, new, **kwargs)

    def price_list_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for price list change."""
        self.prices_changed(entity, attribute, old, new, **kwargs)


"""
Voting:

MAX
    <- DISCHARGE [api, discharge_max] to x% SoC; x = aantal uren tot 09:00 volgende ochtend * 2.0%
Q3
    <- NOM
: ongunstig om te importeren
min(MED,AVG)
: ongunstig om te exporteren
    <- NOM
Q1
    <- CHARGE [api, charge_max] to 100% SoC
MIN


"""
