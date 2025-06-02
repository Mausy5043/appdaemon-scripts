import datetime as dt

import const as cs

"""Handle energy prices for Batman app."""


def now_change(haas, entity, attribute, old, new, kwargs) -> None:
    """Log change of current price.

    Args:
        hass: The Home Assistant instance.
        entity: The entity that changed.
        attribute: The attribute that changed.
        old: The old value of the attribute.
        new: The new value of the attribute.
        kwargs: Additional keyword arguments.
    """
    # Convert old and new price to float with 5 decimal places
    try:
        old = float(f"{float(old):.5f}")
        new = float(f"{float(new):.5f}")
    except (ValueError, TypeError):
        pass
    _p: list[float] = [new]
    # calculate the total nett price
    haas.now_price = total_price(pricelist=_p)[0]
    haas.log(f"Current price changed: {old} -> {new} = {haas.now_price}")


def lst_changed(haas, entity, attribute, old, new, kwargs) -> None:
    """Handle changes in the energy prices.

    Args:
        hass: The Home Assistant instance.
        entity: The entity that changed.
        attribute: The attribute that changed.
        old: The old value of the attribute.
        new: The new value of the attribute.
        kwargs: Additional keyword arguments.
    """
    haas.log(f"Prices changed: {old} -> {new}")
    # Update today's and tomorrow's prices
    today = dt.date.today()
    tomorrow = today + dt.timedelta(days=1)
    haas.todays_prices = convert_prices(haas, today)
    haas.tomorrows_prices = convert_prices(haas, tomorrow)


def convert_prices(haas, datum) -> list[float]:
    """Get the energy prices for a specific date.

    Args:
        hass: The Home Assistant instance.
        datum: The date for which to get the prices.

    Returns:
        list[float]: A list of prices for the specified date, adjusted for storage and taxes.
    """
    no_prices: list[float] = [0.0] * 24
    _p: list[float] = no_prices
    if isinstance(datum, dt.date):
        date_str: str = datum.strftime("%Y-%m-%d")
        attr: dict = haas.get_state(entity_id=cs.ENT_PRICE, attribute=cs.LST_PRICE_ATTR)
        _p = attr.get(date_str, no_prices)
    else:
        haas.log(f"Invalid date: {datum}", level="ERROR")
    return total_price(pricelist=_p)


def total_price(pricelist: list[float]) -> list[float]:
    """Convert a given list of raw prices.

    Args:
        pricelist: A list of raw prices (in Euro).

    Returns:
        list[float]: A list of total prices (in Euro) adjusted for storage, extra costs, and taxes.
    """
    _p = [i * 100 for i in pricelist]
    # add opslag=0.021 + extra=2.000 + taxes=10.15 = 12.171
    _p = [i + (0.021 + 2.0 + 10.15) for i in _p]
    # add BTW = 21%
    _p = [round(i * 1.21, 5) for i in _p]
    return _p
