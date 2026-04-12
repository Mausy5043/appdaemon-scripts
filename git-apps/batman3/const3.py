"""Provides constants for the Batman3 app."""

# from typing import Any

# ### GENERAL SETTINGS ### #
VERSION: str = "3.0.1"
DEBUG: bool = True # debugging mode

# --- datetime and timezone related settings
AUTUMN_EQUINOX_OFFSET: int = -7  # [days] offset to the start of winter
SPRING_EQUINOX_OFFSET: int = -7  # [days] offset to the start of summer
TZ: str = "Europe/Amsterdam"  # timezone used by the app (fixed for now)

# ### PRICES SETTINGS ### #
PRICES: dict = {
    # "nul": 0.0,  # below this, electricity is considered for free
    # "top": 12.5,  # greater difference between lowest and current price than this number is considered very expensive
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

# Watchdog entities
BAT_MIN_SOC_WD: str = "input_boolean.bats_min_soc"  # Detector if SoC is below minimum state of charge
CTRL_BY_ME: str = "input_boolean.bat_ctrl_app"  # Manual override of BatMan3 actions
EV_REQ_PWR: str = "input_boolean.evneedspwr"  # becomes active when EV charger is using power
#   PV-current watch dog
PV_CURRENT_WD: str = "input_boolean.pvovercurrent"  # becomes active when PV current > 23.5 A
ZOMWIN_OVERRIDE: str = "input_boolean.bat_winterstand"  # override current sunny/non-sunny
#   greediness is configurable in HA
GREED_C: str = "input_number.greed_ll"  # setting for greed LL
GREED_D: str = "input_number.greed_hh"  # setting for greed (diff)

# HA automation sensors:
BAT_MIN_SOC: str = "sensor.bats_minimum_soc"  # SoC required to reach next 10AM base on avg baseload
LOW_PV: str = "binary_sensor.lowpv"  # detector for low PV export/import values
PV_CURRENT: str = "sensor.pv_kwh_meter_current"  # current reading HomeWizard meter on PV
PV_POWER: str = "sensor.pv_kwh_meter_power"  # power reading HomeWizard meter on PV
PV_VOLTAGE: str = "sensor.pv_kwh_meter_voltage"  # voltage reading HomeWizard meter on PV
PV_CURRENT_MAX: float = 23.5  # [A(abs)] maximum current setting

# # maximum rates per battery
# MAX_CHARGE = -2200
# MIN_CHARGE = -160
# MAX_DISCHARGE = 1700
# MIN_DISCHARGE = 160
# # Average round-trip efficiency is not read from HA because is hardly changes:
# AVG_RTE = 0.8
# # set to True to enable more aggressive (dis)charging when prices are favourable
# TRADING = False
# # number of hours that we want to (dis)charge the batteries when prices are favourable
# # index 0 is for charging, index 1 is for discharging
# SLOTS = [18, 12]
# # stances  (Sessy calls this 'strategy')
# NOM: str = "NOM"
# DISCHARGE: str = "API+"  # (+)-ve power setting
# DISCHARGE_PWR: int = 1700  # W
# CHARGE: str = "API-"  # (-)-ve power setting
# CHARGE_PWR: int = -2200  # W
# IDLE: str = "IDLE"  # no power setting
# DEFAULT_STANCE: str = NOM
# # EV assist
# # when True, the app will assist the EV charging, notably when prices are high (>Q3)
# # when False, the app will not assist the EV charging
# EV_ASSIST = False

# BATTERIES = ["sensor.bat1_state_of_charge", "sensor.bat2_state_of_charge"]
# SETPOINTS = ["number.bat1_power_setpoint", "number.bat2_power_setpoint"]
# BAT_XOM_SP = "number.sessy_p1_grid_target"
# BAT_STANCE = ["select.bat1_power_strategy", "select.bat2_power_strategy"]
# # time between setpoint changes when ramping to a new setpoint
# RAMP_RATE = [0.4, 23]  # [growthrate, time between steps]
#

#
# # create translation table between battery strategies and battalk stances
# __short2long_strategy: dict[str, str] = {
#     "idle": "POWER_STRATEGY_IDLE",
#     "api": "POWER_STRATEGY_API",
#     "nom": "POWER_STRATEGY_NOM",
# }
# __long2short_strategy: dict[str, str] = {}
# for _k, _v in __short2long_strategy.items():
#     __long2short_strategy[_v] = _k
#
# # ### Talking to the batteries directly because HA/AP doesn't ###
# BATTALK: dict[str, Any] = {
#     "bats": ["bat1", "bat2"],
#     "api_calls": {
#         "strategy": "api/v1/power/active_strategy",
#         "status": "api/v1/power/status",
#         "setpoint": "api/v1/power/setpoint",
#         "grid_target": "api/v1/meter/grid_target",
#     },
#     "api_strats": __short2long_strategy,
#     "bat_stances": __long2short_strategy,
# }
#
# # Due to some hardware configuration issues the sign of various sensors
# # may be confusing.
# # Care should be taken when interpreting values.
# # BATTERIES: DISCHARGING power is positive, CHARGING power is negative
# # PV_POWER: negative when supplying power to the home/grid, positive when CHARGING the batteries
# # PV_CURRENT: is always positive regardless of the direction of the current
