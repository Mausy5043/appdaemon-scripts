#!/usr/bin/env python3

# sensor.hours_till_10am

import datetime as dt
from zoneinfo import ZoneInfo

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import astral.sun as astsun
from astral import LocationInfo

# --- Configuration ---
ELEVATION = 11.0  # Target elevation in degrees
TOLERANCE = 0.1  # altitude tolerance


class NextMorning(hass.Hass):  # type: ignore[misc]
    def initialize(self):
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
        # Date to search on
        # date = dt.datetime.now().date() + dt.timedelta(days=0)

        # Run every minute to update the sensor
        # self.callback_handles.append(self.run_every(self.update_sunonpanels_sensor, dt.datetime.datetime.now(), 60))
        # Also run at startup
        self.update_sunonpanels_sensor(None)

    def terminate(self):
        """Clean up app."""
        self.log("__Terminating NextMorninf...")
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
        if _target < _now:
            self.log(f"Sun has passed {ELEVATION:.2f}deg today")
            _datum = _datum + dt.timedelta(days=1)
            _target = find_time_for_elevation(self.location, _datum, ELEVATION)

        self.log(f"Sun reaches {ELEVATION:.2f}deg at: {_target.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        #target = _now.replace(hour=_target.hour, minute=_target.minute, second=0, microsecond=0)

        total_seconds = (_target - _now).total_seconds()
        hours_until_10am = round(total_seconds / 3600, 2)

        # Update a Home Assistant entity (e.g., sensor.hours_till_10am_appdaemon)
        # You can choose a different entity_id if you prefer
        # self.set_state(
        #     "sensor.hours_till_10am",
        #     state=hours_until_10am,
        #     attributes={"unit_of_measurement": "h", "friendly_name": "Hours until next morning"},
        # )
        self.log(f"Time until next sun_on_panels: {hours_until_10am}")

    def get_eigen_bedrijf_history(self):
        """Get 6 hours of historical data from 'sensor.eigen_bedrijf'."""
        end_time = dt.datetime.now()
        start_time = end_time - dt.timedelta(hours=6)
        # get_history returns a dict with entity_id as key
        # TODO: make this a callback
        history = self.get_history(entity_id="sensor.eigen_bedrijf", start_time=start_time, end_time=end_time)
        self.log(f"6-hour history for sensor.eigen_bedrijf: {history}")
        # Extract the list of state changes for the sensor
        data = history.get("sensor.eigen_bedrijf", [])
        # Each item in data is a dict with 'state' and 'last_changed'
        # Convert states to float if needed
        values = [float(item["state"]) for item in data if "state" in item]
        self.log(f"6-hour history for sensor.eigen_bedrijf: {values}")

        return values


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
O 'sensor.hours_till_10am' is a prediction of the time until the 'binary_sensor.threshold_sun_on_panels_east' will turn on
  (this used to be a template sensor that calculated the time till 10AM).
x 'input_number.home_baseload' is calculated by a Node-RED automation:
    (1) 'binary_sensor.threshold_sun_on_panels_east' which turns on when the sun elevation becomes > 11.5 degrees
    (2) 6 hours of historical data is gathered from 'sensor.eigen_bedrijf'
    (3) median of the data is calculated
    (4) -> input_number.home_baseload
o 'sensor.bats_minimum_soc' is a template sensor that calculates: hours_till_10am * home_baseload
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
