# OPEX item model for validation
from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import json
frontend_dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/dist'))

app = FastAPI(title="Fresh Budget API", version="0.1.0")

# --- Simple SQLite-backed storage for LOB snapshots ---
import sqlite3
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), 'lob_store.db')

def _ensure_db():
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS lob_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lob TEXT NOT NULL,
            fiscal_year TEXT,
            data TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(lob, fiscal_year)
        )
        ''')
        conn.commit()
    finally:
        conn.close()

_ensure_db()

def save_lob_snapshot(lob: str, fiscal_year: str | None, data_json: str):
    conn = sqlite3.connect(DB_FILE)
    try:
        now = datetime.utcnow().isoformat()
        # Upsert by lob + fiscal_year
        cur = conn.cursor()
        cur.execute('SELECT id FROM lob_snapshots WHERE lob=? AND fiscal_year IS ?', (lob, fiscal_year))
        row = cur.fetchone()
        if row:
            cur.execute('UPDATE lob_snapshots SET data=?, updated_at=? WHERE id=?', (data_json, now, row[0]))
        else:
            cur.execute('INSERT INTO lob_snapshots (lob,fiscal_year,data,updated_at) VALUES (?,?,?,?)', (lob, fiscal_year, data_json, now))
        conn.commit()
    finally:
        conn.close()

def load_lob_snapshot(lob: str, fiscal_year: str | None = None):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        if fiscal_year:
            cur.execute('SELECT data, updated_at FROM lob_snapshots WHERE lob=? AND fiscal_year IS ?', (lob, fiscal_year))
            row = cur.fetchone()
            if not row:
                return None
            return {'data': row['data'], 'updated_at': row['updated_at']}
        else:
            # return latest snapshot for lob (by updated_at)
            cur.execute('SELECT data, updated_at FROM lob_snapshots WHERE lob=? ORDER BY updated_at DESC LIMIT 1', (lob,))
            row = cur.fetchone()
            if not row:
                return None
            return {'data': row['data'], 'updated_at': row['updated_at']}
    finally:
        conn.close()

@app.post('/api/lob/save')
async def api_save_lob(payload: dict = Body(...)):
    """Save a LOB snapshot. Expects JSON: { lob: string, fiscal_year?: string, data: object }"""
    lob = payload.get('lob')
    fy = payload.get('fiscal_year')
    data = payload.get('data')
    # Support legacy frontend shape where snapshot fields are spread at top-level
    if data is None:
        # Build data by removing lob and fiscal_year keys
        data = {k: v for k, v in payload.items() if k not in ('lob', 'fiscal_year')}
    if not lob or data is None:
        raise HTTPException(status_code=400, detail='lob and data are required')
    try:
        data_json = json.dumps(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Failed to serialize data: {e}')
    save_lob_snapshot(lob, fy, data_json)
    return {'message': 'saved', 'lob': lob, 'fiscal_year': fy}

@app.get('/api/lob/get/{lob_name}')
async def api_load_lob(lob_name: str, fiscal_year: str | None = None):
    """Load a saved LOB snapshot. Optional query param fiscal_year."""
    res = load_lob_snapshot(lob_name, fiscal_year)
    if not res:
        raise HTTPException(status_code=404, detail='Not found')
    try:
        data_obj = json.loads(res['data'])
    except Exception:
        data_obj = res['data']
    return {'data': data_obj, 'updated_at': res['updated_at']}


class OpexItem(BaseModel):
    name: str
    group: str = "Opex"
    type: str = "opex"
    recognition_offset_months: int = 0
    cashflow_offset_months: int = 0

opex_items = [
    {"name": "Rent", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Electricity", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "People Cost", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Network O&M", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Warehouse Rental", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Operational Others", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Travelling & Sales Promotions", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Freight Internal & other direct", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Insurance", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Passthrough Expense", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Loss on Sale of Scrap", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Software & IT", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
]
opex_items_store = opex_items.copy()

@app.get("/api/opex/working")
async def get_opex_working():
    """Return all OPEX items for reference/modeling."""
    return {"items": opex_items_store}

@app.post("/api/opex/add")
async def add_opex_item(item: OpexItem):
    # Check for duplicate by name
    for existing in opex_items_store:
        if existing["name"].lower() == item.name.lower():
            return {"error": "Opex item with this name already exists."}
    opex_items_store.append(item.dict())
    return {"message": "Opex item added.", "item": item.dict()}

@app.put("/api/opex/update/{name}")
async def update_opex_item(name: str, item: OpexItem):
    for idx, existing in enumerate(opex_items_store):
        if existing["name"].lower() == name.lower():
            opex_items_store[idx] = item.dict()
            return {"message": "Opex item updated.", "item": item.dict()}
    return {"error": "Opex item not found."}

capex_items = [
    # First Time Inventory
    {"name": "Battery, SMPS & Cabinet - First Time", "group": "First Time Inventory", "type": "first_time", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "Pole - First Time", "group": "First Time Inventory", "type": "first_time", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "Fiber - First Time", "group": "First Time Inventory", "type": "first_time", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "Antenna - First Time", "group": "First Time Inventory", "type": "first_time", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "Others - First Time", "group": "First Time Inventory", "type": "first_time", "cashflow_offset_months": 0, "is_refund": False},
    # First Time Capex
    {"name": "Acquisition - First Time", "group": "First Time Capex", "type": "first_time", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "IBD - First Time", "group": "First Time Capex", "type": "first_time", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "MC & EB Permission - First Time", "group": "First Time Capex", "type": "first_time", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "Other Services - First Time", "group": "First Time Capex", "type": "first_time", "cashflow_offset_months": 0, "is_refund": False},
    # Capex People
    {"name": "Capex People", "group": "Capex People", "type": "people", "cashflow_offset_months": 0, "is_refund": False},
    # Replacement Inventory
    {"name": "Battery, SMPS & Cabinet - Replacement", "group": "Replacement Inventory", "type": "replacement", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "Pole - Replacement", "group": "Replacement Inventory", "type": "replacement", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "Fiber - Replacement", "group": "Replacement Inventory", "type": "replacement", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "Antenna - Replacement", "group": "Replacement Inventory", "type": "replacement", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "Others - Replacement", "group": "Replacement Inventory", "type": "replacement", "cashflow_offset_months": 0, "is_refund": False},
    # Replacement Capex
    {"name": "Acquisition - Replacement", "group": "Replacement Capex", "type": "replacement", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "IBD - Replacement", "group": "Replacement Capex", "type": "replacement", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "MC & EB Permission - Replacement", "group": "Replacement Capex", "type": "replacement", "cashflow_offset_months": 0, "is_refund": False},
    {"name": "Other Services - Replacement", "group": "Replacement Capex", "type": "replacement", "cashflow_offset_months": 0, "is_refund": False},
    # ROW Deposit
    {"name": "ROW Deposit", "group": "ROW Deposit", "type": "deposit", "cashflow_offset_months": 0, "is_refund": False},
    # Deposit Refund
    {"name": "Deposit Refund", "group": "Deposit Refund", "type": "deposit_refund", "cashflow_offset_months": 0, "is_refund": True},
]
# ------------------ CAPEX Working Endpoint ------------------
# Returns all CAPEX items for reference/modeling (like Opex working)

 # OPEX items reference list (for /api/opex/working)
opex_items = [
    {"name": "Rent", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Electricity", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "People Cost", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Network O&M", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Warehouse Rental", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Operational Others", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Travelling & Sales Promotions", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Freight Internal & other direct", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Insurance", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Passthrough Expense", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Loss on Sale of Scrap", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
    {"name": "Software & IT", "group": "Opex", "type": "opex", "recognition_offset_months": 0, "cashflow_offset_months": 0},
]

 # ------------------ OPEX Working Endpoint ------------------
 # Returns all OPEX items for reference/modeling
from fastapi import Body
@app.get("/api/opex/working")
async def get_opex_working():
    """Return all OPEX items for reference/modeling."""
    return {"items": opex_items}
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import ast, math
import io, csv

try:
    import pandas as pd  # type: ignore
except Exception:  # pandas optional
    pd = None  # fallback

class RevenueRow(BaseModel):
    dimensions: Dict[str, str]
    monthly_revenue: Dict[str, float]
    monthly_recurring: Dict[str, float] = Field(default_factory=dict)
    monthly_one_time: Dict[str, float] = Field(default_factory=dict)
    # Added breakdown so cashflow can exclude existing one-time component
    monthly_existing_one_time: Dict[str, float] = Field(default_factory=dict)
    monthly_fresh_one_time: Dict[str, float] = Field(default_factory=dict)
    # Cashflow components: recurring (existing + fresh after offset) and one-time (fresh only, no existing)
    monthly_cashflow_recurring: Dict[str, float] = Field(default_factory=dict)
    monthly_cashflow_one_time: Dict[str, float] = Field(default_factory=dict)
    total_recurring: float
    total_one_time: float
    total_revenue: float
    existing_recurring: float = 0.0
    fresh_recurring: float = 0.0
    existing_one_time: float = 0.0
    fresh_one_time: float = 0.0


class RevenueCalcResponse(BaseModel):
    fiscal_year: str
    months: List[str]
    rows: List[RevenueRow]
    monthly_totals: Dict[str, float]
    monthly_recurring_totals: Dict[str, float]
    monthly_one_time_totals: Dict[str, float]
    # Passthrough P&L (e.g., Small Cell rent/electricity passthrough)
    monthly_passthrough_revenue: Dict[str, float] = Field(default_factory=dict)
    monthly_passthrough_expense: Dict[str, float] = Field(default_factory=dict)
    total_revenue: float
    total_passthrough_revenue: float = 0.0
    total_passthrough_expense: float = 0.0
    # Opex outputs
    opex_items: List[Dict[str, Any]] = Field(default_factory=list, description="Per opex item monthly + total")
    monthly_opex_totals: Dict[str, float] = Field(default_factory=dict)
    total_opex: float = 0.0
    # Cashflow outputs (shifted by per-combination cashflow_offset_months)
    monthly_cash_recurring_inflow: Dict[str, float] = Field(default_factory=dict)
    monthly_cash_one_time_inflow: Dict[str, float] = Field(default_factory=dict)
    monthly_cash_passthrough_inflow: Dict[str, float] = Field(default_factory=dict)
    monthly_cash_gross_inflow: Dict[str, float] = Field(default_factory=dict)
    monthly_cash_outflow_items: List[Dict[str, Any]] = Field(default_factory=list, description="Per opex item cash outflow after offsets")
    monthly_cash_outflow_totals: Dict[str, float] = Field(default_factory=dict)
    monthly_cash_net_operating: Dict[str, float] = Field(default_factory=dict)
    total_cash_recurring_inflow: float = 0.0
    total_cash_one_time_inflow: float = 0.0
    total_cash_gross_inflow: float = 0.0
    total_cash_outflow: float = 0.0
    total_cash_net_operating: float = 0.0
    # CAPEX outputs & extended cashflow
    capex_items: List[Dict[str, Any]] = Field(default_factory=list, description="Per CAPEX item (recognized amounts before cash shift)")
    monthly_capex_totals: Dict[str, float] = Field(default_factory=dict, description="Net CAPEX (outflow minus refunds) per month after cash timing shifts")
    total_capex: float = 0.0
    monthly_net_cashflow: Dict[str, float] = Field(default_factory=dict, description="Net Operating Flow - CAPEX")
    monthly_cum_net_cashflow: Dict[str, float] = Field(default_factory=dict)
    peak_funding: float = 0.0
    total_net_cashflow: float = 0.0

def _dim_key(dimensions: Dict[str,str]) -> str:
    return '|'.join(f"{k}={dimensions[k]}" for k in sorted(dimensions.keys()))


def _get_site_type(dimensions: Dict[str, Any] | None) -> str:
    """Return normalized site type from dimensions (case-insensitive key lookup)."""
    if not dimensions:
        return ""
    for k, v in dimensions.items():
        key_norm = str(k).replace('_', ' ').replace('-', ' ').strip().lower()
        if key_norm == 'site type':
            return str(v or '')
    return ""

# Ensure app is always defined at the top level (single instance created earlier)

origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    # Added Vite dev server (current project) origins
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# During local development it's convenient to allow all origins to avoid
# intermittent CORS failures caused by origin variations between localhost
# and 127.0.0.1. For production builds restrict this to known origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # development-only: allow any origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/api/debug')
async def debug(request: Request):
    """Return request headers and origin info to help debug cross-origin fetches."""
    hdrs = {k: v for k, v in request.headers.items()}
    return {"headers": hdrs}

FISCAL_MONTHS = ["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"]

class BudgetCalcRequest(BaseModel):
    method: str = "Volume × Rate"
    months_to_skip: int = 0
    volumes: List[Dict[str, Any]] = []
    rates: List[Dict[str, Any]] = []

class VolumePayload(BaseModel):
    volume: Dict[str, float] = Field(default_factory=dict, description="Monthly volume keyed by fiscal month abbreviation (Apr..Mar)")

class VolumeResponse(BaseModel):
    months: List[str]
    volume: List[float]
    cumulative: List[float]
    total_volume: float

class VolumeCombination(BaseModel):
    """Legacy fixed-dimension combination (kept for backward compatibility)."""
    cost_center: str
    uom: str = "HP Count"
    site_type: str
    customer: str
    volumes: Dict[str, Dict[str, float]] = Field(default_factory=dict, description="Map of fiscal year -> month -> volume (only current FY expected)")
    exit_volumes: Dict[str, float] = Field(default_factory=dict, description="Map of prior fiscal year -> cumulative exit volume")

class MultiYearVolumePayload(BaseModel):
    fiscal_year: str  # e.g. FY24-25 (current planning year)
    prior_years: List[str] = []  # e.g. [FY23-24, FY22-23]
    combinations: List[VolumeCombination] = []

class MultiYearVolumeResponse(BaseModel):
    fiscal_year: str
    months: List[str]
    rows: List[Dict[str, Any]]  # each row with combination + monthly + total
    totals: Dict[str, float]    # monthly aggregated totals for current FY
    grand_total: float

# ------------------ Dynamic Dimension Models ------------------
class DynamicVolumeCombination(BaseModel):
    """Dynamic dimension combination: dimensions is a mapping (e.g. customer,circle,type,extra...)."""
    dimensions: Dict[str, str]
    volumes: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    exit_volumes: Dict[str, float] = Field(default_factory=dict)
    included: Optional[bool] = True  # frontend may send for clarity; backend ignores if False
    existing_revenue: Dict[str, Dict[str, Dict[str, float]]] = Field(default_factory=dict, description="Uploaded existing revenue overrides per base exit year. Structure: { base_year: { 'recurring': {Month: value}, 'one_time': {Month: value} } }")
    existing_cashflow: Dict[str, Dict[str, Dict[str, float]]] = Field(default_factory=dict, description="Uploaded existing cashflow overrides per base exit year (already timed, no offsets applied). Structure: { base_year: { 'recurring': {Month: value}, 'one_time': {Month: value} } }")
    fresh_offset_months: int | None = Field(default=None, ge=0, description="Optional per-combination fresh offset (months) overriding global fresh_offset_months in revenue calc. Deprecated: use recurring_offset_months and one_time_offset_months instead.")
    recurring_offset_months: int | None = Field(default=None, ge=0, description="Per-combination recurring revenue P&L offset (months). Overrides fresh_offset_months for recurring revenue.")
    one_time_offset_months: int | None = Field(default=None, ge=0, description="Per-combination one-time revenue P&L offset (months). Overrides fresh_offset_months for one-time revenue.")
    cashflow_offset_months: int | None = Field(default=0, ge=0, description="Per-combination cashflow timing offset (months) applied to P&L inflows and outflows when generating cashflow summary.")
    cashflow_recurring_offset_months: int | None = Field(default=None, ge=0, description="Per-combination cashflow offset for recurring inflows. Falls back to cashflow_offset_months if unset.")
    cashflow_one_time_offset_months: int | None = Field(default=None, ge=0, description="Per-combination cashflow offset for one-time inflows. Falls back to cashflow_offset_months if unset.")
    # CAPEX specific independent offsets
    capex_offset_months: int | None = Field(default=0, ge=0, description="Recognition offset (months) for CAPEX fresh cumulative volume logic (separate from revenue/opex).")
    capex_cashflow_offset_months: int | None = Field(default=0, ge=0, description="Cash timing offset (months) for CAPEX items at combination level (added to per-item CAPEX cashflow offsets).")

class DynamicMultiYearVolumePayload(BaseModel):
    fiscal_year: str
    prior_years: List[str] = []
    dimensions: List[str] = []  # ordered list of dimension names (for reference/display)
    combinations: List[DynamicVolumeCombination] = []

class DynamicMultiYearVolumeResponse(BaseModel):
    fiscal_year: str
    months: List[str]
    rows: List[Dict[str, Any]]
    totals: Dict[str, float]
    grand_total: float
    dimension_totals: Dict[str, Any] = Field(default_factory=dict, description="Optional per-dimension aggregated totals")

# ------------------ Revenue Calculation Models ------------------
class RateEntry(BaseModel):
    dimensions: Dict[str, str]
    # Fresh volume rates
    recurring_rate: float = 0.0  # per unit per month (fresh cumulative basis if base_exit_year provided)
    one_time_rate: float = 0.0   # per unit (fresh cumulative basis if base_exit_year provided)
    # Existing (prior year exit) rates
    existing_recurring_rate: float = 0.0  # per unit per month applied to selected base exit volume
    existing_one_time_rate: float = 0.0   # per unit applied to selected base exit volume (cumulative logic mirrors recurring when base_exit_year provided)
    one_time_month: str | None = None  # if None apply in first month with volume > 0 else specified month

class RevenueCalcPayload(BaseModel):
    fiscal_year: str
    months: List[str] = FISCAL_MONTHS
    volumes: List[DynamicVolumeCombination] = []
    rates: List[RateEntry] = []
    lob: Optional[str] = Field(default='FTTH', description="Line of Business identifier. Currently only 'FTTH' is implemented.")
    formula_recurring: Optional[str] = Field(default=None, description="Expression for recurring revenue per month. Variables: volume, recurring_rate. Functions: basic math, min,max,round,abs,pow,sqrt,ceil,floor,log,log10,exp.")
    formula_one_time: Optional[str] = Field(default=None, description="Expression for one-time revenue (evaluated yearly). Variables: total_volume_year, one_time_rate.")
    base_exit_year: Optional[str] = Field(default=None, description="Prior year whose exit volume should be treated as existing base volume.")
    fresh_offset_months: int = Field(default=0, ge=0, description="Number of months to delay recognition of fresh volumes. Deprecated: use recurring_offset_months and one_time_offset_months for separate control.")
    recurring_offset_months: int = Field(default=0, ge=0, description="Number of months to delay recognition of fresh recurring revenue. Overrides fresh_offset_months for recurring if provided.")
    one_time_offset_months: int = Field(default=0, ge=0, description="Number of months to delay recognition of fresh one-time revenue. Overrides fresh_offset_months for one-time if provided.")
    include_fresh_volumes: bool = Field(default=True, description="If false, ignore all fresh volumes (only existing base exit volume revenue flows).")
    # Opex extensions
    opex_items: List[Dict[str, Any]] = Field(default_factory=list, description="List of Opex items: each requires name (str) and fresh_offset_months (int >=0). Example: [{name:'Power', fresh_offset_months:1}]")
    opex_rates: List[Dict[str, Any]] = Field(default_factory=list, description="Per-combination per-item Opex rates. Fields: dimensions (mapping), item (str), existing_rate, fresh_rate")
    existing_opex_overrides: List[Dict[str, Any]] = Field(default_factory=list, description="List of existing Opex overrides. Each entry: {item: str, fiscal_year: str, months: {Apr:val,...}}. Replaces existing portion only; fresh portion still computed from volumes.")
    # CAPEX extensions
    capex_items: List[Dict[str, Any]] = Field(default_factory=list, description="List of CAPEX items. Fields: name, group (First Time Inventory, First Time Capex, Capex People, Replacement Inventory, Replacement Capex, ROW Deposit, Deposit Refund), type ('first_time' or 'replacement' or 'people' or 'deposit_refund'), recognition_offset_months (>=0), cashflow_offset_months (>=0), is_refund (bool). First time & people & deposits: fresh only; replacement: existing + fresh logic like revenue.")
    capex_rates: List[Dict[str, Any]] = Field(default_factory=list, description="Per-combination per-item CAPEX rates. Fields: dimensions (mapping), item (str), existing_rate, fresh_rate.")
    existing_capex_overrides: List[Dict[str, Any]] = Field(default_factory=list, description="Existing CAPEX overrides for replacement items only. Each: {item: str, fiscal_year: str, months: {Apr:val,...}} replacing existing portion only.")

    # ------------------ Template / Upload Endpoints ------------------
    @app.get("/api/template/existing")
    async def download_existing_template():
        """Return CSV template for existing revenue/cashflow upload.
        Columns: Customer,Circle,Type,Revenue Type,Fiscal Year,Apr,...,Mar,Total,Exit Volume
        Allowed Revenue Type values:
            - recurring
            - one time
            - cashflow recurring (already timed; no offsets applied)
            - cashflow one time (already timed; no offsets applied)
        """
        header = ["Customer","Circle","Type","Revenue Type","Fiscal Year"] + FISCAL_MONTHS + ["Total","Exit Volume"]
        csv_content = ",".join(header) + "\n"
        return {"filename": "existing_revenue_template.csv", "content": csv_content}

    @app.post("/api/upload/existing")
    async def upload_existing(file: UploadFile = File(...)):
        """Parse uploaded existing revenue file in new template format.

        Hard errors on missing columns, invalid revenue type, non-numeric or negative numbers.
        Duplicate rows aggregated (sum) per (Customer,Circle,Type,Fiscal Year,Revenue Type).
        Output rows aggregated per (Customer,Circle,Type,Fiscal Year) with recurring & one_time maps and total Exit Volume.
        """
        filename = file.filename.lower()
        content = await file.read()
        required_base = {"Customer","Circle","Type","Revenue Type","Fiscal Year","Exit Volume"}
        month_cols = set(FISCAL_MONTHS)
        def _validate_and_aggregate(df_rows):
            errors: List[str] = []
            group: Dict[tuple, Dict[str, Any]] = {}
            for idx, r in df_rows:
                try:
                    cust = str(r.get('Customer')).strip()
                    circle = str(r.get('Circle')).strip()
                    typ = str(r.get('Type')).strip()
                    rev_type = str(r.get('Revenue Type')).strip()
                    fy = str(r.get('Fiscal Year')).strip()
                except Exception:
                    errors.append(f"Row {idx+1}: unable to read mandatory fields")
                    continue
                if not (cust and circle and typ and rev_type and fy):
                    errors.append(f"Row {idx+1}: blank mandatory field")
                    continue
                rev_type_norm = rev_type.lower()
                valid_types = ('recurring','one time','one-time','onetime','cashflow recurring','cf recurring','cashflow one time','cashflow one-time','cashflow onetime','cf one time','cf one-time','cf onetime')
                if rev_type_norm not in valid_types:
                    errors.append(f"Row {idx+1}: invalid Revenue Type '{rev_type}'")
                    continue
                if rev_type_norm.startswith('recurring'):
                    rt = 'recurring'
                elif rev_type_norm.startswith('one'):
                    rt = 'one_time'
                elif 'cashflow' in rev_type_norm or rev_type_norm.startswith('cf '):
                    if 'recurring' in rev_type_norm:
                        rt = 'cf_recurring'
                    else:
                        rt = 'cf_one_time'
                else:
                    rt = 'recurring'
                key = (cust,circle,typ,fy, rt)
                # Parse months
                months_parsed: Dict[str,float] = {}
                month_error = False
                for m in FISCAL_MONTHS:
                    val = r.get(m)
                    if val in (None, "", " "):
                        val = 0
                    try:
                        fval = float(val)
                    except Exception:
                        errors.append(f"Row {idx+1}: non-numeric value for {m}")
                        month_error = True
                        break
                    if fval < 0:
                        errors.append(f"Row {idx+1}: negative value for {m}")
                        month_error = True
                        break
                    months_parsed[m] = fval
                if month_error:
                    continue
                # Exit volume
                try:
                    exit_vol_raw = r.get('Exit Volume')
                    exit_vol = float(exit_vol_raw) if exit_vol_raw not in (None, "", " ") else 0.0
                    if exit_vol < 0:
                        errors.append(f"Row {idx+1}: negative Exit Volume")
                        continue
                except Exception:
                    errors.append(f"Row {idx+1}: invalid Exit Volume")
                    continue
                if key not in group:
                    group[key] = {"months": {m:0.0 for m in FISCAL_MONTHS}, "exit_volume": 0.0}
                for m,v in months_parsed.items():
                    group[key]["months"][m] += v
                group[key]["exit_volume"] += exit_vol
            if errors:
                raise HTTPException(status_code=422, detail={"errors": errors})
            # Aggregate to combination+FY
            combo_year_map: Dict[tuple, Dict[str, Any]] = {}
            for (cust,circle,typ,fy,rt), data in group.items():
                ckey = (cust,circle,typ,fy)
                entry = combo_year_map.setdefault(ckey, {
                    'dimensions': {'Customer': cust, 'Circle': circle, 'Type': typ},
                    'fiscal_year': fy,
                    'exit_volume': 0.0,
                    'recurring': {m:0.0 for m in FISCAL_MONTHS},
                    'one_time': {m:0.0 for m in FISCAL_MONTHS},
                    'cf_recurring': {m:0.0 for m in FISCAL_MONTHS},
                    'cf_one_time': {m:0.0 for m in FISCAL_MONTHS},
                })
                entry['exit_volume'] += data['exit_volume']
                if rt == 'recurring':
                    for m,v in data['months'].items():
                        entry['recurring'][m] += v
                elif rt == 'one_time':
                    for m,v in data['months'].items():
                        entry['one_time'][m] += v
                elif rt == 'cf_recurring':
                    for m,v in data['months'].items():
                        entry['cf_recurring'][m] += v
                elif rt == 'cf_one_time':
                    for m,v in data['months'].items():
                        entry['cf_one_time'][m] += v
            return list(combo_year_map.values())

        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            if not pd:
                raise HTTPException(status_code=415, detail="XLSX support requires pandas. Upload CSV instead.")
            try:
                df = pd.read_excel(io.BytesIO(content))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to read Excel: {e}")
            cols = set(df.columns)
            missing = (required_base | month_cols) - cols
            if missing:
                raise HTTPException(status_code=422, detail={"errors": [f"Missing columns: {', '.join(sorted(missing))}"]})
            rows = _validate_and_aggregate(list(df.iterrows()))
        else:
            try:
                text = content.decode('utf-8-sig')
            except Exception:
                raise HTTPException(status_code=400, detail="File must be UTF-8 text")
            reader = csv.DictReader(io.StringIO(text))
            fieldnames = reader.fieldnames or []
            cols = set(fieldnames)
            missing = (required_base | month_cols) - cols
            if missing:
                raise HTTPException(status_code=422, detail={"errors": [f"Missing columns: {', '.join(sorted(missing))}"]})
            rows_data = list(enumerate(reader))
            rows = _validate_and_aggregate(rows_data)
        return {"rows": rows}

    @app.get("/api/template/opex_existing")
    async def download_opex_existing_template():
        """Return CSV template for existing Opex upload (global per item, no dimensions).

        Columns: Opex Item,Fiscal Year,Apr,...,Mar
        """
        header = ["Opex Item","Fiscal Year"] + FISCAL_MONTHS
        csv_content = ",".join(header) + "\n"
        return {"filename": "existing_opex_template.csv", "content": csv_content}

    @app.post("/api/upload/opex_existing")
    async def upload_opex_existing(file: UploadFile = File(...)):
        """Parse uploaded existing Opex file.

        Aggregates duplicate (Opex Item, Fiscal Year) rows by summing month values.
        Negative or non-numeric values rejected. Blank => 0.
        """
        filename = file.filename.lower()
        content = await file.read()
        required = {"Opex Item","Fiscal Year"}
        month_cols = set(FISCAL_MONTHS)

        def _process_rows(iter_rows):
            errors: List[str] = []
            agg: Dict[tuple, Dict[str, float]] = {}
            for idx, r in iter_rows:
                try:
                    item = str(r.get('Opex Item')).strip()
                    fy = str(r.get('Fiscal Year')).strip()
                except Exception:
                    errors.append(f"Row {idx+1}: unable to read mandatory fields")
                    continue
                if not item or not fy:
                    errors.append(f"Row {idx+1}: blank Opex Item or Fiscal Year")
                    continue
                key = (item, fy)
                months_map: Dict[str,float] = {}
                bad = False
                for m in FISCAL_MONTHS:
                    raw = r.get(m)
                    if raw in (None, "", " "):
                        val = 0.0
                    else:
                        try:
                            val = float(raw)
                        except Exception:
                            errors.append(f"Row {idx+1}: non-numeric value for {m}")
                            bad = True
                            break
                        if val < 0:
                            errors.append(f"Row {idx+1}: negative value for {m}")
                            bad = True
                            break
                    months_map[m] = val
                if bad:
                    continue
                entry = agg.setdefault(key, {m:0.0 for m in FISCAL_MONTHS})
                for m,v in months_map.items():
                    entry[m] += v
            if errors:
                raise HTTPException(status_code=422, detail={"errors": errors})
            rows = []
            for (item, fy), months in agg.items():
                rows.append({"item": item, "fiscal_year": fy, "months": months})
            return rows

        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            if not pd:
                raise HTTPException(status_code=415, detail="XLSX support requires pandas. Upload CSV instead.")
            try:
                df = pd.read_excel(io.BytesIO(content))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to read Excel: {e}")
            cols = set(df.columns)
            missing = (required | month_cols) - cols
            if missing:
                raise HTTPException(status_code=422, detail={"errors": [f"Missing columns: {', '.join(sorted(missing))}"]})
            rows = _process_rows(list(df.iterrows()))
        else:
            try:
                text = content.decode('utf-8-sig')
            except Exception:
                raise HTTPException(status_code=400, detail="File must be UTF-8 text")
            reader = csv.DictReader(io.StringIO(text))
            fieldnames = reader.fieldnames or []
            cols = set(fieldnames)
            missing = (required | month_cols) - cols
            if missing:
                raise HTTPException(status_code=422, detail={"errors": [f"Missing columns: {', '.join(sorted(missing))}"]})
            rows = _process_rows(list(enumerate(reader)))
        return {"rows": rows}

    @app.post("/api/opex/rates-template")
    async def get_opex_rates_template(payload: dict = Body(...)):
        """Generate OPEX rates template CSV matching frontend table structure.
        
        Format: Combination | Item1 (Existing Rate) | Item1 (Fresh Rate) | Item2 (Existing Rate) | ...
        """
        volumes = payload.get('volumes', [])
        opex_items_list = payload.get('opex_items', [])
        
        if not volumes or not opex_items_list:
            raise HTTPException(status_code=400, detail="volumes and opex_items are required")
        
        # Build header: Combination + (Item_Existing, Item_Fresh) for each item
        header = ["Combination"]
        for item in opex_items_list:
            item_name = item.get('name', '')
            header.append(f"{item_name} (Existing Rate)")
            header.append(f"{item_name} (Fresh Rate)")
        
        csv_lines = [",".join(header)]
        
        # Generate rows: one row per combination
        for combo in volumes:
            dims = combo.get('dimensions', {})
            combo_name = " / ".join(str(dims.get(k, "")) for k in dims.keys())
            
            row = [combo_name]
            for item in opex_items_list:
                row.append("")  # Existing Rate (empty for user input)
                row.append("")  # Fresh Rate (empty for user input)
            
            csv_lines.append(",".join(row))
        
        csv_content = "\n".join(csv_lines)
        return StreamingResponse(
            iter([csv_content.encode('utf-8')]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=opex_rates_template.csv"}
        )

    @app.post("/api/opex/rates-upload")
    async def upload_opex_rates(file: UploadFile = File(...)):
        """Parse uploaded OPEX rates CSV in transposed format.
        
        Expected format: Combination | Item1 (Existing Rate) | Item1 (Fresh Rate) | Item2 (Existing Rate) | ...
        Returns: { rates: { "item": { "combo": { "existing_rate": X, "fresh_rate": Y } } } }
        """
        filename = file.filename.lower()
        content = await file.read()
        
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            if not pd:
                raise HTTPException(status_code=415, detail="XLSX support requires pandas. Upload CSV instead.")
            try:
                df = pd.read_excel(io.BytesIO(content))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to read Excel: {e}")
            rows = df.to_dict('records')
            col_names = list(df.columns)
        else:
            try:
                text = content.decode('utf-8-sig')
            except Exception:
                raise HTTPException(status_code=400, detail="File must be UTF-8 text")
            reader = csv.DictReader(io.StringIO(text))
            col_names = reader.fieldnames or []
            rows = list(reader)
        
        if not rows:
            raise HTTPException(status_code=400, detail="No data rows found in file")
        
        # Parse rates from transposed format
        rates = {}
        errors = []
        
        # Column 0 is Combination, then pairs of (Item Existing, Item Fresh)
        for idx, row in enumerate(rows, start=2):
            try:
                combo = str(row.get('Combination', '')).strip()
                if not combo:
                    errors.append(f"Row {idx}: Missing Combination")
                    continue
                
                # Parse all other columns as rate pairs
                for col_idx, col_name in enumerate(col_names):
                    if col_name.lower() == 'combination':
                        continue
                    
                    # Extract item name from column header like "Item Name (Existing Rate)"
                    if '(Existing Rate)' in col_name:
                        item_name = col_name.replace(' (Existing Rate)', '').strip()
                        existing_val = row.get(col_name, '')
                        
                        # Find corresponding Fresh Rate column
                        fresh_col_name = f"{item_name} (Fresh Rate)"
                        fresh_val = row.get(fresh_col_name, '')
                        
                        try:
                            existing_rate = float(existing_val) if existing_val and str(existing_val).strip() else 0.0
                        except (ValueError, TypeError):
                            errors.append(f"Row {idx}: Invalid Existing Rate for {item_name}: '{existing_val}'")
                            continue
                        
                        try:
                            fresh_rate = float(fresh_val) if fresh_val and str(fresh_val).strip() else 0.0
                        except (ValueError, TypeError):
                            errors.append(f"Row {idx}: Invalid Fresh Rate for {item_name}: '{fresh_val}'")
                            continue
                        
                        if item_name not in rates:
                            rates[item_name] = {}
                        rates[item_name][combo] = {
                            "existing_rate": existing_rate,
                            "fresh_rate": fresh_rate
                        }
            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")
        
        if errors:
            raise HTTPException(status_code=422, detail={"errors": errors})
        
        return {"rates": rates, "rows_processed": len(rows)}


        dimensions: Dict[str, str]
        monthly_revenue: Dict[str, float]
        monthly_recurring: Dict[str, float] = Field(default_factory=dict)
        monthly_one_time: Dict[str, float] = Field(default_factory=dict)
        # Added breakdown so cashflow can exclude existing one-time component
        monthly_existing_one_time: Dict[str, float] = Field(default_factory=dict)
        monthly_fresh_one_time: Dict[str, float] = Field(default_factory=dict)
        total_recurring: float
        total_one_time: float
        total_revenue: float
        existing_recurring: float = 0.0
        fresh_recurring: float = 0.0
        existing_one_time: float = 0.0
        fresh_one_time: float = 0.0

    class RevenueCalcResponse(BaseModel):
        fiscal_year: str
        months: List[str]
        rows: List[RevenueRow]
        monthly_totals: Dict[str, float]
        monthly_recurring_totals: Dict[str, float]
        monthly_one_time_totals: Dict[str, float]
        total_revenue: float
        # Opex outputs
        opex_items: List[Dict[str, Any]] = Field(default_factory=list, description="Per opex item monthly + total")
        monthly_opex_totals: Dict[str, float] = Field(default_factory=dict)
        total_opex: float = 0.0
        # Cashflow outputs (shifted by per-combination cashflow_offset_months)
        monthly_cash_recurring_inflow: Dict[str, float] = Field(default_factory=dict)
        monthly_cash_one_time_inflow: Dict[str, float] = Field(default_factory=dict)
        monthly_cash_passthrough_inflow: Dict[str, float] = Field(default_factory=dict)
        monthly_cash_gross_inflow: Dict[str, float] = Field(default_factory=dict)
        monthly_cash_outflow_items: List[Dict[str, Any]] = Field(default_factory=list, description="Per opex item cash outflow after offsets")
        monthly_cash_outflow_totals: Dict[str, float] = Field(default_factory=dict)
        monthly_cash_net_operating: Dict[str, float] = Field(default_factory=dict)
        total_cash_recurring_inflow: float = 0.0
        total_cash_one_time_inflow: float = 0.0
        total_cash_gross_inflow: float = 0.0
        total_cash_outflow: float = 0.0
        total_cash_net_operating: float = 0.0
        # CAPEX outputs & extended cashflow
        capex_items: List[Dict[str, Any]] = Field(default_factory=list, description="Per CAPEX item (recognized amounts before cash shift)")
        monthly_capex_totals: Dict[str, float] = Field(default_factory=dict, description="Net CAPEX (outflow minus refunds) per month after cash timing shifts")
        total_capex: float = 0.0
        monthly_net_cashflow: Dict[str, float] = Field(default_factory=dict, description="Net Operating Flow - CAPEX")
        monthly_cum_net_cashflow: Dict[str, float] = Field(default_factory=dict)
        peak_funding: float = 0.0
        total_net_cashflow: float = 0.0

def _dim_key(dimensions: Dict[str,str]) -> str:
    return '|'.join(f"{k}={dimensions[k]}" for k in sorted(dimensions.keys()))

@app.get("/api/health")
async def health():
    return {"status": "ok"}




@app.get("/api/sample/budget")
async def sample_budget():
    return {
        "year": "FY25",
        "total": 123456.78,
        "categories": [
            {"name": "Recurring", "amount": 90000},
            {"name": "One Time", "amount": 20000},
            {"name": "Other", "amount": 13456.78},
        ],
    }

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    filename = file.filename.lower()
    content = await file.read()
    buf = io.BytesIO(content)
    # Use pandas path if available
    if pd:
        try:
            if filename.endswith(".csv"):
                df = pd.read_csv(buf)
            else:
                df = pd.read_excel(buf)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")
        required_cols = {"Site Type", "Customer", "Circle", "Revenue Year"} | set(FISCAL_MONTHS)
        if not required_cols.issubset(set(df.columns)):
            raise HTTPException(status_code=422, detail="Missing required columns")
        df_long = df.melt(
            id_vars=["Site Type", "Customer", "Circle", "Revenue Year", "Type of Revenue"],
            value_vars=FISCAL_MONTHS,
            var_name="Month",
            value_name="Existing Revenue"
        )
        return df_long.to_dict(orient="records")
    # Fallback minimal CSV parser (no Excel support)
    if not filename.endswith('.csv'):
        raise HTTPException(status_code=415, detail="Excel parsing needs pandas; upload CSV instead.")
    buf.seek(0)
    text = buf.read().decode('utf-8')
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    # Very simple reshape: assume columns present and already long format for months
    return rows

@app.post("/api/budget/calculate")
async def budget_calculate(payload: BudgetCalcRequest):
    # Placeholder calculation until real logic added
    monthly = {m: 0 for m in FISCAL_MONTHS}
    total = 0
    return {"monthly": monthly, "total": total}

@app.post("/api/volume/calculate", response_model=VolumeResponse)
async def calculate_volume(payload: VolumePayload):
    # Normalize order
    vols = []
    cumulative = []
    running = 0.0
    for m in FISCAL_MONTHS:
        v = float(payload.volume.get(m, 0) or 0)
        vols.append(v)
        running += v
        cumulative.append(running)
    return VolumeResponse(
        months=FISCAL_MONTHS,
        volume=vols,
        cumulative=cumulative,
        total_volume=running
    )

@app.post("/api/volume/multiyear", response_model=MultiYearVolumeResponse)
async def volume_multiyear(payload: MultiYearVolumePayload):
    # Aggregate only current fiscal year for now
    fy = payload.fiscal_year
    month_totals = {m: 0.0 for m in FISCAL_MONTHS}
    rows: List[Dict[str, Any]] = []
    for combo in payload.combinations:
        fy_months = combo.volumes.get(fy, {})
        row_months = {}
        row_total = 0.0
        for m in FISCAL_MONTHS:
            v = float(fy_months.get(m, 0) or 0)
            row_months[m] = v
            month_totals[m] += v
            row_total += v
        rows.append({
            "cost_center": combo.cost_center,
            "uom": combo.uom,
            "site_type": combo.site_type,
            "customer": combo.customer,
            "months": row_months,
            "total": row_total,
            "prior_exit_volumes": combo.exit_volumes
        })
    grand_total = sum(month_totals.values())
    return MultiYearVolumeResponse(
        fiscal_year=fy,
        months=FISCAL_MONTHS,
        rows=rows,
        totals=month_totals,
        grand_total=grand_total
    )

@app.post("/api/volume/multiyear/dynamic", response_model=DynamicMultiYearVolumeResponse)
async def volume_multiyear_dynamic(payload: DynamicMultiYearVolumePayload):
    """Dynamic version: Works with arbitrary dimension sets including mandatory customer, circle, type.

    Returns per-combination monthly & total plus overall monthly totals. Additionally computes simple
    per-dimension subtotal aggregation (summing across other dimensions) for informational display, but
    does not create synthetic 'Total' combinations; these are derived only.
    """
    fy = payload.fiscal_year
    month_totals = {m: 0.0 for m in FISCAL_MONTHS}
    rows: List[Dict[str, Any]] = []

    # Aggregate per dimension value -> monthly totals (nested dict)
    per_dimension: Dict[str, Dict[str, Dict[str, float]]] = {}

    for combo in payload.combinations:
        if combo.included is False:
            continue  # skip excluded rows
        fy_months = combo.volumes.get(fy, {})
        row_months: Dict[str, float] = {}
        row_total = 0.0
        for m in FISCAL_MONTHS:
            v = float(fy_months.get(m, 0) or 0)
            row_months[m] = v
            month_totals[m] += v
            row_total += v
        rows.append({
            "dimensions": combo.dimensions,
            "months": row_months,
            "total": row_total,
            "prior_exit_volumes": combo.exit_volumes
        })
        # Dimension aggregation
        for dim_name, dim_value in combo.dimensions.items():
            dstore = per_dimension.setdefault(dim_name, {})
            mstore = dstore.setdefault(dim_value, {m: 0.0 for m in FISCAL_MONTHS})
            for m in FISCAL_MONTHS:
                mstore[m] += row_months[m]

    grand_total = sum(month_totals.values())

    # Convert per_dimension into totals incl. per-value totals
    dimension_totals: Dict[str, Any] = {}
    for dim_name, value_map in per_dimension.items():
        dimension_totals[dim_name] = []
        for val, mvals in value_map.items():
            dimension_totals[dim_name].append({
                "value": val,
                "months": mvals,
                "total": sum(mvals.values())
            })

    return DynamicMultiYearVolumeResponse(
        fiscal_year=fy,
        months=FISCAL_MONTHS,
        rows=rows,
        totals=month_totals,
        grand_total=grand_total,
        dimension_totals=dimension_totals
    )

@app.post("/api/revenue/calculate", response_model=RevenueCalcResponse)
async def revenue_calculate(payload: RevenueCalcPayload):
    """Dispatch to LOB-specific revenue calculation handlers.

    This function is intentionally small and selects a handler from `LOB_HANDLERS`.
    If no handler is registered for the supplied `payload.lob` the default core
    calculation `_revenue_calc_core` is invoked (preserves existing behaviour).
    """
    lob = (getattr(payload, 'lob', None) or 'FTTH')
    handler = LOB_HANDLERS.get(lob, _revenue_calc_core)
    return handler(payload)


def _handler_small_cell(payload: RevenueCalcPayload) -> RevenueCalcResponse:
    """Small Cell revenue logic handler.

    Small Cell specific behavior:
    1. Fresh Recurring revenue: Fresh cumulative volume (after offset) * recurring rate
    2. Existing Recurring revenue: Base exit year volume * recurring rate (no offset)
    3. Has no one-time revenue (zero)
    
    Note: Pricepoint multiplier is always 1 (no rate adjustment needed).
    """
    # Mark this as Small Cell for custom revenue logic in core
    payload.lob = 'Small Cell'
    return _revenue_calc_core(payload)


def _handler_active(payload: RevenueCalcPayload) -> RevenueCalcResponse:
    """Active revenue logic handler.

    Active has the same behavior as Small Cell:
    1. Fresh Recurring revenue: Fresh cumulative volume (after offset) * recurring rate
    2. Existing Recurring revenue: Base exit year volume * recurring rate (no offset)
    3. Has no one-time revenue (zero)
    """
    payload.lob = 'Active'
    return _revenue_calc_core(payload)


def _handler_sdu(payload: RevenueCalcPayload) -> RevenueCalcResponse:
    """SDU revenue logic handler.

    SDU currently uses the standard revenue logic (offset-aware) without
    additional multipliers or overrides. Dimensions for SDU (customer, circle,
    lock-in, type) are assumed to be provided by the UI, so this handler simply
    marks the LOB and delegates to the core calculator.
    """
    payload.lob = 'SDU'
    return _revenue_calc_core(payload)


def _handler_dark_fiber(payload: RevenueCalcPayload) -> RevenueCalcResponse:
    """Dark Fiber revenue logic handler.

    Dark Fiber uses the standard core logic with:
    - Fresh Recurring: cumulative fresh volume (after offset) * recurring rate
    - Existing Recurring: base exit volume * recurring rate
    - Fresh One-Time (P&L): cumulative fresh volume (after offset) * one-time rate / 180
    - Existing One-Time (P&L): base exit volume * one-time rate / 180
    - Fresh One-Time Cashflow: fresh volume (non-cumulative, after offset) * one-time rate
    """
    payload.lob = 'Dark Fiber'
    return _revenue_calc_core(payload)


def _handler_ohfc(payload: RevenueCalcPayload) -> RevenueCalcResponse:
    """OHFC revenue logic handler.

    OHFC specific behavior:
    1. Fresh Recurring (P&L/cashflow): cumulative fresh volume (after offset) * recurring rate
    2. Fresh One-Time P&L: cumulative fresh volume (after offset) * one_time_rate / 12
    3. Fresh One-Time Cashflow: fresh volume (non-cumulative, after offset) * one_time_rate
    4. Existing Recurring: base exit volume * recurring rate
    5. Existing One-Time (P&L and Cashflow): zero
    """
    payload.lob = 'OHFC'
    return _revenue_calc_core(payload)


def _handler_dark_fiber(payload: RevenueCalcPayload) -> RevenueCalcResponse:
    """Dark Fiber revenue logic handler.

    Dark Fiber specific behavior:
    1. Fresh Recurring revenue: Fresh cumulative volume (after offset) * recurring rate
    2. Existing Recurring revenue: Base exit year volume * recurring rate (no offset)
    3. Fresh One-Time: cumulative fresh volume (after offset) * one_time_rate / 180
    4. Existing One-Time: base exit volume * one_time_rate / 180
    
    Dark Fiber uses the standard division factor of 180 for one-time revenue spread over fiscal year.
    """
    payload.lob = 'Dark Fiber'
    return _revenue_calc_core(payload)


def _handler_co_build(payload: RevenueCalcPayload) -> RevenueCalcResponse:
    """Co Build revenue logic handler.

    Co Build specific behavior (identical to Dark Fiber):
    1. Fresh Recurring revenue: Fresh cumulative volume (after offset) * recurring rate
    2. Existing Recurring revenue: Base exit year volume * recurring rate (no offset)
    3. Fresh One-Time: cumulative fresh volume (after offset) * one_time_rate / 180
    4. Existing One-Time: base exit volume * one_time_rate / 180
    
    Co Build uses the standard division factor of 180 for one-time revenue spread over fiscal year.
    """
    payload.lob = 'Co Build'
    return _revenue_calc_core(payload)


def _revenue_calc_core(payload: RevenueCalcPayload) -> RevenueCalcResponse:
    """Core revenue/cost/cashflow calculation.

    This is the extracted original implementation so LOB-specific handlers can
    call it after making lightweight modifications to the payload.
    """
    # --- Begin extracted core logic (preserves existing behaviour) ---
    fy = payload.fiscal_year
    months = payload.months or FISCAL_MONTHS
    # --- Safe evaluation utilities ---
    allowed_funcs: Dict[str, Any] = {
        'min': min, 'max': max, 'round': round, 'abs': abs, 'pow': pow,
        'sqrt': math.sqrt, 'ceil': math.ceil, 'floor': math.floor,
        'log': math.log, 'log10': math.log10, 'exp': math.exp
    }
    allowed_names = set(allowed_funcs.keys()) | {'volume','recurring_rate','total_volume_year','one_time_rate','v','r','volume_year'}

    lob_upper = (getattr(payload, 'lob', 'FTTH') or 'FTTH').upper()
    passthrough_site_types = {'HPSC', 'LITE SITE', 'HLS'}
    passthrough_items = {'ELECTRICITY', 'RENT'}
    enable_small_cell_passthrough = lob_upper == 'SMALL CELL'

    def _safe_eval(expr: str, variables: Dict[str, float]) -> float:
        try:
            tree = ast.parse(expr, mode='eval')
        except SyntaxError as e:
            raise HTTPException(status_code=400, detail=f"Invalid formula syntax: {e}")
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.Expression, ast.Load, ast.BinOp, ast.UnaryOp,
                                ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd,
                                ast.Num, ast.Constant, ast.Call, ast.Name, ast.FloorDiv, ast.Mod,
                                ast.LShift, ast.RShift, ast.BitXor, ast.BitOr, ast.BitAnd, ast.MatMult)):
                if isinstance(node, ast.Call):
                    if not isinstance(node.func, ast.Name) or node.func.id not in allowed_funcs:
                        raise HTTPException(status_code=400, detail="Disallowed function in formula")
                if isinstance(node, ast.Name) and node.id not in allowed_names:
                    raise HTTPException(status_code=400, detail=f"Unknown variable or function '{node.id}' in formula")
                continue
            else:
                raise HTTPException(status_code=400, detail="Disallowed expression in formula")
        env = {**allowed_funcs}
        env.update({k: float(v) for k,v in variables.items() if k in allowed_names})
        try:
            value = eval(compile(tree, '<formula>', 'eval'), {'__builtins__': {}}, env)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error evaluating formula: {e}")
        try:
            return float(value)
        except Exception:
            raise HTTPException(status_code=400, detail="Formula did not return a numeric value")

    # Build volume map
    vol_map: Dict[str, Dict[str,float]] = {}
    offset_map: Dict[str, int | None] = {}  # Deprecated: backward compatibility
    recurring_offset_map: Dict[str, int | None] = {}
    one_time_offset_map: Dict[str, int | None] = {}
    cashflow_offset_map: Dict[str, int] = {}
    cashflow_rec_offset_map: Dict[str, int | None] = {}
    cashflow_ot_offset_map: Dict[str, int | None] = {}
    existing_cashflow_rec_map: Dict[str, Dict[str,float]] = {}
    existing_cashflow_ot_map: Dict[str, Dict[str,float]] = {}
    # Track combos that represent decommissioning so we can invert exit volumes (E)
    decom_map: Dict[str, bool] = {}
    for combo in payload.volumes:
        fy_months = combo.volumes.get(fy, {})
        key = _dim_key(combo.dimensions)
        # Treat combinations whose `type` dimension equals 'Decom' (case-insensitive)
        is_decom = False
        try:
            is_decom = str(combo.dimensions.get('type','')).strip().lower() == 'decom'
        except Exception:
            is_decom = False
        decom_map[key] = is_decom
        # If decom, negate monthly volumes so downstream calculations treat them as reductions
        vol_map[key] = {m: (-(float(fy_months.get(m,0) or 0)) if is_decom else float(fy_months.get(m,0) or 0)) for m in months}
        # Store offsets - handle both int and string inputs
        combo_fresh_offset = getattr(combo, 'fresh_offset_months', None)
        combo_recurring_offset = getattr(combo, 'recurring_offset_months', None)
        combo_one_time_offset = getattr(combo, 'one_time_offset_months', None)
        combo_cf_rec_offset = getattr(combo, 'cashflow_recurring_offset_months', None)
        combo_cf_ot_offset = getattr(combo, 'cashflow_one_time_offset_months', None)
        # Existing cashflow (already timed, no offsets applied). Use base_exit_year key if provided.
        if payload.base_exit_year:
            cf_map = getattr(combo, 'existing_cashflow', {}) or {}
            cf_entry = cf_map.get(payload.base_exit_year, {}) if isinstance(cf_map, dict) else {}
            if cf_entry:
                rec_cf = cf_entry.get('recurring', {}) or {}
                ot_cf = cf_entry.get('one_time', {}) or {}
                existing_cashflow_rec_map[key] = {m: float(rec_cf.get(m,0) or 0) for m in FISCAL_MONTHS}
                existing_cashflow_ot_map[key] = {m: float(ot_cf.get(m,0) or 0) for m in FISCAL_MONTHS}
        if combo_fresh_offset is not None:
            try:
                combo_fresh_offset = int(combo_fresh_offset)
            except (ValueError, TypeError):
                combo_fresh_offset = None
        if combo_recurring_offset is not None:
            try:
                combo_recurring_offset = int(combo_recurring_offset)
            except (ValueError, TypeError):
                combo_recurring_offset = None
        if combo_one_time_offset is not None:
            try:
                combo_one_time_offset = int(combo_one_time_offset)
            except (ValueError, TypeError):
                combo_one_time_offset = None
        if combo_cf_rec_offset is not None:
            try:
                combo_cf_rec_offset = int(combo_cf_rec_offset)
            except (ValueError, TypeError):
                combo_cf_rec_offset = None
        if combo_cf_ot_offset is not None:
            try:
                combo_cf_ot_offset = int(combo_cf_ot_offset)
            except (ValueError, TypeError):
                combo_cf_ot_offset = None
        offset_map[key] = combo_fresh_offset  # Backward compatibility
        recurring_offset_map[key] = combo_recurring_offset
        one_time_offset_map[key] = combo_one_time_offset
        if combo_recurring_offset is not None and combo_recurring_offset > 0:
            print(f"[OFFSET] {key}: recurring_offset_months={combo_recurring_offset}")
        if combo_one_time_offset is not None and combo_one_time_offset > 0:
            print(f"[OFFSET] {key}: one_time_offset_months={combo_one_time_offset}")
        cf_off = getattr(combo, 'cashflow_offset_months', 0) or 0
        cashflow_offset_map[key] = max(int(cf_off), 0)
        # Specific cashflow offsets for recurring / one-time (fallback to combo CF offset later)
        cashflow_rec_offset_map[key] = combo_cf_rec_offset if combo_cf_rec_offset is not None else None
        cashflow_ot_offset_map[key] = combo_cf_ot_offset if combo_cf_ot_offset is not None else None
    rate_map: Dict[str, RateEntry] = {}
    for r in payload.rates:
        rate_map[_dim_key(r.dimensions)] = r

    monthly_totals = {m:0.0 for m in months}
    monthly_recurring_totals = {m:0.0 for m in months}
    monthly_one_time_totals = {m:0.0 for m in months}
    # Passthrough P&L trackers (e.g., Small Cell rent/electricity)
    monthly_passthrough_revenue = {m:0.0 for m in months}
    monthly_passthrough_expense = {m:0.0 for m in months}
    total_passthrough_revenue = 0.0
    total_passthrough_expense = 0.0
    rows: List[RevenueRow] = []
    grand_total = 0.0
    DEN = 180.0
    DECIMALS = 2  # rounding precision for all monetary outputs
    
    for key, month_vols in vol_map.items():
        r = rate_map.get(key, RateEntry(dimensions={}, recurring_rate=0, one_time_rate=0))
        FR = r.recurring_rate if r else 0.0
        FO = r.one_time_rate if r else 0.0
        ER = r.existing_recurring_rate if r else 0.0
        EO = r.existing_one_time_rate if r else 0.0
        print(f"[RATES] key={key}: FR={FR}, FO={FO}, ER={ER}, EO={EO}")
        include_fresh = getattr(payload, 'include_fresh_volumes', True)
        combo_obj = None
        for c in payload.volumes:
            if _dim_key(c.dimensions) == key:
                combo_obj = c
                break

        # Existing per-Lob example preserved (Small Cell multiplier handled by handler if needed)
        E = 0.0
        if payload.base_exit_year and combo_obj:
            E = float(combo_obj.exit_volumes.get(payload.base_exit_year, 0) or 0)
            # If this combination is a decommissioning entry, treat the base exit volume as negative
            if decom_map.get(key):
                E = -E
        print(f"[BASE-EXIT] key={key}, base_exit_year={payload.base_exit_year}, E={E}, exit_volumes={combo_obj.exit_volumes if combo_obj else 'N/A'}")
        existing_override_rec: Dict[str, float] | None = None
        existing_override_ot: Dict[str, float] | None = None
        if payload.base_exit_year and combo_obj and combo_obj.existing_revenue:
            override = combo_obj.existing_revenue.get(payload.base_exit_year)
            if override:
                existing_override_rec = {m: float(override.get('recurring', {}).get(m, 0) or 0) for m in months}
                existing_override_ot = {m: float(override.get('one_time', {}).get(m, 0) or 0) for m in months}
        ordered_months = list(months)
        raw_vols = [float(month_vols.get(m,0.0)) for m in ordered_months]
        cum_raw: List[float] = []
        running = 0.0
        for v in raw_vols:
            running += v
            cum_raw.append(running)
        print(f"[VOL-DEBUG] key={key}, raw_vols={raw_vols}, cum_raw={cum_raw}")
        combo_offset = offset_map.get(key)
        combo_recurring_off = recurring_offset_map.get(key)
        combo_one_time_off = one_time_offset_map.get(key)
        
        # Coerce offsets to integers safely (handle strings like '02')
        parsed_combo_offset = None
        parsed_recurring_offset = None
        parsed_one_time_offset = None
        
        try:
            if combo_offset is not None:
                parsed_combo_offset = int(combo_offset)
                if parsed_combo_offset < 0:
                    parsed_combo_offset = None
        except (ValueError, TypeError):
            parsed_combo_offset = None
        
        try:
            if combo_recurring_off is not None:
                parsed_recurring_offset = int(combo_recurring_off)
                if parsed_recurring_offset < 0:
                    parsed_recurring_offset = None
        except (ValueError, TypeError):
            parsed_recurring_offset = None
            
        try:
            if combo_one_time_off is not None:
                parsed_one_time_offset = int(combo_one_time_off)
                if parsed_one_time_offset < 0:
                    parsed_one_time_offset = None
        except (ValueError, TypeError):
            parsed_one_time_offset = None
        
        # Determine offsets with fallback logic:
        # 1. Use combo-specific recurring/one-time offset if provided
        # 2. Fall back to combo fresh_offset_months (deprecated)
        # 3. Fall back to payload-level recurring/one-time offset if provided
        # 4. Fall back to payload fresh_offset_months (deprecated)
        payload_recurring = max(int(getattr(payload, 'recurring_offset_months', 0) or 0), 0)
        payload_one_time = max(int(getattr(payload, 'one_time_offset_months', 0) or 0), 0)
        payload_fresh = max(int(getattr(payload, 'fresh_offset_months', 0) or 0), 0)
        
        # Recurring offset: prefer specific recurring, then combo fresh, then payload recurring, then payload fresh
        if parsed_recurring_offset is not None:
            recurring_offset = parsed_recurring_offset
        elif parsed_combo_offset is not None:
            recurring_offset = parsed_combo_offset
        elif payload_recurring > 0:
            recurring_offset = payload_recurring
        else:
            recurring_offset = payload_fresh
            
        # One-time offset: prefer specific one-time, then combo fresh, then payload one-time, then payload fresh
        if parsed_one_time_offset is not None:
            one_time_offset = parsed_one_time_offset
        elif parsed_combo_offset is not None:
            one_time_offset = parsed_combo_offset
        elif payload_one_time > 0:
            one_time_offset = payload_one_time
        else:
            one_time_offset = payload_fresh
        
        # Backward compatibility: keep single offset variable for other uses
        offset = parsed_combo_offset if parsed_combo_offset is not None else payload_fresh
        
        if recurring_offset > 0 or one_time_offset > 0:
            print(f"[CALC] key={key}, recurring_offset={recurring_offset}, one_time_offset={one_time_offset}, include_fresh={include_fresh}, FR={FR}, FO={FO}")
        
        # Check LOB flags for custom logic
        lob_name = (getattr(payload, 'lob', 'FTTH') or 'FTTH').upper()
        is_small_cell = lob_name == 'SMALL CELL'
        is_sdu = lob_name == 'SDU'
        is_ohfc = lob_name == 'OHFC'
        is_active = lob_name == 'ACTIVE'
        is_dark_fiber = lob_name == 'DARK FIBER'

        # Dark Fiber: optionally multiply fresh components by number of pairs captured in dimensions
        pair_multiplier = 1.0
        if is_dark_fiber and combo_obj and isinstance(combo_obj.dimensions, dict):
            for k, v in combo_obj.dimensions.items():
                try:
                    key_norm = str(k).lower().replace('_', ' ').strip()
                    if 'pair' in key_norm:
                        parsed = float(v)
                        if parsed > 0:
                            pair_multiplier = parsed
                        break
                except Exception:
                    continue

        # Extract lock-in (months) for SDU; default to 1 to avoid divide-by-zero
        lock_in_val = 1.0
        if is_sdu and combo_obj and isinstance(combo_obj.dimensions, dict):
            for k, v in combo_obj.dimensions.items():
                try:
                    key_norm = str(k).lower().replace('-', ' ').replace('_', ' ').strip()
                    if key_norm in ['lock in', 'lockin']:
                        lv = float(v)
                        if lv > 0:
                            lock_in_val = lv
                        break
                except Exception:
                    continue
        
        monthly_rev: Dict[str, float] = {}
        monthly_rec: Dict[str, float] = {}
        monthly_ot: Dict[str, float] = {}
        monthly_existing_ot_map: Dict[str, float] = {}
        monthly_fresh_ot_map: Dict[str, float] = {}
        monthly_cashflow_rec_map: Dict[str, float] = {}
        monthly_cashflow_ot_map: Dict[str, float] = {}
        existing_recurring_total = 0.0
        fresh_recurring_total = 0.0
        existing_one_time_total = 0.0
        fresh_one_time_total = 0.0
        total_recurring = 0.0
        total_one_time = 0.0

        # Track whether we've recognized one-time revenue for this combination
        # This ensures one-time is recognized only once, accounting for offset
        one_time_recognized = False
        
        # Note: existing one-time has NO cashflow component
        existing_ot_total_amount = 0.0
        
        for idx, m in enumerate(months):
            if existing_override_rec is not None and existing_override_ot is not None:
                existing_rec_m = existing_override_rec.get(m, 0.0)
                existing_ot_m = existing_override_ot.get(m, 0.0)
            else:
                # Existing recurring: base exit volume * recurring rate (no offset, constant monthly)
                existing_rec_m = E * ER
                # Existing one-time:
                # - Small Cell: zero
                # - Active: zero
                # - OHFC: zero
                # - SDU: base exit volume * one-time rate / (lock_in * 12)
                # - Others: base exit volume * one-time rate / 180
                if is_small_cell or is_active or is_ohfc:
                    existing_ot_m = 0.0
                elif is_sdu:
                    denom = (lock_in_val * 12.0) if lock_in_val > 0 else 12.0
                    existing_ot_m = (E * EO / denom) if EO else 0.0
                else:
                    existing_ot_m = (E * EO / DEN) if EO else 0.0
            
            # Calculate cumulative volumes for recurring (uses recurring_offset)
            eff_cum_recurring = 0.0
            # Calculate cumulative volumes for one-time (uses one_time_offset)
            eff_cum_one_time = 0.0
            prev_eff_cum = 0.0
            fresh_vol_month = 0.0  # Non-cumulative fresh volume for this month (for cashflow)
            
            if include_fresh:
                # Recurring: use recurring_offset
                if idx >= recurring_offset and len(cum_raw) > (idx - recurring_offset):
                    eff_cum_recurring = cum_raw[idx - recurring_offset]
                    if idx < 4:
                        print(f"[LOOP-REC] month {idx}({m}): idx({idx}) >= recurring_offset({recurring_offset}), eff_cum_recurring={eff_cum_recurring}, cum_raw[{idx-recurring_offset}]={cum_raw[idx-recurring_offset]}")
                else:
                    eff_cum_recurring = 0.0
                    if idx < 4:
                        print(f"[LOOP-REC] month {idx}({m}): idx({idx}) < recurring_offset({recurring_offset}), eff_cum_recurring=0, cum_raw length={len(cum_raw)}")
                
                # One-time: use one_time_offset
                if idx >= one_time_offset and len(cum_raw) > (idx - one_time_offset):
                    eff_cum_one_time = cum_raw[idx - one_time_offset]
                    if one_time_offset > 0 and idx < 4:
                        print(f"[LOOP-OT] month {idx}({m}): idx({idx}) >= one_time_offset({one_time_offset}), eff_cum_one_time={eff_cum_one_time}")
                else:
                    eff_cum_one_time = 0.0
                    if one_time_offset > 0 and idx < 4:
                        print(f"[LOOP-OT] month {idx}({m}): idx({idx}) < one_time_offset({one_time_offset}), eff_cum_one_time=0")
                
                # Get non-cumulative fresh volume for this month (for cashflow) - use offset for backward compatibility
                if idx >= offset and len(cum_raw) > (idx - offset):
                    eff_cum = cum_raw[idx - offset]
                    if idx == offset:
                        fresh_vol_month = eff_cum
                    else:
                        prev_cum = cum_raw[(idx - 1) - offset] if len(cum_raw) > ((idx - 1) - offset) else 0.0
                        fresh_vol_month = eff_cum - prev_cum
                else:
                    fresh_vol_month = 0.0
                
                # Get non-cumulative fresh volume for one-time (uses one_time_offset)
                fresh_vol_month_ot = 0.0
                if idx >= one_time_offset and len(cum_raw) > (idx - one_time_offset):
                    eff_cum_ot = cum_raw[idx - one_time_offset]
                    if idx == one_time_offset:
                        fresh_vol_month_ot = eff_cum_ot
                    else:
                        prev_cum_ot = cum_raw[(idx - 1) - one_time_offset] if len(cum_raw) > ((idx - 1) - one_time_offset) else 0.0
                        fresh_vol_month_ot = eff_cum_ot - prev_cum_ot
            
            # Fresh Recurring (P&L): cumulative fresh volume (after recurring_offset) * recurring rate
            # SDU: Staggered recognition - half immediate, half delayed by 2 months
            # Others: cumulative fresh volume (after recurring_offset) * recurring rate
            fresh_rec_m = 0.0
            if include_fresh and idx >= recurring_offset and eff_cum_recurring > 0:
                if is_sdu:
                    # SDU: First tranche (immediate half) + Second tranche (delayed 2 months half)
                    # First tranche: current cumulative / 2 * rate
                    first_tranche = (eff_cum_recurring / 2.0) * FR
                    # Second tranche: cumulative from 2 months ago / 2 * rate
                    second_tranche = 0.0
                    if idx >= recurring_offset + 2 and len(cum_raw) > ((idx - 2) - recurring_offset):
                        cum_2_months_ago = cum_raw[(idx - 2) - recurring_offset]
                        second_tranche = (cum_2_months_ago / 2.0) * FR
                    fresh_rec_m = first_tranche + second_tranche
                else:
                    if getattr(payload, 'formula_recurring', None):
                        try:
                            fresh_rec_m = _safe_eval(payload.formula_recurring, {'volume': eff_cum_recurring, 'recurring_rate': FR}) if FR else 0.0
                        except HTTPException:
                            raise
                        except Exception:
                            fresh_rec_m = eff_cum_recurring * FR
                    else:
                        fresh_rec_m = eff_cum_recurring * FR

            if is_dark_fiber:
                fresh_rec_m *= pair_multiplier

            # Fresh One-Time (P&L):
            # - Small Cell: always zero
            # - Active: always zero
            # - OHFC: cumulative fresh volume (after one_time_offset) * one-time rate / 12
            # - SDU: cumulative fresh volume (after one_time_offset) * one-time rate / (lock_in * 12)
            # - Others: cumulative fresh volume (after one_time_offset) * one-time rate / 180
            pl_ot_m_fresh = 0.0
            if not is_small_cell and not is_active and include_fresh and idx >= one_time_offset and eff_cum_one_time > 0 and FO:
                if is_ohfc:
                    # OHFC: divide by 12
                    if getattr(payload, 'formula_one_time', None):
                        try:
                            yearly_ot_fresh = _safe_eval(payload.formula_one_time, {'total_volume_year': eff_cum_one_time, 'one_time_rate': FO, 'volume': eff_cum_one_time}) if FO else 0.0
                            pl_ot_m_fresh = (yearly_ot_fresh / 12.0) if yearly_ot_fresh else 0.0
                        except HTTPException:
                            raise
                        except Exception:
                            pl_ot_m_fresh = (eff_cum_one_time * FO / 12.0)
                    else:
                        pl_ot_m_fresh = (eff_cum_one_time * FO / 12.0)
                elif is_sdu:
                    denom = (lock_in_val * 12.0) if lock_in_val > 0 else 12.0
                    if getattr(payload, 'formula_one_time', None):
                        try:
                            yearly_ot_fresh = _safe_eval(payload.formula_one_time, {'total_volume_year': eff_cum_one_time, 'one_time_rate': FO, 'volume': eff_cum_one_time}) if FO else 0.0
                            pl_ot_m_fresh = (yearly_ot_fresh / denom) if yearly_ot_fresh else 0.0
                        except HTTPException:
                            raise
                        except Exception:
                            pl_ot_m_fresh = (eff_cum_one_time * FO / denom)
                    else:
                        pl_ot_m_fresh = (eff_cum_one_time * FO / denom)
                else:
                    if getattr(payload, 'formula_one_time', None):
                        try:
                            yearly_ot_fresh = _safe_eval(payload.formula_one_time, {'total_volume_year': eff_cum_one_time, 'one_time_rate': FO, 'volume': eff_cum_one_time}) if FO else 0.0
                            pl_ot_m_fresh = yearly_ot_fresh / DEN if yearly_ot_fresh else 0.0
                        except HTTPException:
                            raise
                        except Exception:
                            pl_ot_m_fresh = (eff_cum_one_time * FO / DEN)
                    else:
                        pl_ot_m_fresh = (eff_cum_one_time * FO / DEN)

            if is_dark_fiber:
                pl_ot_m_fresh *= pair_multiplier
            
            # For P&L: existing override completely overrides any calculations
            if existing_override_rec is not None and existing_override_ot is not None:
                # If we have override values, use them as-is (already spread across months)
                existing_ot_m_adjusted = existing_ot_m
                fresh_ot_m = pl_ot_m_fresh
            else:
                # Use calculated values
                existing_ot_m_adjusted = existing_ot_m
                fresh_ot_m = pl_ot_m_fresh
            
            # ===== CASHFLOW CALCULATIONS (ALL LOBS) =====
            # Offset-aware cashflow calculations apply to all LOBs
            # Existing Recurring Cashflow: base exit volume * recurring rate with offset = (fresh recurring offset - 1)
            existing_rec_cf_offset = max((recurring_offset or 0) - 1, 0)
            cashflow_existing_rec_m = E * ER if idx >= existing_rec_cf_offset else 0.0
            if idx < 4:
                print(f"[CASHFLOW-EXIST] month {idx}({m}): E={E}, ER={ER}, existing_rec_cf_offset={existing_rec_cf_offset}, cashflow_existing_rec_m={cashflow_existing_rec_m}")
            
            # Existing One-Time Cashflow: $0 (NO existing one-time cashflow)
            cashflow_existing_ot_m = 0.0
            
            # Fresh Recurring Cashflow: cumulative fresh volume * recurring rate (using UNSHIFTED cumulative - cashflow has its own offset in aggregation)
            cashflow_fresh_rec_m = 0.0
            if include_fresh and len(cum_raw) > idx:
                # Use unshifted cumulative (no recurring_offset applied)
                eff_cum_recurring_cf = cum_raw[idx]
                if eff_cum_recurring_cf > 0:
                    if getattr(payload, 'formula_recurring', None):
                        try:
                            cashflow_fresh_rec_m = _safe_eval(payload.formula_recurring, {'volume': eff_cum_recurring_cf, 'recurring_rate': FR}) if FR else 0.0
                        except:
                            cashflow_fresh_rec_m = eff_cum_recurring_cf * FR if FR else 0.0
                    else:
                        cashflow_fresh_rec_m = eff_cum_recurring_cf * FR if FR else 0.0
                    if idx < 4:
                        print(f"[CASHFLOW-CF] month {idx}({m}): eff_cum_recurring_cf={eff_cum_recurring_cf}, FR={FR}, cashflow_fresh_rec_m={cashflow_fresh_rec_m}")
            elif idx < 4:
                print(f"[CASHFLOW] month {idx}({m}): skipped - include_fresh={include_fresh}, eff_cum_recurring={eff_cum_recurring}, idx={idx}, recurring_offset={recurring_offset}")

            if is_dark_fiber:
                cashflow_fresh_rec_m *= pair_multiplier
            
            # Fresh One-Time Cashflow: fresh volume (non-cumulative) * one-time rate (after offset, NO amortization)
            # For Small Cell, Active, OHFC: this is always zero
            # For SDU and others: full amount upfront when customer connects
            cashflow_fresh_ot_m = 0.0
            if not is_small_cell and not is_active and not is_ohfc and include_fresh and fresh_vol_month_ot > 0 and FO and idx >= one_time_offset:
                # Cashflow one-time: full amount upfront, not amortized like P&L
                cashflow_fresh_ot_m = fresh_vol_month_ot * FO if FO else 0.0

            if is_dark_fiber:
                cashflow_fresh_ot_m *= pair_multiplier
            
            cashflow_ot_m = cashflow_existing_ot_m + cashflow_fresh_ot_m
            cashflow_rec_m = cashflow_existing_rec_m + cashflow_fresh_rec_m
            if idx < 4:
                print(f"[CASHFLOW-TOTAL] month {idx}({m}): cashflow_rec_m={cashflow_rec_m}, cashflow_ot_m={cashflow_ot_m}")

            rec_m = existing_rec_m + fresh_rec_m
            ot_m = existing_ot_m_adjusted + fresh_ot_m
            # debug removed
            # Round per month components before aggregation so row totals equal sum of displayed months
            rec_m_r = round(rec_m, DECIMALS)
            ot_m_r = round(ot_m, DECIMALS)
            total_m_r = round(rec_m_r + ot_m_r, DECIMALS)
            cashflow_rec_m_r = round(cashflow_rec_m, DECIMALS)
            cashflow_ot_m_r = round(cashflow_ot_m, DECIMALS)
            cashflow_total_m_r = round(cashflow_rec_m_r + cashflow_ot_m_r, DECIMALS)
            
            monthly_rec[m] = rec_m_r
            monthly_ot[m] = ot_m_r
            monthly_rev[m] = total_m_r
            # Store component splits for one-time
            monthly_existing_ot_map[m] = round(existing_ot_m_adjusted, DECIMALS)
            monthly_fresh_ot_map[m] = round(fresh_ot_m, DECIMALS)
            # Store cashflow components
            monthly_cashflow_rec_map[m] = cashflow_rec_m_r
            monthly_cashflow_ot_map[m] = cashflow_ot_m_r
            
            existing_recurring_total += existing_rec_m
            fresh_recurring_total += fresh_rec_m
            existing_one_time_total += existing_ot_m_adjusted
            fresh_one_time_total += fresh_ot_m
            total_recurring += rec_m_r
            total_one_time += ot_m_r

        # Round aggregated subtotals
        existing_recurring_total = round(existing_recurring_total, DECIMALS)
        fresh_recurring_total = round(fresh_recurring_total, DECIMALS)
        existing_one_time_total = round(existing_one_time_total, DECIMALS)
        fresh_one_time_total = round(fresh_one_time_total, DECIMALS)
        total_recurring = round(total_recurring, DECIMALS)
        total_one_time = round(total_one_time, DECIMALS)
        row_total = round(total_recurring + total_one_time, DECIMALS)
        for m in months:
            monthly_totals[m] += monthly_rev[m]
            monthly_recurring_totals[m] += monthly_rec[m]
            monthly_one_time_totals[m] += monthly_ot[m]
        grand_total += row_total
        dims = r.dimensions or {kv.split('=')[0]: kv.split('=')[1] for kv in key.split('|') if '=' in kv}
        rows.append(RevenueRow(
            dimensions=dims,
            monthly_revenue=monthly_rev,
            monthly_recurring=monthly_rec,
            monthly_one_time=monthly_ot,
            monthly_existing_one_time=monthly_existing_ot_map,
            monthly_fresh_one_time=monthly_fresh_ot_map,
            monthly_cashflow_recurring=monthly_cashflow_rec_map,
            monthly_cashflow_one_time=monthly_cashflow_ot_map,
            total_recurring=total_recurring,
            total_one_time=total_one_time,
            total_revenue=row_total,
            existing_recurring=existing_recurring_total,
            fresh_recurring=fresh_recurring_total,
            existing_one_time=existing_one_time_total,
            fresh_one_time=fresh_one_time_total
        ))
    # Final rounding for overall totals (already sums of rounded per-row values)
    for m in months:
        monthly_totals[m] = round(monthly_totals[m], DECIMALS)
        monthly_recurring_totals[m] = round(monthly_recurring_totals[m], DECIMALS)
        monthly_one_time_totals[m] = round(monthly_one_time_totals[m], DECIMALS)
    grand_total = round(grand_total, DECIMALS)

    # -------- OPEX CALCULATION --------
    opex_items_results: List[Dict[str, Any]] = []
    monthly_opex_totals: Dict[str, float] = {m:0.0 for m in months}
    total_opex = 0.0
    # Track passthrough (P&L + cash) for qualified site types/items
    passthrough_combo_pl: Dict[str, Dict[str, Dict[str, float]]] = {}
    # Build lookup for opex rates: item -> key -> (existing_rate,fresh_rate)
    opex_rate_map: Dict[str, Dict[str, Dict[str,float]]] = {}
    for entry in getattr(payload, 'opex_rates', []) or []:
        dims = entry.get('dimensions') or {}
        item_name = entry.get('item')
        if not item_name:
            continue
        k = _dim_key(dims)
        opex_rate_map.setdefault(item_name, {})[k] = {
            'existing_rate': float(entry.get('existing_rate') or 0),
            'fresh_rate': float(entry.get('fresh_rate') or 0)
        }
    include_fresh = getattr(payload, 'include_fresh_volumes', True)
    # Build override map: item -> months dict
    override_map: Dict[str, Dict[str,float]] = {}
    for ov in getattr(payload, 'existing_opex_overrides', []) or []:
        item_name = ov.get('item') if isinstance(ov, dict) else None
        months_obj = ov.get('months') if isinstance(ov, dict) else None
        fy_row = ov.get('fiscal_year') if isinstance(ov, dict) else None
        if not item_name or not months_obj:
            continue
        override_map[item_name] = {m: float(months_obj.get(m,0) or 0) for m in months}
    # Track per-combination per-item monthly P&L (pre-cashflow shift) to build cashflow later
    combo_item_pl: Dict[str, Dict[str, Dict[str, float]]] = {}  # item -> combo_key -> month -> value
    # New: per-opex-item cashflow offsets (additional to combination-level)
    item_cashflow_offset_map: Dict[str, int] = {}
    passthrough_inflow_offset_map: Dict[str, int] = {}
    passthrough_outflow_offset_map: Dict[str, int] = {}
    for item in getattr(payload, 'opex_items', []) or []:
        name = item.get('name')
        if not name:
            continue
        item_offset = int(item.get('fresh_offset_months') or 0)
        # Optional per-item cashflow offset (independent timing for cash actualization of this opex item)
        item_cashflow_offset = int(item.get('cashflow_offset_months') or 0)
        if item_cashflow_offset < 0:
            item_cashflow_offset = 0
        item_cashflow_offset_map[name] = item_cashflow_offset
        # Passthrough-specific offsets: inflow and outflow can differ
        pt_inflow_offset = int(item.get('passthrough_inflow_offset_months') or item_cashflow_offset)
        pt_outflow_offset = int(item.get('passthrough_outflow_offset_months') or item_cashflow_offset)
        if pt_inflow_offset < 0:
            pt_inflow_offset = 0
        if pt_outflow_offset < 0:
            pt_outflow_offset = 0
        passthrough_inflow_offset_map[name] = pt_inflow_offset
        passthrough_outflow_offset_map[name] = pt_outflow_offset
        is_passthrough_item = enable_small_cell_passthrough and str(name).strip().upper() in passthrough_items
        # Passthrough items ignore overrides (always recomputed per combo)
        has_override = False if is_passthrough_item else name in override_map
        # Start with override months if present, else zeros
        item_monthly = {m: (override_map[name][m] if has_override else 0.0) for m in months}
        # Iterate combinations for fresh + (existing if no override)
        for combo in payload.volumes:
            if combo.included is False:
                continue
            key = _dim_key(combo.dimensions)
            rates_obj = opex_rate_map.get(name, {}).get(key, {'existing_rate':0.0,'fresh_rate':0.0})
            existing_rate = rates_obj['existing_rate']
            fresh_rate = rates_obj['fresh_rate']
            E = 0.0
            if payload.base_exit_year:
                E = float(combo.exit_volumes.get(payload.base_exit_year, 0) or 0)
                # Decom combos reduce base exit volume
                if decom_map.get(key):
                    E = -E
            fy_months = combo.volumes.get(fy, {})
            raw_vols = [float(fy_months.get(m,0) or 0) for m in months]
            cum_raw = []
            run = 0.0
            for v in raw_vols:
                run += v
                cum_raw.append(run)
            # Prepare per-combo item store
            cit = combo_item_pl.setdefault(name, {}).setdefault(key, {m:0.0 for m in months})
            pt_store = None
            if is_passthrough_item:
                pt_store = passthrough_combo_pl.setdefault(name, {}).setdefault(key, {m:0.0 for m in months})
            # Use dimensions-based site type; fallback to explicit site_type attr if present
            site_type_val = _get_site_type(getattr(combo, 'dimensions', None)) or str(getattr(combo, 'site_type', '') or '')
            site_type_upper = site_type_val.strip().upper()
            for idx, m in enumerate(months):
                eff_cum = 0.0
                if include_fresh:
                    # Apply the same offset logic as revenue: check bounds before accessing
                    if idx >= item_offset and len(cum_raw) > (idx - item_offset):
                        eff_cum = cum_raw[idx - item_offset]
                    else:
                        eff_cum = 0.0
                existing_part = 0.0 if has_override else (E * existing_rate)
                fresh_part = eff_cum * fresh_rate if include_fresh else 0.0
                val = existing_part + fresh_part

                if is_passthrough_item and site_type_upper in passthrough_site_types:
                    pt_store[m] += val
                    monthly_passthrough_revenue[m] += val
                    monthly_passthrough_expense[m] += val
                    continue

                item_monthly[m] += val
                cit[m] += val
        # Round
        item_monthly = {m: round(v, DECIMALS) for m,v in item_monthly.items()}
        item_total = round(sum(item_monthly.values()), DECIMALS)
        for m in months:
            monthly_opex_totals[m] += item_monthly[m]
        total_opex += item_total
        opex_items_results.append({
            'name': name,
            'fresh_offset_months': item_offset,
            'cashflow_offset_months': item_cashflow_offset_map.get(name, 0),
            'override_applied': has_override,
            'monthly': item_monthly,
            'total': item_total
        })
    # Add passthrough P&L (Small Cell rent/electricity for specific site types)
    if enable_small_cell_passthrough and any(v != 0 for v in monthly_passthrough_revenue.values()):
        monthly_passthrough_revenue = {m: round(v, DECIMALS) for m,v in monthly_passthrough_revenue.items()}
        monthly_passthrough_expense = {m: round(v, DECIMALS) for m,v in monthly_passthrough_expense.items()}
        total_passthrough_revenue = round(sum(monthly_passthrough_revenue.values()), DECIMALS)
        total_passthrough_expense = round(sum(monthly_passthrough_expense.values()), DECIMALS)
        for m in months:
            monthly_totals[m] = round(monthly_totals[m] + monthly_passthrough_revenue[m], DECIMALS)
            monthly_opex_totals[m] += monthly_passthrough_expense[m]
        grand_total = round(grand_total + total_passthrough_revenue, DECIMALS)
        total_opex += total_passthrough_expense
        opex_items_results.append({
            'name': 'Passthrough Expense',
            'fresh_offset_months': 0,
            'cashflow_offset_months': 0,
            'override_applied': False,
            'monthly': monthly_passthrough_expense,
            'total': total_passthrough_expense,
            'site_types': sorted(list(passthrough_site_types)),
            'items': ['Electricity', 'Rent']
        })
    else:
        monthly_passthrough_revenue = {m:0.0 for m in months}
        monthly_passthrough_expense = {m:0.0 for m in months}
        total_passthrough_revenue = 0.0
        total_passthrough_expense = 0.0

    for m in months:
        monthly_opex_totals[m] = round(monthly_opex_totals[m], DECIMALS)
    total_opex = round(total_opex, DECIMALS)

    # -------- CASHFLOW (shifted) - TESTING DEBUG --------
    cash_recurring = {m:0.0 for m in months}
    cash_one_time = {m:0.0 for m in months}
    cash_passthrough = {m:0.0 for m in months}
    passthrough_cash_outflow = {m:0.0 for m in months}
    # Per-item shifted outflows
    cash_item_outflows: Dict[str, Dict[str,float]] = {name: {m:0.0 for m in months} for name in combo_item_pl.keys()}
    # Build helper maps for revenue rows by key
    rev_row_map = {}
    for r in rows:
        rev_row_map[_dim_key(r.dimensions)] = r
    print(f"[CF-DEBUG] rows list: {len(rows)} rows, checking monthly_cashflow_recurring...")
    for i, row in enumerate(rows):
        total_cf_rec = sum(row.monthly_cashflow_recurring.values()) if row.monthly_cashflow_recurring else 0
        print(f"[CF-DEBUG] row {i}: {row.dimensions}, total monthly_cashflow_recurring sum: {total_cf_rec}, dict: {row.monthly_cashflow_recurring}")
    for key, row in rev_row_map.items():
        cf_off_base = cashflow_offset_map.get(key, 0)
        cf_rec_off = cashflow_rec_offset_map.get(key)
        cf_ot_off = cashflow_ot_offset_map.get(key)
        # Fallback to base CF offset when specific offsets are not provided
        cf_rec_shift = cf_rec_off if cf_rec_off is not None else cf_off_base
        cf_ot_shift = cf_ot_off if cf_ot_off is not None else cf_off_base
        # Add uploaded existing cashflow directly (already timed; no shift)
        ex_cf_rec = existing_cashflow_rec_map.get(key)
        if ex_cf_rec:
            for m,v in ex_cf_rec.items():
                cash_recurring[m] += v
        ex_cf_ot = existing_cashflow_ot_map.get(key)
        if ex_cf_ot:
            for m,v in ex_cf_ot.items():
                cash_one_time[m] += v
        for idx, m in enumerate(months):
            # Recurring shift
            target_idx_rec = idx + cf_rec_shift
            if target_idx_rec < len(months):
                tm_rec = months[target_idx_rec]
                cf_val = row.monthly_cashflow_recurring.get(m, 0)
                cash_recurring[tm_rec] += cf_val
            # One-time shift
            target_idx_ot = idx + cf_ot_shift
            if target_idx_ot < len(months):
                tm_ot = months[target_idx_ot]
                cash_one_time[tm_ot] += row.monthly_cashflow_one_time.get(m, 0)

    # Passthrough inflow/outflow shifting (Small Cell rent/electricity)
    if enable_small_cell_passthrough:
        for item_name, combo_map in passthrough_combo_pl.items():
            pt_inflow_cf_off = passthrough_inflow_offset_map.get(item_name, 0)
            pt_outflow_cf_off = passthrough_outflow_offset_map.get(item_name, 0)
            for key, month_vals in combo_map.items():
                cf_off_combo = cashflow_offset_map.get(key, 0)
                # Inflow shift: combo offset + passthrough inflow offset
                inflow_cf_off = cf_off_combo + pt_inflow_cf_off
                # Outflow shift: combo offset + passthrough outflow offset
                outflow_cf_off = cf_off_combo + pt_outflow_cf_off
                for idx, m in enumerate(months):
                    # Inflow (cash_passthrough)
                    target_idx_inflow = idx + inflow_cf_off
                    if target_idx_inflow < len(months):
                        tm_inflow = months[target_idx_inflow]
                        shifted_val = round(month_vals[m], DECIMALS)
                        cash_passthrough[tm_inflow] += shifted_val
                    # Outflow (passthrough_cash_outflow)
                    target_idx_outflow = idx + outflow_cf_off
                    if target_idx_outflow < len(months):
                        tm_outflow = months[target_idx_outflow]
                        shifted_val = round(month_vals[m], DECIMALS)
                        passthrough_cash_outflow[tm_outflow] += shifted_val

    # Opex shifting per combination & item
    for item_name, combo_map in combo_item_pl.items():
        base_item_cf_off = item_cashflow_offset_map.get(item_name, 0)
        for key, month_vals in combo_map.items():
            cf_off_combo = cashflow_offset_map.get(key, 0)
            # Combined shift = combination-level cashflow offset + per-item offset
            cf_off = cf_off_combo + base_item_cf_off
            for idx, m in enumerate(months):
                target_idx = idx + cf_off
                if target_idx >= len(months):
                    continue
                tm = months[target_idx]
                cash_item_outflows[item_name][tm] += round(month_vals[m], DECIMALS)
    # Aggregate totals
    cash_gross = {m: round(cash_recurring[m] + cash_one_time[m] + cash_passthrough[m], DECIMALS) for m in months}
    cash_outflow_totals = {m:0.0 for m in months}
    for m in months:
        for item_name in cash_item_outflows.keys():
            cash_outflow_totals[m] += cash_item_outflows[item_name][m]
        cash_outflow_totals[m] += passthrough_cash_outflow[m]
        cash_outflow_totals[m] = round(cash_outflow_totals[m], DECIMALS)
    cash_net_operating = {m: round(cash_gross[m] - cash_outflow_totals[m], DECIMALS) for m in months}
    # Build per-item list
    cash_outflow_items_list = []
    for name, mv in cash_item_outflows.items():
        cash_outflow_items_list.append({
            'name': name,
            'cashflow_offset_months': item_cashflow_offset_map.get(name, 0),
            'monthly': {m: round(mv[m], DECIMALS) for m in months},
            'total': round(sum(mv.values()), DECIMALS)
        })
    if enable_small_cell_passthrough and any(v != 0 for v in passthrough_cash_outflow.values()):
        cash_outflow_items_list.append({
            'name': 'Passthrough Expense',
            'cashflow_offset_months': 0,
            'monthly': {m: round(passthrough_cash_outflow[m], DECIMALS) for m in months},
            'total': round(sum(passthrough_cash_outflow.values()), DECIMALS)
        })
    # Convert cashflow to millions for display
    cash_recurring = {m: round(v / 1_000_000, 2) for m, v in cash_recurring.items()}
    cash_one_time = {m: round(v / 1_000_000, 2) for m, v in cash_one_time.items()}
    cash_passthrough = {m: round(v / 1_000_000, 2) for m, v in cash_passthrough.items()}
    cash_gross = {m: round(v / 1_000_000, 2) for m, v in cash_gross.items()}
    cash_outflow_totals = {m: round(v / 1_000_000, 2) for m, v in cash_outflow_totals.items()}
    cash_net_operating = {m: round(v / 1_000_000, 2) for m, v in cash_net_operating.items()}
    
    # Update per-item outflows to millions
    for item in cash_outflow_items_list:
        item['monthly'] = {m: round(v / 1_000_000, 2) for m, v in item['monthly'].items()}
        item['total'] = round(item['total'] / 1_000_000, 2)
    
    total_cash_rec = round(sum(cash_recurring.values()), 2)
    total_cash_one = round(sum(cash_one_time.values()), 2)
    total_cash_gross = round(sum(cash_gross.values()), 2)
    total_cash_outflow = round(sum(cash_outflow_totals.values()), 2)
    total_cash_net = round(sum(cash_net_operating.values()), 2)

    # -------- CAPEX (refined: per-combination recognition & cash shifting) --------
    capex_rate_map: Dict[str, Dict[str, Dict[str,float]]] = {}
    for entry in getattr(payload, 'capex_rates', []) or []:
        dims = entry.get('dimensions') or {}
        item_name = entry.get('item')
        if not item_name:
            continue
        k = _dim_key(dims)
        capex_rate_map.setdefault(item_name, {})[k] = {
            'existing_rate': float(entry.get('existing_rate') or 0),
            'fresh_rate': float(entry.get('fresh_rate') or 0)
        }
    capex_override_map: Dict[str, Dict[str,float]] = {}
    for ov in getattr(payload, 'existing_capex_overrides', []) or []:
        item_name = ov.get('item') if isinstance(ov, dict) else None
        months_obj = ov.get('months') if isinstance(ov, dict) else None
        if not item_name or not months_obj:
            continue
        capex_override_map[item_name] = {m: float(months_obj.get(m,0) or 0) for m in months}
    capex_items_recognized: List[Dict[str, Any]] = []
    capex_combo_recog: Dict[str, Dict[str, Dict[str,float]]] = {}
    inventory_groups = {'First Time Inventory', 'Replacement Inventory'}
    for item in getattr(payload, 'capex_items', []) or []:
        iname = item.get('name')
        if not iname:
            continue
        igroup = item.get('group') or ''
        itype = item.get('type') or 'first_time'
        cf_off_item = int(item.get('cashflow_offset_months') or 0)
        is_refund = bool(item.get('is_refund')) or (itype == 'deposit_refund')
        is_advance_procurement = igroup in inventory_groups
        override_months = capex_override_map.get(iname)
        monthly_recog_total = {m:0.0 for m in months}
        for combo in payload.volumes:
            if combo.included is False:
                continue
            key = _dim_key(combo.dimensions)
            fy_months = combo.volumes.get(fy, {})
            raw_vols = [float(fy_months.get(m,0) or 0) for m in months]
            cum_raw = []
            run_v = 0.0
            for v in raw_vols:
                run_v += v
                cum_raw.append(run_v)
            # Recognition combo offset disabled (P&L CAPEX recognition deprecated, using cashflow only)
            eff_recog_off = 0
            rates_obj = capex_rate_map.get(iname, {}).get(key, {'existing_rate':0.0,'fresh_rate':0.0})
            existing_rate = rates_obj['existing_rate']
            fresh_rate = rates_obj['fresh_rate']
            E = 0.0
            if itype == 'replacement' and payload.base_exit_year:
                E = float(combo.exit_volumes.get(payload.base_exit_year, 0) or 0)
                # If this combo represents decommissioning, invert the exit base
                if decom_map.get(key):
                    E = -E
            combo_store = capex_combo_recog.setdefault(iname, {}).setdefault(key, {m:0.0 for m in months})
            for midx, m in enumerate(months):
                existing_part = 0.0
                if itype == 'replacement':
                    existing_part = (override_months.get(m,0.0) if override_months is not None else (E * existing_rate))
                
                # For inventory items, apply advance offset to volume lookup
                # For service items, use current month volume
                vol_offset = cf_off_item if is_advance_procurement else 0
                lookup_idx = midx + vol_offset if is_advance_procurement else midx
                
                # Safe offset logic: only access if index is valid
                if lookup_idx >= 0 and lookup_idx < len(cum_raw):
                    eff_cum = cum_raw[lookup_idx]
                else:
                    eff_cum = 0.0
                
                fresh_part = 0.0
                if itype in ('first_time','replacement','people'):
                    fresh_part = eff_cum * fresh_rate
                amount = (existing_part + fresh_part) * (-1 if is_refund else 1)
                combo_store[m] += amount
                monthly_recog_total[m] += amount
        monthly_recog_total = {m: round(v, DECIMALS) for m,v in monthly_recog_total.items()}
        capex_items_recognized.append({
            'name': iname,
            'group': igroup,
            'type': itype,
            'cashflow_offset_months': cf_off_item,
            'is_refund': is_refund,
            'monthly': monthly_recog_total,
            'total': round(sum(monthly_recog_total.values()), DECIMALS)
        })
    # Cash shift for service items only (inventory items already have offset applied at recognition)
    inventory_groups = {'First Time Inventory', 'Replacement Inventory'}
    capex_cash_map: Dict[str, Dict[str,float]] = {}
    for item in getattr(payload, 'capex_items', []) or []:
        iname = item.get('name')
        if not iname:
            continue
        igroup = item.get('group') or ''
        item_cf_off = int(item.get('cashflow_offset_months') or 0)
        is_advance_procurement = igroup in inventory_groups
        item_cash_months = {m:0.0 for m in months}
        combo_map = capex_combo_recog.get(iname, {})
        for combo in payload.volumes:
            if combo.included is False:
                continue
            key = _dim_key(combo.dimensions)
            combo_cf_off = int(getattr(combo, 'capex_cashflow_offset_months', 0) or 0)
            cf_off = combo_cf_off + item_cf_off
            month_vals = combo_map.get(key)
            if not month_vals:
                continue
            # For inventory items: offset already applied at recognition, copy directly
            # For service items: apply delay offset (pay AFTER transaction)
            if is_advance_procurement:
                for m in months:
                    item_cash_months[m] += round(month_vals[m], DECIMALS)
            else:
                for midx, m in enumerate(months):
                    target_idx = midx + cf_off
                    if target_idx >= len(months):
                        continue
                    tm = months[target_idx]
                    item_cash_months[tm] += round(month_vals[m], DECIMALS)
        capex_cash_map[iname] = item_cash_months
    # Group CAPEX cashflow by group header
    group_headers = [
        'First Time Inventory',
        'First Time Capex',
        'Replacement Inventory',
        'Replacement Capex',
        'Capex People',
        'ROW Deposit',
        'Deposit Refund'
    ]
    capex_group_cash = {g: {m: 0.0 for m in months} for g in group_headers}
    capex_group_total = {g: 0.0 for g in group_headers}
    for item in getattr(payload, 'capex_items', []):
        iname = item.get('name')
        igroup = item.get('group')
        if igroup in group_headers:
            mv = capex_cash_map.get(iname, {})
            for m in months:
                capex_group_cash[igroup][m] += mv.get(m, 0.0)
            capex_group_total[igroup] += sum(mv.values())
    # Provide overall monthly CAPEX total as before
    monthly_capex_totals = {m:0.0 for m in months}
    for mv in capex_cash_map.values():
        for m in months:
            monthly_capex_totals[m] += mv[m]
    monthly_capex_totals = {m: round(v, DECIMALS) for m,v in monthly_capex_totals.items()}
    total_capex = round(sum(monthly_capex_totals.values()), DECIMALS)
    # Convert to millions for display
    monthly_net_cashflow = {m: round((cash_net_operating[m] - monthly_capex_totals[m]) / 1_000_000, 2) for m in months}
    running_cum = 0.0
    monthly_cum_net_cashflow: Dict[str,float] = {}
    peak_funding = 0.0
    for m in months:
        running_cum += monthly_net_cashflow[m]
        monthly_cum_net_cashflow[m] = round(running_cum, 2)
        if running_cum < peak_funding:
            peak_funding = running_cum
    total_net_cashflow = round(sum(monthly_net_cashflow.values()), 2)
    peak_funding = round(peak_funding, 2)

    return RevenueCalcResponse(
        fiscal_year=fy,
        months=months,
        rows=rows,
        monthly_totals=monthly_totals,
        monthly_recurring_totals=monthly_recurring_totals,
        monthly_one_time_totals=monthly_one_time_totals,
        monthly_passthrough_revenue=monthly_passthrough_revenue,
        monthly_passthrough_expense=monthly_passthrough_expense,
        total_revenue=grand_total,
        total_passthrough_revenue=total_passthrough_revenue,
        total_passthrough_expense=total_passthrough_expense,
        opex_items=opex_items_results,
        monthly_opex_totals=monthly_opex_totals,
        total_opex=total_opex,
        monthly_cash_recurring_inflow=cash_recurring,
        monthly_cash_one_time_inflow=cash_one_time,
        monthly_cash_passthrough_inflow=cash_passthrough,
        monthly_cash_gross_inflow=cash_gross,
        monthly_cash_outflow_items=cash_outflow_items_list,
        monthly_cash_outflow_totals=cash_outflow_totals,
        monthly_cash_net_operating=cash_net_operating,
        total_cash_recurring_inflow=total_cash_rec,
        total_cash_one_time_inflow=total_cash_one,
        total_cash_gross_inflow=total_cash_gross,
        total_cash_outflow=total_cash_outflow,
        total_cash_net_operating=total_cash_net,
        capex_items=capex_items_recognized,
        monthly_capex_totals=monthly_capex_totals,
        total_capex=total_capex,
        monthly_net_cashflow=monthly_net_cashflow,
        monthly_cum_net_cashflow=monthly_cum_net_cashflow,
        peak_funding=peak_funding,
        total_net_cashflow=total_net_cashflow,
        capex_group_cash=capex_group_cash,
        capex_group_total=capex_group_total
    )


# Register handlers here: map the payload.lob value to a handler function.
LOB_HANDLERS = {
    'FTTH': _revenue_calc_core,
    'Small Cell': _handler_small_cell,
    'Active': _handler_active,
    'SDU': _handler_sdu,
    'OHFC': _handler_ohfc,
    'Dark Fiber': _handler_dark_fiber,
    'Co Build': _handler_co_build,
}


if os.path.exists(frontend_dist_path):
    app.mount("/", StaticFiles(directory=frontend_dist_path, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )