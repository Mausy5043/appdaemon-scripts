"""Fetch price info from Tibber API instead of from HA."""


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

    def get_pricelist(self) -> list:
        """Get the price list from the API."""
        now_data: dict = {}
        data: list = [{"error": "no data returned"}]
        payload: dict = {"query": self.qry_now}
        now_data = post_request(self.api_url, self.headers_post, payload)
        if "error" in now_data:
            return [now_data]
        resp_data: list = unpeel(now_data, "today")
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


def unpeel(_data: dict[str, dict], _key: str) -> list:
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

    return _lkey


def convert(_data: list[dict]) -> list:
    _ret = []
    for item in _data:
        try:
            sample_time = parser.isoparse(item["startsAt"])
            price = float(item["total"]) * 100
            _ret.append(
                {
                    "sample_time": sample_time,     # datetime object
                    "price": price,                 # float cEUR/kWh
                }
            )
        except (KeyError, ValueError, TypeError) as her:
            _ret.append(
                {
                    "error": f"Error processing item: {item}, error: {her}",
                }
            )
    return _ret


def get_pricelist(token: str, url: str):
    """Get the price list from the API."""
    price_getter = Tibber(token, url)
    _a = price_getter.get_pricelist()
    return _a
