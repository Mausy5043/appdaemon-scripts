import datetime

import appdaemon.plugins.hass.hassapi as hass  # pyright: ignore[reportMissingImports]

"""Listen App
Listen to changes in an entity's state or attribute, or to a specific event.

Args:
    entity: The entity to listen to.
    attribute: The attribute of the entity to listen to.
    event: The event to listen for.
"""


class BestPrice(hass.Hass):
    def initialize(self):
        """Initialize the app."""
        # Define the entities and attributes to listen to
        self.entity_prices: str = "sensor.bat1_energy_price"
        self.entity_strategy: str = "sensor.bat1_power_schedule"
        self.attr_state: str = "state"
        self.attr_prices: str = "attributes"
        self.attr_strategy: str = "attributes"

        self.now_price = 25.0
        self.now_strategy = 0

        # when debugging & first run: log everything
        _e: dict = self.get_state(entity_id=self.entity_prices, attribute="all")
        for _k, _v in _e.items():
            self.log(f"____{_k}: {_v}", level="DEBUG")
        # when debugging & first run: log everything
        _e = self.get_state(entity_id=self.entity_strategy, attribute="all")
        for _k, _v in _e.items():
            self.log(f"____{_k}: {_v}", level="DEBUG")
        # Initialize today's and tomorrow's prices and strategies
        self.prices_changed("prices", "", "none", "new", None)
        self.strategies_changed("strategy", "", "none", "new", None)
        # initialze current price and strategy
        self.price_change(
            "price",
            self.attr_state,
            "none",
            self.get_state(entity_id=self.entity_prices, attribute=self.attr_state),
            None,
        )
        self.strategy_change(
            "strategy",
            self.attr_state,
            "none",
            self.get_state(entity_id=self.entity_strategy, attribute=self.attr_state),
            None,
        )

        # start listening
        self.log(f"\n\t*** Listening to entity: {self.entity_prices}, attribute: {self.attr_state}")
        self.listen_state(self.price_change, self.entity_prices, attribute=self.attr_state)
        self.log(f"\n\t*** Listening to entity: {self.entity_prices}, attribute: {self.attr_prices}")
        self.listen_state(self.prices_changed, self.entity_prices, attribute=self.attr_prices)

        self.log(f"\n\t*** Listening to entity: {self.entity_strategy}, attribute: {self.attr_state}")
        self.listen_state(self.strategy_change, self.entity_strategy, attribute=self.attr_state)
        self.log(f"\n\t*** Listening to entity: {self.entity_strategy}, attribute: {self.attr_strategy}")
        self.listen_state(self.strategies_changed, self.entity_strategy, attribute=self.attr_strategy)

    def price_change(self, entity, attribute, old, new, kwargs):
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
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)
        self.todays_prices = self.get_prices(today)
        self.log(f"Today's prices:\n{self.todays_prices}")
        self.tomorrows_prices = self.get_prices(tomorrow)
        self.log(f"Tomorrow's prices:\n{self.tomorrows_prices}\n .")

    def get_prices(self, date) -> list[float]:
        """Get the energy prices for a specific date."""
        no_prices: list[float] = [0.0] * 24
        _p: list[float] = no_prices
        if isinstance(date, datetime.date):
            date_str: str = date.strftime("%Y-%m-%d")
            attr: dict = self.get_state(entity_id=self.entity_prices, attribute=self.attr_prices)
            _p = attr.get(date_str, no_prices)
        else:
            self.log(f"Invalid date: {date}", level="ERROR")
        return self.total_price(pricelist=_p)

    def total_price(self, pricelist: list[float]) -> list[float]:
        """Convert a given list of raw prices."""
        _p = [i * 100 for i in pricelist]
        # add opslag=0.021 + extra=2.000 + taxes=10.15 = 12.171
        _p = [i + (0.021 + 2.0 + 10.15) for i in _p]
        # add BTW = 21%
        _p = [round(i * 1.21, 5) for i in _p]
        return _p

    def strategy_change(self, entity, attribute, old, new, kwargs):
        """Log change of current strategy."""
        self.log(f"State changed for {entity} ({attribute}): {old} -> {new}")
        self.now_strategy = int(new)

    def strategies_changed(self, entity, attribute, old, new, kwargs):
        """Handle changes in the power strategy."""
        self.log(f"Strategies changed: {old} -> {new}")
        # Update today's and tomorrow's strategies
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)
        self.todays_strategy = self.get_strategy(today)
        self.log(f"Today's strategy:\n{self.todays_strategy}")
        self.log(f"Charging   : {sort_index(self.todays_strategy)[-3:]}")
        self.log(f"Discharging: {sort_index(self.todays_strategy)[:3]}")

        self.tomorrows_strategy = self.get_strategy(tomorrow)
        self.log(f"Tomorrow's strategy:\n{self.tomorrows_strategy}\n .")
        self.log(f"Charging   : {sort_index(self.tomorrows_strategy)[-3:]}")
        self.log(f"Discharging: {sort_index(self.tomorrows_strategy)[:3]}")

    def get_strategy(self, date) -> list[int]:
        """Get the power strategy for a specific date."""
        no_strategy: list[int] = [0] * 24
        if isinstance(date, datetime.date):
            date_str: str = date.strftime("%Y-%m-%d")
            attr: dict = self.get_state(entity_id=self.entity_strategy, attribute=self.attr_strategy)
            return attr.get(date_str, no_strategy)
        else:
            self.log(f"Invalid date: {date}", level="ERROR")
            return no_strategy


def sort_index(lst, rev=True):
    index = range(len(lst))
    s = sorted(index, reverse=rev, key=lambda i: lst[i])
    return s
