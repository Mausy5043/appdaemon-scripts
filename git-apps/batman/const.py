"""Provides constants for the Batman app."""

VERSION = "0.1.0"

TZ = "Europe/Amsterdam"

# maximum rates per battery
MAX_CHARGE = -2200
MAX_DISCHARGE = 1700

# set to True to enable more aggressive (dis)charging when prices are favourable
TRADING = False

# SCHEDULES settings
# schedules are used to propose the charge/discharge power of the batteries for each hour
SCHEDULES: dict = {
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
PRICES: dict = {
    "name": "price",
    "nul": 0.0,  # below this, electricity is considered for free
    "top": 35.0,  # above this, electricity is considered very expensive
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
#

# STRATEGIES settings
STRATEGIES: dict = {
    "name": "strat",
    "actual": "NOM",  # index of the current strategy
    "entity": ["select.bat1_power_strategy", "select.bat2_power_strategy"],
    "attr": {
        "current": "state",
    },
    "strategies": [],
    "manager": "the_batman",
}
#

# BATTERIES settings
BATTERIES: dict = {
    "name": "bats",
    "entity": ["sensor.bat1_state_of_charge", "sensor.bat2_state_of_charge"],
    "evneedspwr": "input_boolean.evneedspwr",
    "ctrlbyapp": "input_boolean.bat_ctrl_app",
    "attr": {
        "soc": "state",
    },
    "speed": 0.0,  # Speed of change %/h
    "baseload": 2.0,  # %/h
    "soc": {
        "now": 0.0,
        "prev": 0.0,  # Previous state of charge
        "speed": 0.0,  # Speed of change %/h
        "speeds": [],  # List of speeds of change %/h
        "states": [],  # List of current SoCs
        "ll_limit": 0.1,
        "l_limit": 5.0,  # vote charge when SoC is below this limit
        "h_limit": 95.0,  # vote discharge when SoC is above this limit
        "hh_limit": 99.9,  #
    },
    "manager": "the_batman",
}

POLL_SOC = 30  # minutes: Poll every half hour

# Defaults and settings for stategy & battery power management
EXTERNAL_OVERRIDE = False
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
# STRATEGIES = ["nom", "eco", "roi", "idle", "api"]

# solar optimal position
# morning elevation > 28deg
#         azimuth > 88deg
# evening elevation < 21deg
#         azimuth < 281deg

# Default values for logging
LOG_LVL_INFO = "INFO"
LOG_LVL_DEBUG = "DEBUG"
# Default values for price and strategy change log messages
LOG_MSG_LISTENING = "\n\t*** Listening to entity: {}, attribute: {}"
# Default values for price and strategy change log messages
LOG_MSG_ENTITY = "____{}: {}"

TALLY = {
    "NOM": 0,  # Keep P1 CT at 0 (no import from or export to grid)
    "API+": 0,  # discharge (*to* the home/grid) votes
    "API-": 0,  # charge (*from* the grid) votes
    "IDLE": 0,  # hold votes (e.g.: EV charging)
}
