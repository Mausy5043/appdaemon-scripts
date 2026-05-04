# Control
This document describes the control by the EMS *batman3* and supporting controls by *Home Assistant* automations.

## Home Assistant
Entities under *Home Assistant* are always active and cannot (easily) and should not be disabled.

<details>
<summary>
Batteries
</summary>

`bat1_full` is used to detect a full battery
* When the SoC is above 99.9 % for more than 45 minutes:
* `input_boolean.bat1_lohi` is switched ON 

`calc_bat1_RTE` is used to calculate the battery's RTE.
* When SoC is at 0% for 45 minutes
* AND `bat1_lohi` is ON:
* `input_boolean.bat1_lohi` is switched OFF
* `input_number.bat1_rte_value` is set to a new value

*(same for `bat2*`)*

`AboveMinSoC`
* When `sensor.bats_avg_soc` > `sensor.bats_minimum_soc`:
* `input_boolean.bats_min_soc` is switched OFF

`BelowMinSoC`
* When `sensor.bats_avg_soc` < `sensor.bats_minimum_soc`:
* `input_boolean.bats_min_soc` is switched ON

</details>

<details>
<summary>
PV  
</summary>

`PV_OverCurrent_ON` / `PV_OverCurrent_OFF`
* Detects if `sensor.pv_kwh_meter_current` comes above 24.1 A (ON) or below 23.9 A (OFF).

</details>

<details>
<summary>
EV   
</summary>

`EVneedsPWR_OFF`
* When `sensor.ev_kwh_meter_power` is below 660 W for 1 minute;
* `input_boolean.evneedspwr` is switched OFF

`EVneedsPWR_ON`
* When `sensor.ev_kwh_meter_power` is above 880 W;
* `input_boolean.evneedspwr` is switched ON immediately

</details>

---

## BatMan3

If `input_boolean.bat_ctrl_app` is OFF, nothing is done. 

When `EVneedsPWR` turns OFF, the batteries are put in NOM state.
When `EVneedsPWR` turns ON, the batteries are put in IDLE state. This can be overruled by greed.

These modes are defined:

- (I) Idle : batteries are idle
- (X) XOM : P1 SP 
- (0) NOM : XOM w/ P1 SP = 0 W

0. update prices/current price
1. (q,w) update states
2. control states XOM/stance
3. log

quarter_started_cb
    fail: exception_cb

watchdog_cb
    watchdog_runin_cb || lowpv_runin_cb

```(yaml)
debug:
    type: bool
    description: 
bat_ctrl:
    type: dict
    description: hold battery objects
    contents:
        "bat1":
            type: dict
            contents:
                "url":
                    type: str
                    description: URL to the battery API
                "username":
                    type: str
                "password":
                    type: str
                "api":
                    type: battalk3.Sessy()
                    contents:
                        session:
                            type: requests.Session()
                        bat_ip:
                            type: str
                            contents: IP/URL of the device
                        api_call:
                            type: dict[str, str]
                            contents: supported API calls
                        strat:
                            type: dict[str, str]
                            contents: supported API strategies
                        headers:
                            type: dict[str, str]
                            contents: headers for use by requests
                        status:
                            type: dict[str, str]
                            contents: current status of the device from the API
                        strategy:
                            type: str
                            contents: currently active battery strategy
                        type:
                            type: str
                            contents: "bat" or "p1"
                "strategy"
                    type: str
                    contents: "UNK", "nom" or "idl"
        "bat2":
            type: dict
            contents: see bat1
p1_ctrl:
    type: dict
    description: hold CT objects
    contents: 
        "p1": 
            type: dict
            contents: see bat_ctrl.bat1
                "state":
                    type: str
                    contents: 
                            
                
```
