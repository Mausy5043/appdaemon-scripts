"""Fetch price info from Tibber API instead of from HA."""

import configparser
import json
import os
import sys

import const2 as cs
import requests

requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]



def unpeel(
    _data: dict[str, dict],
    _key: str,
) -> list:
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

class Tibber:
    """Class to interact with the Tibber API."""

    def __init__(self, token: str, url: str) -> None:
        """Initialize the Tibber class with the API token and URL."""
        self.api_key = token
        self.api_url = url
        self.qry_now: str = cs.PRICES["qry_now"]
        self.qry_nxt: str = cs.PRICES["qry_nxt"]
        self.headers_post: dict = {"Content-Type": "application/json",
                                   "Authorization":
                                   f"Bearer {self.api_key}"
                                   }


    def get_pricelist(self) -> str:     # -> dict:
        """Get the price list from the API."""
        now_data: dict = {}
        payload: dict = {"query": self.qry_now}
        now_data = post_request(self.api_url, self.headers_post, payload)
        return json.dumps(now_data, indent=1)


def post_request(
    _url: str,
    _headers: dict[str, str],
    _payload: dict[str, str],
) -> dict:
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


def deprecated() -> None:



    # Get the tomorrow's data from the API
    nxt_data: dict = {}
    # qrt
    # payload = {"query": qry_nxt}
    # try:
    #     nxt_data = req_post(
    #         api_url,
    #         headers_post,
    #         payload,
    #     )
    # except KeyError as her:
    #     print(f"Error fetching tomorrow's data: {her}")
    #     pass
    print(json.dumps(nxt_data, indent=1))
    now_data={}
    resp_data: list = unpeel(now_data, "today") + unpeel(nxt_data, "tomorrow")
    # Convert the data for the database
    data: list = []
    site_id: str = cs.PRICES["template"]["site_id"]
    for item in resp_data:
        try:
            sample_time = item["startsAt"].split(".")[0].replace("T", " ")
            price = float(item["total"])
            sample_epoch = int(pd.Timestamp(sample_time).timestamp())
            data.append(
                {
                    "sample_time": sample_time,
                    "sample_epoch": sample_epoch,
                    "site_id": site_id,
                    "price": price,
                }
            )
        except (KeyError, ValueError, TypeError) as her:
            print(f"Error processing item: {item}, error: {her}")

    # Save the data to a JSON file
    savefile=""
    with open(savefile, "w", encoding="utf-8") as _f:
        json.dump(data, _f, ensure_ascii=True, indent=4)
    # print(json.dumps(data, indent=4))


def get_pricelist(token: str, url: str):
    """Get the price list from the API."""
    price_getter = Tibber(token, url)
    _a = price_getter.get_pricelist()
    return _a
