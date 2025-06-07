"""Provides constants for the Batman app."""

VERSION = "0.0.4"


# Defaults and settings for energy prices
ACT_PRICE = 25.0  # default price in cents/kWh
# Entity ID
ENT_PRICE = "sensor.bat1_energy_price"
# Attributes
CUR_PRICE_ATTR = "state"
LST_PRICE_ATTR = "attributes"

# Defaults and settings for schedules
ACT_SCHEDULE = 0  # Default schedule
# Entity ID
ENT_SCHEDULE = "sensor.bat1_power_schedule"
# Attributes
CUR_SCHEDULE_ATTR = "state"
LST_SCHEDULE_ATTR = "attributes"

# Defaults and settings for batteries
ACT_SOC = [0.0, 0.0]  # Default battery level in kWh
# Entity IDs
ENT_SOC1 = "sensor.bat1_state_of_charge"
ENT_SOC2 = "sensor.bat2_state_of_charge"
# Attributes
CUR_SOC_ATTR = "state"
POLL_SOC = 30  # minutes: Poll every half hour

# Defaults and settings for stategy & battery power management
EXTERNAL_OVERRIDE = False
CUR_STRATEGY_IDX = 0  # Default strategy index
CUR_STRATEGY_ATTR = "state"
ENT_STRATEGY = None
ENT_BAT1_STRATEGY = "select.bat1_power_strategy"
SET_BAT1_STRATEGY = "nom"
SET_BAT1_POWER = 0
ENT_BAT2_STRATEGY = "select.bat2_power_strategy"
SET_BAT2_STRATEGY = "nom"
SET_BAT2_POWER = 0
LIMIT_BAT_CHARGE = -2200  # W
LIMIT_BAT_DISCHARGE = 1700  # W
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
ACT_STRATEGY = 0  # Default strategy index


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


# Default values for logging
LOG_LVL_INFO = "INFO"
LOG_LVL_DEBUG = "INFO"
# Default values for price and strategy change log messages
LOG_MSG_LISTENING = "\n\t*** Listening to entity: {}, attribute: {}"
# Default values for price and strategy change log messages
LOG_MSG_ENTITY = "____{}: {}"


# add opslag=0.021 + extra=2.000 + taxes=10.15 = 12.171
PRICE_HIKE = 0.021
PRICE_XTRA = 2.0
PRICE_TAXS = 10.15
PRICE_BTW = 1.21
