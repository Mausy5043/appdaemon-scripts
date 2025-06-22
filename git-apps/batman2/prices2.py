"""Fetch price info from Tibber API instead of from HA."""

import configparser
import json
import os
import sys

import const2 as cs
import requests

requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]




def req_post(
    _url: str,
    _headers: dict[str, str],
    _payload: dict[str, str],
) -> dict:
    """Make a POST request to the given URL with the specified headers and payload."""
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
        print(f"An error occurred: {her}")
        return {}


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


def main() -> None:
    # Read the API key and URL from the INI file
    config_file = cs.PRICES["config"]
    config = configparser.ConfigParser()
    try:
        # Reading the INI config file
        with open(config_file) as file:
            config.read_file(file)
        api_key: str = config.get("API", "key", fallback="")
        api_url: str = config.get("API", "url", fallback="")
        savefile: str = os.path.expanduser(config.get("API", "saveto"))
        qry_now: str = config.get("API", "qry_now", fallback="")
        qry_nxt: str = config.get("API", "qry_nxt", fallback="")
        if not api_key or not api_url:
            print("API key or URL missing in the configuration.")
            sys.exit(1)
    except FileNotFoundError:
        print(f"Config file not found: {config_file}")
        sys.exit(1)
    except configparser.Error as her:
        print(f"Error processing config file: {her}")
        sys.exit(1)

    headers_post: dict = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    # Get the today's data from the API
    now_data: dict = {}
    payload: dict = {"query": qry_now}
    try:
        now_data = req_post(
            api_url,
            headers_post,
            payload,
        )
    except Exception as her:
        print(f"Error fetching today's data: {her}")
        pass
    if OPTION.debug:
        print(json.dumps(now_data, indent=1))

    # Get the tomorrow's data from the API
    nxt_data: dict = {}
    payload = {"query": qry_nxt}
    try:
        nxt_data = req_post(
            api_url,
            headers_post,
            payload,
        )
    except KeyError as her:
        print(f"Error fetching tomorrow's data: {her}")
        pass
    if OPTION.debug:
        print(json.dumps(nxt_data, indent=1))

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
    with open(savefile, "w", encoding="utf-8") as _f:
        json.dump(data, _f, ensure_ascii=True, indent=4)
    # print(json.dumps(data, indent=4))

def get_pricelist(token: str, url: str):
    """Get the price list from the API."""
    return "pricelist v2 not implemented yet"
