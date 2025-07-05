#!/usr/bin/env python3

# sensor.hours_till_10am

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import appdaemon.plugins.hass.hassapi as hass
import pytz
from astral import LocationInfo
from astral.sun import elevation

# --- Configuration ---
city = "Tilburg"
country = "Netherlands"
zonename = "Europe/Amsterdam"
lat = 51.5556
long = 5.0913
altitude = 11.0  # Target elevation in degrees
tolerance = 0.1  # altitude tolerance
local_timezone = pytz.timezone(zonename)

# Define your location
location = LocationInfo(city, country, zonename, lat, long)

# Target elevation
target_elevation = altitude

# Date to search on
date = datetime.now().date() + timedelta(days=0)
tz = ZoneInfo(location.timezone)


# Binary search for time when sun reaches target elevation
def find_time_for_elevation(location, date, tz, target_elevation, tolerance=tolerance):
    start = datetime.combine(date, datetime.min.time(), tzinfo=tz)
    end = start + timedelta(days=1)

    while (end - start).total_seconds() > 1:  # 1-second precision
        mid = start + (end - start) / 2
        alt = elevation(observer=location.observer, dateandtime=mid)

        if abs(alt - target_elevation) < tolerance:
            return mid
        elif alt < target_elevation:
            start = mid
        else:
            end = mid
    return start


class NextMorning(hass.Hass):
    def initialize(self):
        # Run every minute to update the sensor
        self.run_every(self.update_hours_sensor, datetime.datetime.now(), 60)
        # Also run at startup
        self.update_hours_sensor(None)

    def update_hours_sensor(self, kwargs):
        datum = datetime.now().date() + timedelta(days=0)
        tz = ZoneInfo(location.timezone)
        target = find_time_for_elevation(location, datum, tz, target_elevation)
        target_hr = target.hour
        target_mn = target.minute

        now = datetime.datetime.now()
        target = now.replace(hour=target_hr, minute=target_mn, second=0, microsecond=0)

        # If current time is past 10 AM, set target to 10 AM tomorrow
        if now > target:
            target = target + datetime.timedelta(days=1)

        total_seconds = (target - now).total_seconds()
        hours_until_10am = round(total_seconds / 3600, 2)

        # Update a Home Assistant entity (e.g., sensor.hours_till_10am_appdaemon)
        # You can choose a different entity_id if you prefer
        self.set_state(
            "sensor.hours_till_10am_appdaemon",
            state=hours_until_10am,
            attributes={"unit_of_measurement": "h", "friendly_name": "Hours until 10 AM (AppDaemon)"},
        )
        self.log(f"Hours until 10 AM updated: {hours_until_10am}")
