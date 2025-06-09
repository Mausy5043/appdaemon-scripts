from typing import Any

"""Provides constants for the Batman app."""

VERSION = "0.0.5"

# SCHEDULES settings
# schedules are used to propose the charge/discharge power of the batteries for each hour
SCHEDULES: dict[str, Any] = {
    "name": "schds",
    "actual": 0,  # W
    "entity": "sensor.bat1_power_schedule",
    "attr": {
        "actual": "state",
        "list": "attributes",
    },
    "today": [],
    "tomor": [],
    "manager": "the_batman",
}
#

# PRICES settings
# prices are used to determine the best time to charge/discharge the batteries
PRICES: dict[str, Any] = {
    "name": "price",
    "actual": 25.0,  # cents/kWh
    "entity": "sensor.bat1_energy_price",
    "attr": {
        "current": "state",
        "list": "attributes",
    },
    "today": {
        "data": [],
        "min": 14.0,
        "q1": 20.0,
        "med": 25.0,
        "avg": 27.5,
        "q3": 30.0,
        "max": 35.0,
    },
    "tomor": {
        "data": [],
        "min": 14.0,
        "q1": 20.0,
        "med": 25.0,
        "avg": 27.5,
        "q3": 30.0,
        "max": 35.0,
    },
    "adjust": {"hike": 0.021, "extra": 2.0, "taxes": 10.15, "btw": 1.21},
    "manager": "the_batman",
}
# Defaults and settings for energy prices
# ACT_PRICE = 25.0  # default price in cents/kWh
# # Entity ID
# ENT_PRICE = "sensor.bat1_energy_price"
# # Attributes
# CUR_PRICE_ATTR = "state"
# LST_PRICE_ATTR = "attributes"

# STRATEGIES settings
STRATEGIES: dict[str, Any] = {
    "name": "strat",
    "actual": 0,  # index of the current strategy
    "entity": "select.bat1_power_strategy",
    "attr": {
        "current": "state",
        "list": "options",
    },
    "manager": "the_batman",
}

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
