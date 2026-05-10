"""Provides constants for the Batman3 app."""

from typing import Any

# ### GENERAL SETTINGS ### #
VERSION: str = "3.0.3"
DEBUG: bool = True  # debugging mode

# --- datetime and timezone related settings
CB_DELAY: float = 21.12  # [sec] delay for quarterly callbacks; this allows remote APIs to update
AUTUMN_EQUINOX_OFFSET: int = -7  # [days] offset to the start of winter
SPRING_EQUINOX_OFFSET: int = -7  # [days] offset to the start of summer
TZ: str = "Europe/Amsterdam"  # timezone used by the app (fixed for now)

# ### PRICES SETTINGS ### #
PRICES: dict = {
    "nul": 0.0,  # below this, electricity is considered for free
    "top": 20.0,  # greater difference between q1 avg and current price than this number is considered very expensive
    "entity": "sensor.bat1_energy_price",
    "attr": {
        "now": "state",
        "list": "attributes",
    },
    "update_interval": 15 * 60,  # seconds
    "adjust": {"hike": 0.021, "extra": 2.0, "taxes": 11.15, "btw": 1.21},
    "qry_now": "{viewer {homes {currentSubscription { priceInfo(resolution: QUARTER_HOURLY) {today      { total energy tax startsAt } } } } } }",
    "qry_nxt": "{viewer {homes {currentSubscription { priceInfo(resolution: QUARTER_HOURLY) {tomorrow   { total energy tax startsAt } } } } } }",
}

# ### HA WATCHDOG ENTITIES ### #
BAT_MIN_SOC_WD: str = "input_boolean.bats_min_soc"  # Detector if SoC is below minimum state of charge
CTRL_BY_ME: str = "input_boolean.bat_ctrl_app"  # Manual override of BatMan3 actions
EV_REQ_PWR: str = "input_boolean.evneedspwr"  # becomes active when EV charger is using power
#   PV-current watch dog
PV_CURRENT_WD: str = "input_boolean.pvovercurrent"  # becomes active when PV current > 23.5 A
ZOMWIN_OVERRIDE: str = "input_boolean.bat_winterstand"  # override current sunny/non-sunny
#   greediness is configurable in HA
GREED_C: str = "input_number.greed_ll"  # setting for greed LL
GREED_D: str = "input_number.greed_hh"  # setting for greed (diff)

# HA AUTOMATION SENSORS ### #
BAT_MIN_SOC: str = "sensor.bats_minimum_soc"  # SoC required to reach next 10AM on avg baseload
LOW_PV: str = "binary_sensor.lowpv"  # detector for low PV export/import values
PV_CURRENT: str = "sensor.pv_kwh_meter_current"  # current reading HomeWizard meter on PV
PV_POWER: str = "sensor.pv_kwh_meter_power"  # power reading HomeWizard meter on PV
PV_VOLTAGE: str = "sensor.pv_kwh_meter_voltage"  # voltage reading HomeWizard meter on PV
PV_CURRENT_MAX: float = 23.5  # [A(abs)] maximum current setting

# ### BATTERIES SETTINGS ### #
# create translation table between battery strategies and battalk stances
__short2long_strategy: dict[str, str] = {
    "idl": "POWER_STRATEGY_IDLE",
    "nom": "POWER_STRATEGY_NOM",
    "api": "POWER_STRATEGY_API",
    "dyn": "POWER_STRATEGY_ROI",
    "eco": "POWER_STRATEGY_ECO",
    "ext": "POWER_STRATEGY_SESSY_CONNECT",
}
__long2short_strategy: dict[str, str] = {}
for _k, _v in __short2long_strategy.items():
    __long2short_strategy[_v] = _k

# ### Talking to the batteries directly because HA/AP doesn't ###
BATTALK: dict[str, Any] = {
    "bats": ["bat1", "bat2"],
    "cts": ["p1"],
    "api_calls": {
        "strategy": "api/v1/power/active_strategy",  # bats(get/post)
        "status": "api/v1/power/status",  # bats(get)
        "setpoint": "api/v1/power/setpoint",  # bats(post)
        "grid_target": "api/v1/meter/grid_target",  # cts(get/post)
        "details": "api/v2/p1/details",  # cts(get)
    },
    "api_strats": __short2long_strategy,
    "bat_stances": __long2short_strategy,
}

# Maximum power at P1. Allow for consumers to kick in, so don't take up the full 35A
MAX_P1_ABS: int = int(35 * 230 * 0.9)
# maximum/minimum rates per battery
MAX_CHARGE: int = 2200  # W
# MIN_CHARGE: int = -160  # W
MAX_DISCHARGE: int = 1700  # W
# MIN_DISCHARGE: int = 160  # W
BAT_CAPACITY: int = 5000  # Wh

# Grid target setpoints
MAX_CHARGE_SP: int = 4400  # W
MAX_DISCHARGE_SP: int = -3400  # W
LPV_DISCHARGE_SP: int = -200  # W
# Grid target default
DEFAULT_XOM_SP: int = 0  # W

# Average round-trip efficiency is not read from HA because is hardly changes:
AVG_RTE: float = 0.8

# Number of quarters needed to fully charge a battery
_F = 1.4  # compensation factor to allow for variations in actual wattages used.
CHARGE_TIME: float = BAT_CAPACITY / MAX_CHARGE  # hours
CHARGE_SLOTS: int = int(CHARGE_TIME * 4 * _F)  # quarters needed to fully charge the batteries
DISCHG_TIME: float = BAT_CAPACITY / MAX_DISCHARGE * AVG_RTE
# quarters needed to fully discharge the batteries (must be (+)-ve!)
DISCHG_SLOTS: int = int(DISCHG_TIME * 4 * _F)
SWITCHEROO_DIFF: float = 2.5  # difference in SoC between batteries when to call the switcheroo

# Supported battery stances  (Sessy calls this 'strategy')
NOM: str = "nom"
IDLE: str = "idl"  # no power setting
DEFAULT_STANCE: str = NOM

# BATTERIES = ["sensor.bat1_state_of_charge", "sensor.bat2_state_of_charge"]
# SETPOINTS = ["number.bat1_power_setpoint", "number.bat2_power_setpoint"]
# BAT_XOM_SP = "number.sessy_p1_grid_target"
# # time between setpoint changes when ramping to a new setpoint
# RAMP_RATE = [0.4, 23]  # [growthrate, time between steps]
#


#
# # Due to some hardware configuration issues the sign of various sensors
# # may be confusing.
# # Care should be taken when interpreting values.
# # BATTERIES: DISCHARGING power is positive, CHARGING power is negative
# # PV_POWER: negative when supplying power to the home/grid, positive when CHARGING the batteries
# # PV_CURRENT: is always positive regardless of the direction of the current
