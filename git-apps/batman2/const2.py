"""Provides constants for the Batman2 app."""

from typing import Any

# ### GENERAL SETTINGS ### #
VERSION = "2.2.2"
# debugging mode
DEBUG = True
# timezone for the app
TZ = "Europe/Amsterdam"
# maximum rates per battery
MAX_CHARGE = -2200
MAX_DISCHARGE = 1700
# set to True to enable more aggressive (dis)charging when prices are favourable
TRADING = False
# stances  (Sessy calls this 'strategy')
NOM: str = "NOM"
DISCHARGE: str = "API+"  # (+)-ve power setting
DISCHARGE_PWR: int = 1700  # W
CHARGE: str = "API-"  # (-)-ve power setting
CHARGE_PWR: int = -2200  # W
IDLE: str = "IDLE"  # no power setting
DEFAULT_STANCE: str = NOM
# EV assist
# when True, the app will assist the EV charging, notably when prices are high (>Q3)
# when False, the app will not assist the EV charging
EV_ASSIST = False
# HA automation: becomes active when EV charger is using power
EV_REQ_PWR = "input_boolean.evneedspwr"
# HA automation: to manually override BatMan2 actions
CTRL_BY_ME = "input_boolean.bat_ctrl_app"
# HA automation: SoC required to reach next 10AM base on avg baseload
BAT_MIN_SOC = "sensor.bats_minimum_soc"
# HA automation: watchdog to detect if SoC is below minimum state of charge
BAT_MIN_SOC_WD = "input_boolean.bats_min_soc"
# current reading HomeWizard meter on PV
PV_CURRENT = "sensor.pv_kwh_meter_current"
# PV-current watch dog > 23.5 A
PV_CURRENT_WD = "input_boolean.pvovercurrent"
PV_CURRENT_MAX = 23.5  # A;abs
# voltage reading HomeWizard meter on PV
PV_VOLTAGE = "sensor.pv_kwh_meter_voltage"
# power reading HomeWizard meter on PV
PV_POWER = "sensor.pv_kwh_meter_power"
BATTERIES = ["sensor.bat1_state_of_charge", "sensor.bat2_state_of_charge"]
SETPOINTS = ["number.bat1_power_setpoint", "number.bat2_power_setpoint"]
BAT_XOM_SP = "number.sessy_p1_grid_target"
BAT_STANCE = ["select.bat1_power_strategy", "select.bat2_power_strategy"]
# time between setpoint changes when ramping to a new setpoint
RAMP_RATE = [0.4, 23]  # [growthrate, time between steps]
WINTERSTAND = "input_boolean.bat_winterstand"

# make greediness configurable in HA
GREED_LL = "input_number.greed_ll"
GREED_HH = "input_number.greed_hh"
# ### PRICES SETTINGS ### #
PRICES: dict = {
    "nul": 0.0,  # below this, electricity is considered for free
    "top": 12.5,  # greater difference between lowest and current price than this number is considered very expensive
    "entity": "sensor.bat1_energy_price",
    "attr": {
        "now": "state",
        "list": "attributes",
    },
    "adjust": {"hike": 0.021, "extra": 2.0, "taxes": 10.15, "btw": 1.21},
    "qry_now": "{viewer {homes {currentSubscription { priceInfo {today      { total energy tax startsAt } } } } } }",
    "qry_nxt": "{viewer {homes {currentSubscription { priceInfo {tomorrow   { total energy tax startsAt } } } } } }",
}

# create translation table between battery strategies and battalk stances
__short2long_strategy: dict[str, str] = {
    "idle": "POWER_STRATEGY_IDLE",
    "api": "POWER_STRATEGY_API",
    "nom": "POWER_STRATEGY_NOM",
}
__long2short_strategy: dict[str, str] = {}
for _k, _v in __short2long_strategy.items():
    __long2short_strategy[_v] = _k

# ### Talking to the batteries directly because HA/AP doesn't ###
BATTALK: dict[str, Any] = {
    "bats": ["bat1", "bat2"],
    "api_calls": {
        "strategy": "api/v1/power/active_strategy",
        "status": "api/v1/power/status",
        "setpoint": "api/v1/power/setpoint",
        "grid_target": "api/v1/meter/grid_target",
    },
    "api_strats": __short2long_strategy,
    "bat_stances": __long2short_strategy,
}

# Due to some hardware configuration issues the sign of various sensors
# may be confusing.
# Care should be taken when interpreting values.
# BATTERIES: DISCHARGING power is positive, CHARGING power is negative
# PV_POWER: negative when supplying power to the home/grid, positive when CHARGING the batteries
# PV_CURRENT: is always positive regardless of the direction of the current
