import datetime as dt

"""Utility functions for the Batman app."""


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
