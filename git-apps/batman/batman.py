import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import batteries
import const as cs
import utils as ut

"""BatMan App
Listen to changes in the battery state and control the charging/discharging based on energy prices and strategies.
"""


class BatMan(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        """Initialize the app."""
        # initialize the prices and strategies
        self.todays_prices: list[float] = []
        self.tomorrows_prices: list[float] = []
        self.todays_strategy: list[int] = []
        self.tomorrows_strategy: list[int] = []
        self.now_price: float = cs.ACT_PRICE
        self.now_strategy: int = cs.ACT_STRATEGY

        # Log the version and entity attributes
        self.log(f"=== BatMan v{cs.VERSION} ===")
        ut.log_entity_attr(self, cs.ENT_PRICE, level="DEBUG")
        ut.log_entity_attr(self, cs.ENT_STRATEGY, level="DEBUG")

        self.log(f"\n*** Today's prices:\n{self.todays_prices}\n.")
        self.log(f"\n*** Tomorrow's prices:\n{self.tomorrows_prices}\n .")

        self.log(f"Today's strategy:\n{self.todays_strategy}")
        self.log(f"Charging   : {ut.sort_index(self.todays_strategy)[-3:]}")
        self.log(f"Discharging: {ut.sort_index(self.todays_strategy)[:3]}")
        self.log(f"Tomorrow's strategy:\n{self.tomorrows_strategy}\n .")
        self.log(f"Charging   : {ut.sort_index(self.tomorrows_strategy)[-3:]}")
        self.log(f"Discharging: {ut.sort_index(self.tomorrows_strategy)[:3]}")

        # self.listen_state(prices.price_list_cb, cs.ENT_PRICE, attribute=cs.LST_PRICE_ATTR)
        # batteries.ramp(self, "ramping...")

    def terminate(self):
        """Clean up app."""
        self.log("Terminating BatMan...")
        # some cleanup code goes here
        # - set batteries to NOM strategy
        self.log("...terminated BatMan.")
