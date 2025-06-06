"""Provides constants for the Batman app."""

VERSION = "0.0.4"
# Entity IDs for energy prices and strategies
ENT_PRICE = "sensor.bat1_energy_price"
ENT_STRATEGY = "sensor.bat1_power_schedule"
ENT_SOC1 = "sensor.bat1_state_of_charge"
ENT_SOC2 = "sensor.bat2_state_of_charge"
# Attributes for the entities
CUR_PRICE_ATTR = "state"
CUR_STRATEGY_ATTR = "state"
LST_PRICE_ATTR = "attributes"
LST_STRATEGY_ATTR = "attributes"

# Default values for energy prices and strategies
ACT_PRICE = 25.0  # Default price in cents
ACT_STRATEGY = 0  # Default strategy index
ACT_SOC = 0.0  # Default battery level in kWh

# ONLY these strategies may be selected by the app:
# nom : null-on-meter
#       default for summer days
# eco : charge when prices are low, otherwise act as `nom`
#       default for winter days
# roi : charge when prices are low, discharge when prices are high, otherwise act as `idle`
#       default for vacation days
# idle: do nothing
# api : power set-point is controlled externally (by HASS or other(!) app)
#       used to transition bumplessly
STRATEGIES = ["nom", "eco", "roi", "idle", "api"]
EXTERNAL_OVERRIDE = False

ENT_BAT1_STRATEGY = "select.bat1_power_strategy"
SET_BAT1_STRATEGY = "nom"
SET_BAT1_POWER = 0
ENT_BAT2_STRATEGY = "select.bat2_power_strategy"
SET_BAT2_STRATEGY = "nom"
SET_BAT2_POWER = 0

# Default values for price and strategy change events
PRICE_CHANGE_EVENT = "price_change"
STRATEGY_CHANGE_EVENT = "strategy_change"
# Default values for price and strategy change attributes
PRICE_CHANGE_ATTR = "price"
STRATEGY_CHANGE_ATTR = "strategy"
# Default values for price and strategy change states
PRICE_CHANGE_STATE = "none"
STRATEGY_CHANGE_STATE = "none"
# Default values for price and strategy change new values
PRICE_CHANGE_NEW = None
STRATEGY_CHANGE_NEW = None
# Default values for price and strategy change old values
PRICE_CHANGE_OLD = None
STRATEGY_CHANGE_OLD = None
# Default values for price and strategy change kwargs
PRICE_CHANGE_KWARGS = None
STRATEGY_CHANGE_KWARGS = None
# Default values for price and strategy change log level
LOG_LEVEL_DEBUG = "DEBUG"
# Default values for price and strategy change log messages
LOG_MSG_LISTENING = "\n\t*** Listening to entity: {}, attribute: {}"
# Default values for price and strategy change log messages
LOG_MSG_ENTITY = "____{}: {}"


# add opslag=0.021 + extra=2.000 + taxes=10.15 = 12.171
PRICE_HIKE = 0.021
PRICE_XTRA = 2.0
PRICE_TAXS = 10.15
PRICE_BTW = 1.21
