"""Fetch price info from Tibber API instead of from HA."""

import datetime as dt
from statistics import quantiles as stqu
from typing import Any

import const3 as cs
import requests
import utils3 as ut
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
        self.prices: dict[str, float] = {}
        self.pricelist: list[float] = []
        # set a default price until we get the actual
        self.price_now: float = cs.PRICES["adjust"]["extra"] + cs.PRICES["adjust"]["taxes"]
        self.quarter_now: int = 0
        self.stats: dict[str, Any] = {}
        self.statstext: str = "statistics unavailable"

        # self.charge: list[int] = []
        # self.discharge: list[int] = []
        self.update_prices()

    def _fetch_pricedict(self) -> dict[str, float]:
        """Get the price list from the API."""
        now_data: dict = {}
        data: dict = {"error": "no data returned"}
        payload: dict = {"query": self.qry_now}
        now_data = self._post_request(payload)
        resp_data: list[dict] = self._unpeel(_data=now_data, _key="today")
        data = self._convert(resp_data)
        return data

    def _post_request(self, _payload: dict[str, str]) -> dict:
        """Make a POST request to the given URL with the specified headers and payload.

        Args:
            _payload (dict): the query to be used

        Returns:
            dict: contains the query results
        """
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers_post,
                json=_payload,
                timeout=30.0,
                verify=False,  # nosec B501
            )
            response.raise_for_status()  # Raise an exception for HTTP errors
            return dict(response.json())
        except requests.exceptions.RequestException as her:
            return {"error": f"An error occurred: {her}"}

    @staticmethod
    def _unpeel(_data: dict[str, dict], _key: str) -> list[dict]:
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

    @staticmethod
    def _convert(_data: list[dict]) -> dict[str, float]:
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
        #  }
        # fmt: on
        return dict(sorted(_ret.items()))

    def update_prices(self) -> None:
        self.prices = self._fetch_pricedict()  # get the prices from the API
        self.pricelist = list(self.prices.values())  # convert the prices to a list
        self.price_statistics()
        # TODO: lists
        # self.charge_greed = "indices of prices < LL or 0.0 (?)"
        # self.charge_q1 = "indices of prices < q1"
        # self.discharge_q3 = "indices of prices > q3"
        # self.discharge_greed = "indices of prices > (Q1avg + HH) or (?)"
        self.update_current_price()

    def update_current_price(self) -> None:
        self.update_current_quarter()  # make sure we are looking at the correct quarter
        self.price_now = self.get_price_qrter(self.quarter_now)

    def update_current_quarter(self):
        self.quarter_now = ut.calculate_quarter(dt.datetime.now())

    def get_price_hm(self, hour: int, min: int) -> float:
        """Return the price for a given hour and minute."""
        # Round the minutes to the nearest 15 minutes to get the quarter
        _qrtr: int = int(round(min / 15) * 15)
        return self.get_price_qrter(_qrtr)

    def get_price_qrter(self, quarter: int) -> float:
        # for _dt, _price in self.prices.items():
        #     sample_time: dt.datetime = parser.isoparse(_dt)
        #     if sample_time.hour == hour and sample_time.minute == _qrtr:
        #         break
        _price: float = self.pricelist[quarter]
        return _price

    def price_statistics(self) -> None:
        """Calculate price statistics."""

        def sum_values_at_index(idx: list[int], val: list[float]) -> float:
            return sum(val[i] for i in idx)

        Q = stqu(self.pricelist, n=4, method="inclusive")
        self.stats = {
            "min": round(min(self.pricelist), 3),
            "q1": round(Q[0], 3),
            "med": round(Q[1], 3),
            "avg": round(sum(self.pricelist) / len(self.pricelist), 3),
            "q3": round(Q[2], 3),
            "max": round(max(self.pricelist), 3),
            "rng": round(max(self.pricelist) - min(self.pricelist), 3),
            "iqr": round(Q[2] - Q[0], 3),
            "Q1": {},
            "Q2": {},
            "Q3": {},
            "Q4": {},
        }

        # build a list of indices; lowest to highest price
        sorted_indices = ut.sort_index(self.pricelist, rev=False)
        # __si = sorted_indices  # remember this list

        # build a list of the slots that are in Q1 (in the interval min...q1)
        Q1 = [idx for idx in sorted_indices if self.pricelist[idx] < Q[0]]
        # remove the indices in Q1 to avoid adding them to the next list
        sorted_indices = sorted_indices[len(Q1) :]
        self.stats["Q1"] = {
            "idx": Q1,
            "avg": sum_values_at_index(Q1, self.pricelist) / len(Q1),
            "n": len(Q1),
        }

        # build a list of the slots that are in Q2 (in the interval q1...median)
        Q2 = [idx for idx in sorted_indices if self.pricelist[idx] < Q[1]]
        sorted_indices = sorted_indices[len(Q2) :]
        self.stats["Q2"] = {
            "idx": Q2,
            "avg": sum_values_at_index(Q2, self.pricelist) / len(Q2),
            "n": len(Q2),
        }

        # build a list of the slots that are in Q3 (in the interval median...q3)
        Q3 = [idx for idx in sorted_indices if self.pricelist[idx] < Q[2]]
        sorted_indices = sorted_indices[len(Q3) :]
        self.stats["Q3"] = {
            "idx": Q3,
            "avg": sum_values_at_index(Q3, self.pricelist) / len(Q3),
            "n": len(Q3),
        }

        Q4 = sorted_indices
        self.stats["Q4"] = {
            "idx": Q4,
            "avg": sum_values_at_index(Q4, self.pricelist) / len(Q4),
            "n": len(Q4),
        }

        self.statstext = (
            f" : min: {self.stats['min']:.3f}, "
            f"q1 : {self.stats['q1']:.3f}, "
            f"med: {self.stats['med']:.3f}, "
            f"avg: {self.stats['avg']:.3f}, "
            f"q3 : {self.stats['q3']:.3f}, "
            f"max: {self.stats['max']:.3f}, "
            f"rng: {self.stats['rng']:.3f}, "
            f"iqr: {self.stats['iqr']:.3f}\n"
            f" :      Q1 avg: {self.stats['Q1']['avg']:.3f}, "
            f"Q2 avg: {self.stats['Q2']['avg']:.3f}, "
            f"Q3 avg: {self.stats['Q3']['avg']:.3f}, "
            f"Q4 avg: {self.stats['Q4']['avg']:.3f} "
        )
