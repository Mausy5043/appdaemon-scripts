#!/usr/bin/env python3

# sensor.next_sun_on_panels

import contextlib
import datetime as dt
import statistics as stat
import traceback
from functools import partial
from statistics import quantiles as stqu
from zoneinfo import ZoneInfo

import appdaemon.plugins.hass.hassapi as hass  # type: ignore[import-untyped]
import astral.sun as astsun
from astral import LocationInfo

# --- Configuration ---
ELEVATION: float = 11.11  # target elevation of the sun in degrees
TOLERANCE: float = 0.005  # elevation tolerance
CB_TIME: int = 60  # callback interval in seconds
# CONVERSION is based on
# 2 batteries
# each 5200 Wh when @ 100%
CONVERSION: float = 2 * 5200 / 100
HISTORY_HOURS: float = 24.0  # hours of historical data to fetch from 'sensor.eigen_bedrijf'
ENTITY_BASELOAD: str = "input_number.home_baseload"  # entity to update with the calculated baseload
ENTITY_EB: str = "sensor.eigen_bedrijf"  # entity from which to fetch historical data
ATTR_NSOP: dict = {"unit_of_measurement": "h", "friendly_name": "next_sun_on_panels"}
ATTR_BMS: dict = {"unit_of_measurement": "%", "friendly_name": "bats_minimum_soc"}
ATTR_BL: dict = {"unit_of_measurement": "W", "friendly_name": "home_baseload"}
EPS: float = 0.0001


VERSION: str = "1.4.1"


