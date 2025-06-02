import appdaemon.plugins.hass.hassapi as hass  # pyright: ignore[reportMissingImports]
import batteries
import const as cs
import prices
import strategies
import utils as ut

"""BatMan App
Listen to changes in the battery state and control the charging/discharging based on energy prices and strategies.
"""


class BatMan(hass.Hass):
    def initialize(self):
        """Initialize the app."""
        # initialize the prices and strategies
        self.todays_prices = []
        self.tomorrows_prices = []
        self.todays_strategy = []
        self.tomorrows_strategy = []
        self.now_price = cs.ACT_PRICE
        self.now_strategy = cs.ACT_STRATEGY

        # Log the version and entity attributes
        self.log(f"=== BatMan v{cs.VERSION} ===")
        ut.log_entity_attr(self, cs.ENT_PRICE, level="DEBUG")
        ut.log_entity_attr(self, cs.ENT_STRATEGY, level="DEBUG")

        # Initialize today's and tomorrow's prices and strategies
        prices.lst_changed(
            self,
            entity=cs.ENT_PRICE,
            attribute=cs.CUR_PRICE_ATTR,
            old=self.todays_prices,
            new="new",
            kwargs=None,
        )
        self.log(f"\n*** Today's prices:\n{self.todays_prices}\n.")
        self.log(f"\n*** Tomorrow's prices:\n{self.tomorrows_prices}\n .")

        strategies.lst_changed(
            self,
            entity=cs.ENT_STRATEGY,
            attribute=cs.CUR_STRATEGY_ATTR,
            old="none",
            new="new",
            kwargs=None,
        )
        self.log(f"Today's strategy:\n{self.todays_strategy}")
        self.log(f"Charging   : {ut.sort_index(self.todays_strategy)[-3:]}")
        self.log(f"Discharging: {ut.sort_index(self.todays_strategy)[:3]}")
        self.log(f"Tomorrow's strategy:\n{self.tomorrows_strategy}\n .")
        self.log(f"Charging   : {ut.sort_index(self.tomorrows_strategy)[-3:]}")
        self.log(f"Discharging: {ut.sort_index(self.tomorrows_strategy)[:3]}")

        # Set-up callbacks for price and strategy changes
        self.listen_state(self.price_current_cb, cs.ENT_PRICE, attribute=cs.CUR_PRICE_ATTR)
        # self.listen_state(prices.price_current_cb, cs.ENT_PRICE, attribute=cs.CUR_PRICE_ATTR)
        self.listen_state(self.price_list_cb, cs.ENT_PRICE, attribute=cs.LST_PRICE_ATTR)
        # self.listen_state(prices.price_list_cb, cs.ENT_PRICE, attribute=cs.LST_PRICE_ATTR)
        self.listen_state(self.strategy_current_cb, cs.ENT_STRATEGY, attribute=cs.CUR_STRATEGY_ATTR)
        self.listen_state(self.strategy_list_cb, cs.ENT_STRATEGY, attribute=cs.LST_STRATEGY_ATTR)
        batteries.ramp(self, "ramping...")

    def terminate(self):
        """Clean up app."""
        self.log("Terminating BatMan...")
        # some cleanup code goes here
        # - set batteries to NOM strategy
        self.log("...terminated BatMan.")

    def price_current_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for current price change."""
        prices.now_change(self, entity, attribute, old, new, kwargs)

    def price_list_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for price list change."""
        prices.lst_changed(self, entity, attribute, old, new, kwargs)

    def strategy_current_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for current strategy change."""
        strategies.now_change(self, entity, attribute, old, new, kwargs)

    def strategy_list_cb(self, entity, attribute, old, new, **kwargs):
        """Callback for strategy list change."""
        strategies.lst_changed(self, entity, attribute, old, new, kwargs)
