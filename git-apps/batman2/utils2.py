import datetime as dt
import math

import const2 as cs
import pytz

"""Utility functions for the Batman apps."""


def log_entity_attr(hass, entity_id, attribute="all", level="DEBUG") -> None:
    """Log everything we can known about an entity."""
    entity_state = hass.get_state(entity_id, attribute=attribute)
    if isinstance(entity_state, dict):
        for key, value in entity_state.items():
            hass.log(f"____{key}: {value}", level=level)
    else:
        hass.log(f"____{entity_id} ({attribute}): {entity_state}", level=level)


def sort_index(lst: list, rev=True) -> list:
    """Return a list of indexes of the sorted list of prices provided"""
    s: list = [i[0] for i in sorted(enumerate(lst), key=lambda x: x[1], reverse=rev)]
    return s


def next_hour(stamp: dt.datetime) -> dt.datetime:
    """Return timestamp of the next whole hour."""
    return stamp.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)


def next_half_hour(stamp: dt.datetime) -> dt.datetime:
    """Return timestamp of the next full half-hour."""
    minutes = 30 if stamp.minute < 30 else 0
    next_time = stamp.replace(minute=minutes, second=0, microsecond=0)

    if next_time <= stamp:
        next_time += dt.timedelta(hours=1)

    return next_time


def hours_until_next_10am() -> int:
    """Calculate the number of hours until the next 10 A.M."""
    cest = pytz.timezone(cs.TZ)
    now = dt.datetime.now(cest)
    next_10am = now.replace(hour=10, minute=0, second=0, microsecond=0)

    if now > next_10am:
        next_10am += dt.timedelta(days=1)

    time_diff = next_10am - now
    hours_until_10am = math.ceil(time_diff.total_seconds() / 3600)

    return hours_until_10am


def is_sunny_day(datum: dt.date) -> bool:
    """Check if the given date is likely to be a sunny day.
    A sunny day is defined as a day between the spring and autumn approximate equinoxes.
    It is expected that power production is high enough during this period.
    """
    year = datum.year
    # Approximate equinox dates (can be adjusted for precision)
    spring_equinox = dt.date(year, 3, 21)
    autumn_equinox = dt.date(year, 9, 21)
    return spring_equinox <= datum <= autumn_equinox


def get_these_days() -> dict:
    """Get today's date, tomorrow's date, and whether today is a sunny day.

    Returns:
        dict: today's date, tomorrow's date, and a boolean indicating if today is sunny
    """
    return {
        "today": dt.date.today(),
        "tomor": dt.date.today() + dt.timedelta(days=1),
        "sunny": is_sunny_day(dt.date.today()),
    }


def get_greedy(price: float, lo_price: float, hi_price: float) -> int:
    """Determine if the price is low, high, or neutral.
    Greediness is determined based on predefined price thresholds:
    - Low price: less than the 'nul' price threshold (greedy for low).
    - High price: greater than the 'top' price threshold (greedy for high).
    - Neutral price: between the 'nul' and 'top' thresholds (not greedy).

    Args:
        price (float): The price to evaluate.

    Returns:
        -1 for low price (greedy for low),
         0 for neutral price (not greedy),
         1 for high price (greedy for high).
    """
    _g = 0  # not greedy
    if price <= lo_price:
        _g = -1  # greedy for low price
    if price >= hi_price:
        _g = 1  # greedy for high price

    return _g


def get_steps(stepsize: float, deadband: float = 0.1):
    """Calculate the number of steps required to get from 0 to 100% given a stepsize."""
    return math.ceil(math.log(deadband) / math.log(1 - stepsize))
