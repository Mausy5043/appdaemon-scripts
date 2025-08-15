#!/usr/bin/env python3

# sensor.next_sun_on_panels

import contextlib
import datetime as dt
import statistics as stat
from zoneinfo import ZoneInfo

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import astral.sun as astsun
from astral import LocationInfo

# --- Configuration ---
ELEVATION = 11.11  # target elevation of the sun in degrees
TOLERANCE = 0.005  # elevation tolerance
CB_TIME = 60  # callback interval in seconds
# CONVERSION is based on
# 2 batteries
# each 5200 Wh when @ 100%
CONVERSION = 2 * 5200 / 100

VERSION = "1.1.2"


class NextMorning(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        self.log(f"============================== NextMorning v{VERSION} ====")
        self.starting = True
        self.callback_handles: list = []
        self.secrets = self.get_app("scrts")
        cfg: dict = self.secrets.get_location()
        # Define our location
        self.location = LocationInfo(
            cfg["city"],
            cfg["country"],
            cfg["timezone"],
            float(cfg["latitude"]),
            float(cfg["longitude"]),
        )

        # Initial run at startup
        _eb_median: str = self.get_state(
            entity_id="input_number.home_baseload",
            attribute="state",
            default="234.5",
        )
        self.eb_median: float = float(_eb_median)
        self.update_sunonpanels_sensor(None)
        self.log(f"Median own usage past 6 hours: {self.get_eigen_bedrijf_history():.2f} W ")

        # Run every minute to update the sensor
        # self.callback_handles.append(self.run_every(self.update_sunonpanels_sensor, dt.datetime.now(), CB_TIME))
        self.run_every(self.update_sunonpanels_sensor, dt.datetime.now(), CB_TIME)
        self.starting = False

    def terminate(self):
        """Clean up app."""
        self.log("__Terminating NextMorning...")
        # Cancel all registered callbacks
        for handle in self.callback_handles:
            self.cancel_listen_state(handle)
        self.callback_handles.clear()
        self.log("__...terminated NextMorning.")

    def update_sunonpanels_sensor(self, kwargs):
        _tz = ZoneInfo(self.location.timezone)
        _now = dt.datetime.now(_tz)
        _datum = _now.date() + dt.timedelta(days=0)
        _target = find_time_for_elevation(self.location, _datum, ELEVATION)

        # determine solar elevation and time when reaching ELEVATION +/- TOLERANCE
        if _target < _now:
            if self.starting:
                self.log(f"Sun has passed {ELEVATION:.2f} deg today")
            _datum = _datum + dt.timedelta(days=1)
            _target = find_time_for_elevation(self.location, _datum, ELEVATION)
        if self.starting:
            self.log(f"Sun reaches {ELEVATION:.2f} deg at: {_target.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        _t_sec = (_target - _now).total_seconds()
        self.next_sun_on_panels = round(_t_sec / 3600, 2)
        if self.starting:
            self.log(f"Time until next sun_on_panels: {self.next_sun_on_panels:.2f} hours")

        # Update the prediction in HA
        self.set_state(
            "sensor.next_sun_on_panels",
            state=self.next_sun_on_panels,
            attributes={
                "unit_of_measurement": "h",
                "friendly_name": "next_sun_on_panels",
            },
        )

        # When we're close to the predicted time we calculate the new home baseload
        if _t_sec <= CB_TIME:
            self.log(f"{_t_sec:.0f} secs to sun on panels, updating home baseload")
            eb_median = int(round(self.get_eigen_bedrijf_history(),0))
            self.set_eigen_bedrijf_median(eb_median)

        # calculate the minimum SoC required to reach the predicted time and 5% margin
        minimum_soc: float = round((self.next_sun_on_panels * self.eb_median / CONVERSION) + 5.0, 2)
        if self.starting:
            self.log(f"Calculated minimum SoC: {minimum_soc:.2f} %")
        self.set_state(
            "sensor.bats_minimum_soc",
            state=minimum_soc,
            attributes={
                "unit_of_measurement": "%",
                "friendly_name": "bats_minimum_soc",
            },
        )

    def get_eigen_bedrijf_history(self) -> float:
        """Get 6 hours of historical data from 'sensor.eigen_bedrijf'."""
        end_time = dt.datetime.now()
        start_time = end_time - dt.timedelta(hours=6)
        # get_history returns a dict with entity_id as key
        history: list = self.get_history(
            entity_id="sensor.eigen_bedrijf", start_time=start_time, end_time=end_time
        )
        # Extract the list of state changes for the sensor
        data = []
        for _d in history[0]:
            with contextlib.suppress(ValueError):
                _dstate = float(_d["state"])
                data.append(_dstate)
        return stat.median(data)

    def set_eigen_bedrijf_median(self, value: float):
        # Update the Home Assistant entity
        self.log(f"Setting home baseload: {value:.2f} W")
        self.set_state(
            "input_number.home_baseload",
            state=value,
            attributes={
                "unit_of_measurement": "W",
                "friendly_name": "home_baseload",
            },
        )


# Binary search for time when sun reaches target elevation
def find_time_for_elevation(locatie, datum, elevatie, tolerance=TOLERANCE):
    start = dt.datetime.combine(datum, dt.datetime.min.time(), tzinfo=ZoneInfo(locatie.timezone))
    end = start + dt.timedelta(days=1)

    while (end - start).total_seconds() > 1:  # 1-second precision
        mid = start + (end - start) / 2
        alt = astsun.elevation(observer=locatie.observer, dateandtime=mid)

        if abs(alt - elevatie) < tolerance:
            return mid
        elif alt < elevatie:
            start = mid
        else:
            end = mid
    return start


"""
Calculate the amount of SoC required to reach the next morning.


- Each battery has it's own SoC sensor.
o 'sensor.bats_avg_soc' (template) calculates the average value of the batteries SoC's
O 'sensor.next_sun_on_panels' is a prediction of the time until the 'binary_sensor.threshold_sun_on_panels_east' will turn on
  (this used to be a template sensor that calculated the time till 10AM).
x 'input_number.home_baseload' is calculated by update_sunonpanels_sensor() function:
    (1) predicted time until sun on panels becomes less than 60s
    (2) 6 hours of historical data is gathered from 'sensor.eigen_bedrijf'
    (3) median of the data is calculated
    (4) -> input_number.home_baseload
o 'sensor.bats_minimum_soc' is a template sensor that calculates: next_sun_on_panels * home_baseload
o 'input_boolean.bats_min_soc' toggles when 'sensor.bats_avg_soc' passes through the bats_minimum_soc threshold
  ON when average SoC is below the threshold value; OFF when it is above
x Batman2 receives a callback everytime when bats_min_soc triggers (ON and OFF)
x 'sensor.bats_minimum_soc' is used by batman2 to determine the level above which the batteries
  may be discharged or below which they must be charged.

- "Next morning" is the moment the sun reaches the elevation at which the solar panels start delivering
The SoC required is the number of minutes until next morning * the home_baseload.
every minute:
- determine avg SoC  & deprecate 'sensor.bats_avg_soc'
- predict next sun on panels
- get baseload
- calculate bats_minimum_soc
"""

"""
2025-07-06 10:21:14.345721 INFO nxtmorning: 6-hour history for sensor.eigen_bedrijf:
[
    [
        {
            'entity_id': 'sensor.eigen_bedrijf',
            'state': '228.4',
            'attributes':  {'unit_of_measurement': 'W', 'friendly_name': 'eigen_bedrijf'},
            'last_changed': datetime.datetime(2025, 7, 6, 4, 21, 14, 21871, tzinfo=<DstTzInfo 'Europe/Amsterdam' CEST+2:00:00 DST>),
            'last_updated': datetime.datetime(2025, 7, 6, 4, 21, 14, 21871, tzinfo=<DstTzInfo 'Europe/Amsterdam' CEST+2:00:00 DST>)
        },
        {
            'entity_id': 'sensor.eigen_bedrijf',
            'state': '224.7',
            'attributes': {'unit_of_measurement': 'W', 'friendly_name': 'eigen_bedrijf'},
            'last_changed': datetime.datetime(2025, 7, 6, 4, 21, 21, 654572, tzinfo=<DstTzInfo 'Europe/Amsterdam' CEST+2:00:00 DST>),
            'last_updated': datetime.datetime(2025, 7, 6, 4, 21, 21, 654572, tzinfo=<DstTzInfo 'Europe/Amsterdam' CEST+2:00:00 DST>)
            }
"""