class NextMorning(hass.Hass):  # type: ignore[misc]
    def initialize(self):
        self.log(f"============================== NextMorning v{VERSION} ====")
        self.starting = True
        self.callback_handles: list = []
        self.callback_active: bool = False
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
        _eb_median: str = self.get_state(entity_id=ENTITY_BASELOAD, attribute="state", default="234.5")
        self.eb_median: float = float(_eb_median)
        self.update_sunonpanels_sensor(None)
        # to prevent updating the value we ask for a bit more data
        self.get_eigen_bedrijf_history(hours=HISTORY_HOURS + 0.1)

        # Run every minute to update the sensor
        # self.callback_handles.append(
        self.run_every(self.update_sunonpanels_sensor, dt.datetime.now(), CB_TIME)
        # )
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
        _datum = _now.date()
        _target = find_time_for_elevation(self.location, _datum, ELEVATION)
        # determine solar elevation and time when reaching ELEVATION +/- TOLERANCE
        if _target < _now:
            if self.starting:
                self.log(f"Sun has passed {ELEVATION:.2f} deg today")
            _datum += dt.timedelta(days=1)
            _target = find_time_for_elevation(self.location, _datum, ELEVATION)
        if self.starting:
            self.log(f"Sun reaches {ELEVATION:.2f} deg at: {_target.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        _t_sec: float = max(0.0, (_target - _now).total_seconds())  # avoid negative _t_sec in edge-cases
        self.next_sun_on_panels: float = round(_t_sec / 3600, 2)
        if self.starting:
            self.log(f"Time until next sun_on_panels : {self.next_sun_on_panels:.2f} hours")

        # Update the prediction in HA
        try:
            self.set_state(
                entity_id="sensor.next_sun_on_panels", state=self.next_sun_on_panels, attributes=ATTR_NSOP
            )
        except Exception as her:
            self.log(str(type(her)), level="ERROR")
            self.log(str(her), level="ERROR")
            self.log(traceback.format_exc(), level="ERROR")
            self.log(
                f"Could not update sensor.next_sun_on_panels with {self.next_sun_on_panels} hr",
                level="ERROR",
            )

        # and update the minimum SoC required to reach the next morning
        self.set_bats_minimum_soc()

        # When we're close to the predicted time we also calculate the new home baseload
        if _t_sec <= CB_TIME:
            self.log(f"{_t_sec:.0f} secs to sun on panels, updating home baseload")
            self.get_eigen_bedrijf_history(hours=HISTORY_HOURS)
            self.callback_active = True

    def set_bats_minimum_soc(self):
        """Calculate and update the minimum SoC required to reach the next morning."""
        # calculate the minimum SoC required to reach the predicted time
        minimum_soc: float = round((self.next_sun_on_panels * self.eb_median / CONVERSION), 1)
        if self.starting:
            self.log(f"Calculated minimum SoC        : {minimum_soc:.2f} %")
        try:
            if abs(minimum_soc) < EPS:
                minimum_soc = EPS
            self.set_state(entity_id="sensor.bats_minimum_soc", state=minimum_soc, attributes=ATTR_BMS)
        except Exception as her:
            self.log(str(type(her)), level="ERROR")
            self.log(str(her), level="ERROR")
            self.log(traceback.format_exc(), level="ERROR")
            self.log(f"Could not update sensor.bats_minimum_soc with {minimum_soc} %", level="ERROR")

    def set_baseload(self, value: float):
        """Update the Home Baseload with the median own usage (eigen bedrijf)."""
        self.log(f"Setting home baseload: {value:.2f} W")
        try:
            if abs(value) < EPS:
                value = EPS
            self.set_state(entity_id=ENTITY_BASELOAD, state=value, attributes=ATTR_BL)
        except Exception as her:
            self.log(str(type(her)), level="ERROR")
            self.log(str(her), level="ERROR")
            self.log(traceback.format_exc(), level="ERROR")
            self.log(f"Could not update {ENTITY_BASELOAD} with {value} W", level="ERROR")

    def get_eigen_bedrijf_history(self, hours: float) -> None:
        """Request X hours of historical data from 'sensor.eigen_bedrijf'."""
        end_time = dt.datetime.now()
        start_time = end_time - dt.timedelta(hours=hours)
        # get_history returns a dict with entity_id as key
        # we use a callback to process the data when it arrives
        _cb = partial(self.get_eigen_bedrijf_history_cb, hours=hours)
        self.get_history(entity_id=ENTITY_EB, start_time=start_time, end_time=end_time, callback=_cb)
        self.log(f"Requested {hours:.1f} hours of history for sensor.eigen_bedrijf")

    def get_eigen_bedrijf_history_cb(self, **kwargs) -> None:
        """Callback to process the X-hour history data from 'sensor.eigen_bedrijf'.

        Args:
            kwargs: dict with 'result'

        Returns:
            None
        """
        # Extract the list of state changes for the sensor
        hours: float = kwargs["hours"]
        history: list = kwargs["result"]
        _res = self.calc_stats(history[0], hours)

        if hours == HISTORY_HOURS:
            self.set_baseload(_res)
            self.eb_median = _res
            self.set_bats_minimum_soc()
        self.callback_active = False

    def calc_stats(self, history: list, hours: float) -> int:
        """Calculate various statistics of the historical data.

        Args:
            history: list of state changes from get_history
            hours:   number of hours the history covers

        Returns:
            int: median of the historical data"""
        data = []
        # _prev = self.eb_median  # use baseload as initial previous value
        _dstate: float = self.eb_median
        self.log(f"Processing history callback for {hours} hours")
        for _d in history:
            with contextlib.suppress(ValueError):
                _prev = _dstate
                _dstate = float(_d["state"])
                # due to a mismatch in update intervals of the various kWh-meters we sometimes get negative values
                # in that case we use the previous value
                if _dstate <= 0.0:
                    _dstate = _prev
                data.append(_dstate)
        _mean_data = int(round(stat.fmean(data), 0))
        _median_data = int(round(stat.median(data), 0))
        _q1 = int(round(stqu(data, n=4, method="inclusive")[0], 0))
        _q3 = int(round(stqu(data, n=4, method="inclusive")[2], 0))
        self.usage_stats = {
            "min": int(round(min(data), 0)),
            "q1": _q1,
            "med": _median_data,
            "avg": _mean_data,
            "q3": _q3,
            "max": int(round(max(data), 0)),
            "iqr": _q3 - _q1,
        }
        data_stats = (
            f"Min: {self.usage_stats.get('min', 'N/A'):.0f}, "
            f"Q1 : {self.usage_stats.get('q1', 'N/A'):.0f}, "
            f"Med: {self.usage_stats.get('med', 'N/A'):.0f}, "
            f"Avg: {self.usage_stats.get('avg', 'N/A'):.0f}, "
            f"Q3 : {self.usage_stats.get('q3', 'N/A'):.0f}, "
            f"Max: {self.usage_stats.get('max', 'N/A'):.0f}, "
            f"IQR: {self.usage_stats.get('iqr', 'N/A'):.0f}"
        )
        # if avg > Q3 then avg does not represent the baseload (probably caused by EV charging)
        # if avg < Q3 then pick either median or avg depending on which is bigger.
        _ret_value = max(_median_data, min(_mean_data, _q3))  # _median_data
        self.log(f"Statistics own usage past {hours} hours:\n :\t\t {data_stats} => {_ret_value:.0f}")
        return _ret_value


def find_time_for_elevation(
    locatie: LocationInfo, datum: dt.date, elevatie: float, tolerance: float = TOLERANCE
) -> dt.datetime:
    """Search for the time when the sun reaches the given target elevation.

    Args:
        locatie     location of the Earth for which to do the calculation
        datum       starting date
        elevatie    desired elevation of the sun (degrees)
        tolerance   tolerance in the elevation (degrees)
    """
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
