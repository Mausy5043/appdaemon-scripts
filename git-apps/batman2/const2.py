"""Provides constants for the Batman2 app."""

# ### GENERAL SETTINGS ### #
VERSION = "0.1.0"
# debugging mode
DEBUG = True
# timezone for the app
TZ = "Europe/Amsterdam"
# maximum rates per battery
MAX_CHARGE = -2200
MAX_DISCHARGE = 1700
# set to True to enable more aggressive (dis)charging when prices are favourable
TRADING = False
# stances
NOM = "NOM"
DISCHARGE = "API"  # (+)-ve power setting
DISCHARGE_PWR = 1700  # W
CHARGE = "API"  # (-)-ve power setting
CHARGE_PWR = -2200  # W
IDLE = "IDLE"  # no power setting
DEFAULT_STANCE = NOM
# EV assist
# when True, the app will assist the EV charging when prices are high (>Q3)
# when False, the app will not assist the EV charging
EV_ASSIST = False


# ### PRICES SETTINGS ### #
PRICES: dict = {
    "nul": 0.0,  # below this, electricity is considered for free
    "top": 35.0,  # above this, electricity is considered very expensive
    "entity": "sensor.bat1_energy_price",
    "attr": {
        "now": "state",
        "list": "attributes",
    },
    "adjust": {"hike": 0.021, "extra": 2.0, "taxes": 10.15, "btw": 1.21},
}
