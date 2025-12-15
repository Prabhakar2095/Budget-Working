import requests
import json

# Test payload for Small Cell
payload = {
    "lob": "SMALL CELL",
    "fiscal_year": "FY25-26",
    "volumes": [
        {
            "dimensions": {"customer": "TestCust", "siteType": "HPSC", "type": "RFAI"},
            "volumes": {"FY25-26": {"Apr": 0, "May": 0, "Jun": 100000, "Jul": 0, "Aug": 0, "Sep": 0, "Oct": 0, "Nov": 0, "Dec": 0, "Jan": 0, "Feb": 0, "Mar": 0}},
            "exit_volumes": {},
            "fresh_offset_months": 0,
            "recurring_offset_months": 2,
            "one_time_offset_months": 2,
            "cashflow_recurring_offset_months": 2,
            "cashflow_one_time_offset_months": 2,
            "capex_cashflow_offset_months": 0,
            "included": True
        }
    ],
    "rates": [
        {
            "dimensions": {"customer": "TestCust", "siteType": "HPSC", "type": "RFAI"},
            "recurring_rate": 100.0,
            "one_time_rate": 0.0,
            "existing_recurring_rate": 0.0,
            "existing_one_time_rate": 0.0,
            "one_time_month": None
        }
    ],
    "include_fresh_volumes": True,
    "base_exit_year": None,
    "formula_recurring": None,
    "formula_one_time": None,
    "opex_items": [],
    "opex_rates": [],
    "capex_items": [],
    "capex_rates": []
}

try:
    resp = requests.post("http://localhost:8000/api/revenue/calculate", json=payload)
    print(f"Status: {resp.status_code}")
    if resp.ok:
        print("Success!")
        result = resp.json()
        print(f"\nResponse keys: {list(result.keys())}")
        print(f"\nFull response:")
        print(json.dumps(result, indent=2)[:2000])
    else:
        print(f"Error: {resp.text}")
except Exception as e:
    print(f"Exception: {e}")


