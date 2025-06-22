"""Fetch price info from Tibber API instead of from HA."""

from statistics import quantiles as stqu

import const2 as cs
import requests
from dateutil import parser

requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]


class Tibber:
    """Class to interact with the Tibber API."""

    def __init__(self, token: str, url: str) -> None:
        """Initialize the Tibber class with the API token and URL."""
        self.api_key = token
        self.api_url = url
        self.qry_now: str = cs.PRICES["qry_now"]
        self.qry_nxt: str = cs.PRICES["qry_nxt"]
        self.headers_post: dict = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def get_pricedict(self) -> dict[str, float]:
        """Get the price list from the API."""
        now_data: dict = {}
        data: dict = {"error": "no data returned"}
        payload: dict = {"query": self.qry_now}
        now_data = post_request(self.api_url, self.headers_post, payload)
        resp_data: list[dict] = unpeel(now_data, "today")
        data = convert(resp_data)
        return data


def post_request(_url: str, _headers: dict[str, str], _payload: dict[str, str]) -> dict:
    """Make a POST request to the given URL with the specified headers and payload.

    Args:
        _url (str): URL to call
        _headers (dict): headers to be used
        _payload (dict): the query to be used

    Returns:
        dict: contains the query results

    """
    try:
        response = requests.post(
            _url,
            headers=_headers,
            json=_payload,
            timeout=30.0,
            verify=False,  # nosec B501
        )
        response.raise_for_status()  # Raise an exception for HTTP errors
        return dict(response.json())
    except requests.exceptions.RequestException as her:
        return {"error": f"An error occurred: {her}"}


def unpeel(_data: dict[str, dict], _key: str) -> list[dict]:
    """Unpeel the data from the given key."""
    _lkey: list = []
    try:
        _ldata: dict = _data["data"]
        _lviewer: dict = _ldata["viewer"]
        _lhomes: list = _lviewer["homes"]
        _lhome: dict = _lhomes[0]
        _lcurSub: dict = _lhome["currentSubscription"]
        _lpriceInfo: dict = _lcurSub["priceInfo"]
        _lkey = _lpriceInfo[_key]
    except KeyError:
        pass
    # fmt: off
    # _lkey is a list of dicts with the following structure:
    # [{'total': 0.277, 'energy': 0.1069, 'tax': 0.1701, 'startsAt': '2025-06-22T00:00:00.000+02:00'},
    #  {'total': 0.27, 'energy': 0.1011, 'tax': 0.1689, 'startsAt': '2025-06-22T01:00:00.000+02:00'},
    #  {'total': 0.2675, 'energy': 0.099, 'tax': 0.1685, 'startsAt': '2025-06-22T02:00:00.000+02:00'},
    #  {'total': 0.2573, 'energy': 0.0906, 'tax': 0.1667, 'startsAt': '2025-06-22T03:00:00.000+02:00'},
    # fmt: on
    return _lkey


def convert(_data: list[dict]) -> dict[str, float]:
    _ret: dict[str, float] = {}
    for item in _data:
        sample_time = parser.isoparse(item["startsAt"]).strftime("%Y-%m-%d %H:%M:%S")
        price = float(item["total"]) * 100  # float cEUR/kWh
        _ret[sample_time] = price

    # fmt: off
    # _ret is a dict with the following structure:
    # {'2025-06-22 00:00:00': 27.700000000000003,
    #  '2025-06-22 01:00:00': 27.0,
    #  '2025-06-22 02:00:00': 26.75,
    #  '2025-06-22 03:00:00': 25.729999999999997,
    # fmt: on
    return dict(sorted(_ret.items()))


def get_pricedict(token: str, url: str) -> dict[str, float]:
    """Get the price list from the API."""
    price_getter = Tibber(token, url)
    _a = price_getter.get_pricedict()
    return _a


def get_price(price_dict: dict[str, float], hour: int, min: int) -> float:
    _price: float = 0.0
    # Round the quarter to the nearest 15 minutes
    _qrtr: int = int(round(min / 15) * 15)
    for _k, _v in price_dict.items():
        item = {"sample_time": parser.isoparse(_k), "price": _v}
        if item["sample_time"].hour == hour and item["sample_time"].minute == _qrtr:
            _price = item["price"]
            break
    return _price


def total_price(pricelist: dict[str, float]) -> list[float]:
    """Convert a given list of raw Tibber prices.
    Note: the output of the convert() method is expected as input
          we expect the dict to be sorted by sample_time.
    """
    # Euro to cents conversion
    _p: list[float] = list(pricelist.values())
    return _p


def price_statistics(prices: list) -> dict:
    """Calculate and return price statistics."""
    price_stats = {
        "min": round(min(prices), 3),
        "q1": round(stqu(prices, n=4, method="inclusive")[0], 3),
        "med": round(stqu(prices, n=4, method="inclusive")[1], 3),
        "avg": round(sum(prices) / len(prices), 3),
        "q3": round(stqu(prices, n=4, method="inclusive")[2], 3),
        "max": round(max(prices), 3),
        "text": "",
    }
    price_stats["text"] = (
        f"Min: {price_stats.get('min', 'N/A'):.3f}, "
        f"Q1 : {price_stats.get('q1', 'N/A'):.3f}, "
        f"Med: {price_stats.get('med', 'N/A'):.3f}, "
        f"Avg: {price_stats.get('avg', 'N/A'):.3f}, "
        f"Q3 : {price_stats.get('q3', 'N/A'):.3f}, "
        f"Max: {price_stats.get('max', 'N/A'):.3f}"
    )
    return price_stats
