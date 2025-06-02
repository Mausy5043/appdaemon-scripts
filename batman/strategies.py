import datetime as dt

import const as cs

"""Handle power strategies for Batman app."""


def now_change(haas, entity, attribute, old, new, **kwargs) -> None:
    """Log change of current strategy."""
    haas.log(f"State changed for {entity} ({attribute}): {old} -> {new}")
    haas.now_strategy = int(new)


def lst_changed(haas, entity, attribute, old, new, **kwargs) -> None:
    """Handle changes in the power strategy."""
    haas.log(f"Strategies changed: {old} -> {new}")
    # Update today's and tomorrow's strategies
    today = dt.date.today()
    tomorrow = today + dt.timedelta(days=1)
    haas.todays_strategy = get_strategy(hass, today)

    haas.tomorrows_strategy = get_strategy(hass, tomorrow)


def get_strategy(haas, datum) -> list[int]:
    """Get the power strategy for a specific date."""
    no_strategy: list[int] = [0] * 24
    if isinstance(datum, dt.date):
        date_str: str = datum.strftime("%Y-%m-%d")
        attr: dict = haas.get_state(entity_id=cs.ENT_STRATEGY, attribute=cs.LST_STRATEGY_ATTR)
        return attr.get(date_str, no_strategy)
    else:
        haas.log(f"Invalid date: {datum}", level="ERROR")
        return no_strategy
