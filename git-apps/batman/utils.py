import datetime as dt
import math

import const as cs
import pytz

"""Utility functions for the Batman apps."""


def log_entity_attr(hass, entity_id, attribute="all", level="DEBUG"):
    """Log everything we can known about an entity."""
    entity_state = hass.get_state(entity_id, attribute=attribute)
    if isinstance(entity_state, dict):
        for key, value in entity_state.items():
            hass.log(f"____{key}: {value}", level=level)
    else:
        hass.log(f"____{entity_id} ({attribute}): {entity_state}", level=level)


def sort_index(lst: list, rev=True):
    s: list = [i[0] for i in sorted(enumerate(lst), key=lambda x: x[1], reverse=rev)]
    return s


def next_hour(stamp: dt.datetime) -> dt.datetime:
    """Return stamp with minutes, seconds and microseconds set to zero and hour increased by 1h."""
    return stamp.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)


def next_half_hour(stamp: dt.datetime) -> dt.datetime:
    """Return stamp with seconds and microseconds set to zero and time advanced to the next full half-hour."""
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
