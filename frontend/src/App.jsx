import React, { useEffect, useState } from 'react';
import { fetchHealth, saveLob, loadLobData, calculateRevenue } from './api';
import OpexItems from './OpexItems';

const FISCAL_MONTHS = ["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"];

function derivePriorYears(fy) {
  // Expect format FY24-25
  if(!/^FY\d{2}-\d{2}$/.test(fy)) return [];
  const start = parseInt(fy.substring(2,4),10); // 24
  const py1Start = start-1; const py2Start = start-2;
  const fmt = (s)=> `FY${String(s).padStart(2,'0')}-${String((s+1)%100).padStart(2,'0')}`;
  return [fmt(py1Start), fmt(py2Start)];
}

function VolumeDesignFlow() {
  // Step control (simplified: 1=select FY, 2=after combos generation proceed to exit, 3=exit vols, 4=monthly)
  const [step, setStep] = useState(1); // we will keep editing of dimensions always visible after FY locked
  const [fiscalYearInput, setFiscalYearInput] = useState('FY25-26');
  const [fiscalYear, setFiscalYear] = useState(null);
  const [priorYears, setPriorYears] = useState([]);
  // LOB selection (Option A: only FTTH implemented; others Coming Soon)
  const LOBS = ['FTTH','Small Cell','SDU','Dark Fiber','OHFC','Active'];
  const [lob, setLob] = useState('');

  // Dimension data (editable anytime after FY set)
  const [customers, setCustomers] = useState(['Airtel']);
  const [newCustomer, setNewCustomer] = useState('');
  const [newCircle, setNewCircle] = useState('');
  const [circles, setCircles] = useState(['SOBO']);
  const SITE_TYPES = ['LPSC','HPSC','Lite Site'];
  const [siteTypes, setSiteTypes] = useState(SITE_TYPES);
  const [newSiteType, setNewSiteType] = useState('');
  const FIXED_TYPES = ['RFAI','Decom'];
  const [extraLevels, setExtraLevels] = useState([]); // [{name:'Tower', values:['PH1','TPF']}]
  const [newLevelName, setNewLevelName] = useState('');
  const [newLevelValue, setNewLevelValue] = useState('');

  // Generated combinations
  const [combos, setCombos] = useState([]); // {dimensions:{customer, circle, type, ...extra}, included, volumes, exit_volumes, fresh_offset_months, cashflow_offset_months}
  const [dimensionDirty, setDimensionDirty] = useState(false); // indicates lists changed after combos generated
  const [lastDimSignature, setLastDimSignature] = useState('');
  const [combosCollapsed, setCombosCollapsed] = useState(false);

  const initMonths = Object.fromEntries(FISCAL_MONTHS.map(m=>[m,0]));

  // Helpers
  const lockFiscalYear = () => {
    const fy = fiscalYearInput.trim();
    if(!/^FY\d{2}-\d{2}$/.test(fy)) return;
    setFiscalYear(fy);
    setPriorYears(derivePriorYears(fy));
    setStep(2); // move to LOB selection
  };

  // Reset all modeling state (called when changing LOB or FY)
  const resetModelState = () => {
    setCustomers(['Airtel']);
    setNewCustomer('');
    setCircles(['SOBO']);
    setNewCircle('');
    setExtraLevels([]);
    setNewLevelName('');
    setNewLevelValue('');
    setCombos([]);
    setDimensionDirty(false);
    setLastDimSignature('');
    setCombosCollapsed(false);
    setVolumeResult(null);
    setRevenueResult(null);
    setRates({});
    setFormulaRecurring('volume * recurring_rate');
    setFormulaOneTime('total_volume_year * one_time_rate');
    setBaseExitYear('');
  // per-combination fresh offsets reset implicitly via combos regeneration
    setIncludeFresh(true);
    setUseUploadExisting(false);
    setUploadInfo(null);
    setOpexItems([]);
    setNewOpexName('');
    setOpexRates({});
    setProvisionPct(0);
    setCustomerPenaltyPct(0);
    setVendorPenaltyPct(0);
  };

  // Dynamic dimension for circle/siteType
  const [newDimension, setNewDimension] = useState('');
  const isSmallCell = lob === 'Small Cell';
  const dimensionList = isSmallCell ? siteTypes : circles;
  const setDimensionList = isSmallCell ? setSiteTypes : setCircles;
  const addDimension = () => {
    if(newDimension && !dimensionList.includes(newDimension)) {
      setDimensionList([...dimensionList, newDimension]);
      markDirty();
    }
    setNewDimension('');
  };
  const removeDimension = (d) => {
    setDimensionList(dimensionList.filter(x => x !== d));
    markDirty();
  };
  const hasModelData = () => {
    if(combos.length>0) return true;
    if(opexItems.length>0) return true;
    if(Object.keys(rates).length>0) return true;
    if(provisionPct || customerPenaltyPct || vendorPenaltyPct) return true;
    // Check if any non-default dimension edits
    if(customers.length>1 || dimensionList.length>1 || extraLevels.length>0) return true;
    return false;
  };

  const handleLobChange = async (newLob) => {
    // If selecting same LOB, just proceed
    if(newLob === lob){
      if(newLob) setStep(3);
      return;
    }
    // If we have unsaved FTTH data (or any current modeling data), save it to server before changing
    try{
      if(lob && hasModelData()){
        // Build snapshot of current modeling state
        const snapshot = {
          fiscal_year: fiscalYear,
          prior_years: priorYears,
          lob: lob,
          combos: combos,
          rates: rates,
          formula_recurring: formulaRecurring,
          formula_one_time: formulaOneTime,
          base_exit_year: baseExitYear,
          include_fresh: includeFresh,
          opex_items: opexItems,
          opex_rates: opexRates,
          capex_items: capexItems,
          capex_rates: capexRates,
          existing_opex_overrides: existingOpexOverrides,
          existing_capex_overrides: existingCapexOverrides,
          provision_pct: provisionPct,
          customer_penalty_pct: customerPenaltyPct,
          vendor_penalty_pct: vendorPenaltyPct
        };
        setLoading(true);
        await saveLob(lob, snapshot);
        setLoading(false);
      }
    } catch(err){ setLoading(false); alert('Failed to save current LOB snapshot: '+ (err.message||err)); }

  // Reset current modeling state and set new LOB
  resetModelState();
    setLob(newLob);

    // If there's a saved snapshot for the newly selected LOB, load and restore it
    if(newLob){
      setLoading(true);
      try{
        const loaded = await loadLobData(newLob);
        if(loaded){
          // restore fields defensively
          if(loaded.fiscal_year) { setFiscalYear(loaded.fiscal_year); setPriorYears(derivePriorYears(loaded.fiscal_year)); }
          if(loaded.combos) setCombos(loaded.combos);
          if(loaded.rates) setRates(loaded.rates);
          if(loaded.formula_recurring) setFormulaRecurring(loaded.formula_recurring);
          if(loaded.formula_one_time) setFormulaOneTime(loaded.formula_one_time);
          if(typeof loaded.include_fresh !== 'undefined') setIncludeFresh(loaded.include_fresh);
          if(loaded.opex_items) setOpexItems(loaded.opex_items);
          if(loaded.opex_rates) setOpexRates(loaded.opex_rates);
          if(loaded.capex_items) setCapexItems(loaded.capex_items);
          if(loaded.capex_rates) setCapexRates(loaded.capex_rates);
          if(loaded.existing_opex_overrides) setExistingOpexOverrides(loaded.existing_opex_overrides);
          if(loaded.existing_capex_overrides) setExistingCapexOverrides(loaded.existing_capex_overrides);
          if(typeof loaded.provision_pct !== 'undefined') setProvisionPct(loaded.provision_pct);
          if(typeof loaded.customer_penalty_pct !== 'undefined') setCustomerPenaltyPct(loaded.customer_penalty_pct);
          if(typeof loaded.vendor_penalty_pct !== 'undefined') setVendorPenaltyPct(loaded.vendor_penalty_pct);
        }
      } catch(err){ alert('Failed to load saved LOB snapshot: '+(err.message||err)); }
      setLoading(false);
      setStep(3);
    } else {
      // If user cleared selection, show LOB chooser (step 2)
      setStep(2);
    }
  };

  const markDirty = () => { if(combos.length>0) setDimensionDirty(true); };
  const addCustomer = () => { if(newCustomer && !customers.includes(newCustomer)) { setCustomers([...customers,newCustomer]); markDirty(); } setNewCustomer(''); };
  const removeCustomer = (c)=> { setCustomers(customers.filter(x=> x!==c)); markDirty(); };
  // (removed duplicate isSmallCell, dimensionList, setDimensionList, addDimension, removeDimension)

  // Extra levels CRUD
  const addExtraLevel = () => {
    const name = newLevelName.trim();
    if(!name) return; if(extraLevels.some(l=> l.name.toLowerCase()===name.toLowerCase())) return;
    setExtraLevels([...extraLevels, { name, values: [] }]);
    setNewLevelName('');
    markDirty();
  };
  const addValueToLevel = (levelIdx) => {
    const v = newLevelValue.trim();
    if(!v) return;
    setExtraLevels(levels => {
      const copy=[...levels];
      const lvl={...copy[levelIdx]};
  if(!lvl.values.includes(v)) { lvl.values=[...lvl.values,v]; markDirty(); }
      copy[levelIdx]=lvl; return copy;
    });
    setNewLevelValue('');
  };
  const removeValue = (levelIdx, val) => {
    setExtraLevels(levels=> {
      const copy=[...levels];
      const lvl={...copy[levelIdx], values: copy[levelIdx].values.filter(x=> x!==val)}; copy[levelIdx]=lvl; return copy;
    });
    markDirty();
  };
  const deleteLevel = (idx) => { setExtraLevels(extraLevels.filter((_,i)=> i!==idx)); markDirty(); };

  // Generate combinations (cartesian product)
  const comboKey = (dimMap) => Object.entries(dimMap).sort((a,b)=> a[0].localeCompare(b[0])).map(([k,v])=> `${k}=${v}`).join('|');
  const generateCombos = (preserve=true) => {
    const extras = extraLevels.filter(l=> l.values.length>0);
    let base = [];
    if(lob === 'Small Cell') {
      for(const cust of customers){
        for(const siteType of siteTypes){
          for(const type of ['RFAI','Decom','FDD upgrades','BB upgrades']){
            // Only allow upgrades for HPSC and Lite Site
            if((type === 'FDD upgrades' || type === 'BB upgrades') && siteType === 'LPSC') continue;
            base.push({customer:cust,siteType,type,pricepoint:'',upgradeType: (type === 'FDD upgrades' || type === 'BB upgrades') ? type : ''});
          }
        }
      }
    } else {
      for(const cust of customers){
        for(const circle of circles){
          for(const type of FIXED_TYPES){ base.push({customer:cust,circle,type}); }
        }
      }
    }
    let expanded = base.map(o=> ({...o}));
    for(const lvl of extras){
      const next=[]; for(const row of expanded){ for(const val of lvl.values){ next.push({...row, [lvl.name]: val}); } } expanded=next;
    }
    const oldMap = new Map();
    if(preserve){ combos.forEach(c=> oldMap.set(comboKey(c.dimensions), c)); }
    const comboObjs = expanded.map(dimMap => {
      const key = comboKey(dimMap);
      if(oldMap.has(key)) { return { ...oldMap.get(key) }; }
      return { dimensions: dimMap, included: true, volumes:{}, exit_volumes:{}, fresh_offset_months:0, cashflow_offset_months:0, capex_offset_months:0, capex_cashflow_offset_months:0 };
    });
    setCombos(comboObjs);
    setDimensionDirty(false);
    setLastDimSignature(JSON.stringify({customers:[...customers].sort(), siteTypes:[...siteTypes].sort(), circles:[...circles].sort(), extras: extras.map(e=> ({name:e.name, values:[...e.values].sort()}))}));
    if(step < 3) setStep(3);
  };

  const toggleInclude = (idx) => setCombos(list=> list.map((c,i)=> i===idx? {...c, included: !c.included}: c));

  const ensureFy = (combo) => { if(!combo.volumes[fiscalYear]) combo.volumes[fiscalYear] = {...initMonths}; };
  const updateMonth = (idx, month, value) => {
    setCombos(list=> list.map((c,i)=> {
      if(i!==idx) return c; const copy={...c, volumes:{...c.volumes}}; ensureFy(copy); copy.volumes[fiscalYear] = {...copy.volumes[fiscalYear], [month]: Number(value)}; return copy; }));
  };
  const updateExit = (idx, year, value) => {
    setCombos(list=> list.map((c,i)=> i===idx? {...c, exit_volumes:{...c.exit_volumes, [year]: Number(value)}}: c));
  };

  const [volumeResult,setVolumeResult]=useState(null); // result of volume aggregation
  const [revenueResult,setRevenueResult]=useState(null); // result of revenue calculation
  const [loading,setLoading]=useState(false); const [error,setError]=useState(null);
  // Rates state
  const [rates, setRates] = useState({}); // key -> {recurring_rate, one_time_rate}
  const [formulaRecurring, setFormulaRecurring] = useState('volume * recurring_rate');
  // Leave formulaOneTime empty by default so backend uses its built-in spread logic
  const [formulaOneTime, setFormulaOneTime] = useState('');
  const [baseExitYear, setBaseExitYear] = useState('');
  // Removed global freshOffsetMonths; now per-combination fresh_offset_months
  const [includeFresh, setIncludeFresh] = useState(true); // Option B: ON means include fresh volumes
  const [useUploadExisting, setUseUploadExisting] = useState(false);
  const [uploadInfo, setUploadInfo] = useState(null);
  // Opex
  const DEFAULT_OPEX_ITEMS = [
    'Rent',
    'Electricity',
    'People Cost',
    'Network O&M',
    'Warehouse Rental',
    'Operational Others',
    'Travelling & Sales Promotions',
    'Freight Internal & other direct',
    'Insurance',
    'Passthrough Expense',
    'Loss on Sale of Scrap',
    'Software & IT'
  ];
  const [opexItems, setOpexItems] = useState(DEFAULT_OPEX_ITEMS.map(name => ({ name })));
  const [newOpexName, setNewOpexName] = useState('');
  const [opexRates, setOpexRates] = useState({}); // key -> { itemName: {existing_rate, fresh_rate} }
  // Existing Opex overrides (global per item, replaces existing portion only)
  const [useUploadOpexExisting, setUseUploadOpexExisting] = useState(false);
  const [existingOpexOverrides, setExistingOpexOverrides] = useState({}); // item -> {month:value}
  const [opexUploadInfo, setOpexUploadInfo] = useState(null);
  // P&L percentage assumptions
  const [provisionPct, setProvisionPct] = useState(0); // % of Gross Revenue
  const [customerPenaltyPct, setCustomerPenaltyPct] = useState(0); // % of Net Revenue (cost)
  const [vendorPenaltyPct, setVendorPenaltyPct] = useState(0); // % of Net Revenue (refund / benefit)
  // CAPEX state
  const CAPEX_GROUPS = ['First Time Inventory','First Time Capex','Capex People','Replacement Inventory','Replacement Capex','ROW Deposit','Deposit Refund'];
  const DEFAULT_CAPEX_ITEMS = [
    // First Time Inventory
    { name: 'Battery, SMPS & Cabinet - First Time', group: 'First Time Inventory', type: 'first_time', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'Pole - First Time', group: 'First Time Inventory', type: 'first_time', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'Fiber - First Time', group: 'First Time Inventory', type: 'first_time', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'Antenna - First Time', group: 'First Time Inventory', type: 'first_time', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'Others - First Time', group: 'First Time Inventory', type: 'first_time', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    // First Time Capex
    { name: 'Acquisition - First Time', group: 'First Time Capex', type: 'first_time', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'IBD - First Time', group: 'First Time Capex', type: 'first_time', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'MC & EB Permission - First Time', group: 'First Time Capex', type: 'first_time', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'Other Services - First Time', group: 'First Time Capex', type: 'first_time', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    // Replacement Inventory
    { name: 'Battery, SMPS & Cabinet - Replacement', group: 'Replacement Inventory', type: 'replacement', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'Pole - Replacement', group: 'Replacement Inventory', type: 'replacement', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'Fiber - Replacement', group: 'Replacement Inventory', type: 'replacement', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'Antenna - Replacement', group: 'Replacement Inventory', type: 'replacement', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'Others - Replacement', group: 'Replacement Inventory', type: 'replacement', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    // Replacement Capex
    { name: 'Acquisition - Replacement', group: 'Replacement Capex', type: 'replacement', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'IBD - Replacement', group: 'Replacement Capex', type: 'replacement', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'MC & EB Permission - Replacement', group: 'Replacement Capex', type: 'replacement', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    { name: 'Other Services - Replacement', group: 'Replacement Capex', type: 'replacement', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    // Capex People
    { name: 'Capex People', group: 'Capex People', type: 'people', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    // ROW Deposit
    { name: 'ROW Deposit', group: 'ROW Deposit', type: 'deposit_refund', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: false },
    // Deposit Refund
    { name: 'Deposit Refund', group: 'Deposit Refund', type: 'deposit_refund', recognition_offset_months: 0, cashflow_offset_months: 0, is_refund: true }
  ];
  const [capexItems, setCapexItems] = useState(DEFAULT_CAPEX_ITEMS);
  const [newCapexName, setNewCapexName] = useState('');
  const [newCapexGroup, setNewCapexGroup] = useState('First Time Capex');
  const [capexRates, setCapexRates] = useState({}); // key -> { itemName: {existing_rate, fresh_rate} }
  const [existingCapexOverrides, setExistingCapexOverrides] = useState({}); // placeholder for future upload

  const dimensionOrder = ['customer','circle','type', ...extraLevels.filter(l=> l.values.length>0).map(l=> l.name)];
  const hasReplacementCapex = capexItems.some(it => it.type === 'replacement');

  const downloadTemplate = async () => {
    const dims = dimensionOrder.join(',');
    const resp = await fetch(`/api/template/existing?dims=${encodeURIComponent(dims)}`);
    const data = await resp.json();
    const blob = new Blob([data.content], {type:'text/csv'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = data.filename || 'existing_revenue_template.csv';
    a.click();
  };
  const downloadOpexTemplate = async () => {
    const resp = await fetch('/api/template/opex_existing');
    const data = await resp.json();
    const blob = new Blob([data.content], {type:'text/csv'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = data.filename || 'existing_opex_template.csv';
    a.click();
  };

  const handleExistingUpload = async (e) => {
    const file = e.target.files[0];
    if(!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const resp = await fetch('/api/upload/existing', { method:'POST', body: fd });
      if(!resp.ok){
        let msg = 'Upload parse failed';
        try {
          const errJson = await resp.json();
          if(errJson && errJson.detail){
            if(typeof errJson.detail === 'string') msg = errJson.detail;
            else if(errJson.detail.errors){
              const errs = errJson.detail.errors;
              const shown = errs.slice(0,10).join('\n');
              msg = `Upload validation errors (showing ${Math.min(errs.length,10)} of ${errs.length}):\n${shown}`;
            }
          }
        } catch(_) { /* ignore parse failure */ }
        alert(msg);
        return;
      }
      const data = await resp.json();
      // Validate all uploaded combinations exist; otherwise hard error
      const comboKeys = new Set(combos.map(c => Object.entries(c.dimensions).sort((a,b)=> a[0].localeCompare(b[0])).map(([k,v])=> k+"="+v).join('|')));
      const missing = [];
      data.rows.forEach(r => {
        const dimMap = { customer: r.dimensions.Customer, circle: r.dimensions.Circle, type: r.dimensions.Type };
        const key = Object.entries(dimMap).sort((a,b)=> a[0].localeCompare(b[0])).map(([k,v])=> k+"="+v).join('|');
        if(!comboKeys.has(key)) missing.push(Object.values(dimMap).join(' / '));
      });
      if(missing.length){
        alert('Upload error: combinations not found in current design: '+missing.join('; '));
        return;
      }
      // Merge aggregated rows
      setCombos(list => list.map(c => {
        const matches = data.rows.filter(r => r.dimensions.Customer === c.dimensions.customer && r.dimensions.Circle === c.dimensions.circle && r.dimensions.Type === c.dimensions.type);
        if(!matches.length) return c;
        let updated = { ...c, exit_volumes: { ...c.exit_volumes }, existing_revenue: { ...(c.existing_revenue||{}) } };
        matches.forEach(r => {
          const fy = r.fiscal_year;
            updated.exit_volumes[fy] = (updated.exit_volumes[fy]||0) + r.exit_volume; // sum in case of multiple uploads
            updated.existing_revenue[fy] = { recurring: r.recurring, one_time: r.one_time };
        });
        return updated;
      }));
      setUploadInfo({ rows: data.rows.length });
    } catch(err){
      alert(err.message);
    } finally {
      e.target.value='';
    }
  };
  const handleOpexExistingUpload = async (e) => {
    const file = e.target.files[0];
    if(!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const resp = await fetch('/api/upload/opex_existing', { method:'POST', body: fd });
      if(!resp.ok){
        let msg = 'Opex upload parse failed';
        try { const errJson = await resp.json(); if(errJson && errJson.detail){ if(typeof errJson.detail==='string') msg = errJson.detail; else if(errJson.detail.errors){ const errs = errJson.detail.errors; msg = `Opex upload errors (showing first 10):\n${errs.slice(0,10).join('\n')}`; } } } catch(_){}
        alert(msg); return;
      }
      const data = await resp.json();
      const rows = data.rows||[];
      const mismatches = rows.filter(r=> r.fiscal_year !== fiscalYear);
      if(mismatches.length && !window.confirm(`Some rows (${mismatches.length}) have Fiscal Year differing from ${fiscalYear}. Ignore those rows?`)){
        return;
      }
      const usable = rows.filter(r=> r.fiscal_year === fiscalYear);
      const map = {};
      usable.forEach(r=> { map[r.item] = r.months; });
      setExistingOpexOverrides(map);
      setOpexUploadInfo({ rows: usable.length });
    } catch(err){
      alert(err.message);
    } finally { e.target.value=''; }
  };

  const runRevenueCalc = async () => {
  setLoading(true); setError(null); setRevenueResult(null);
        try {
          const dimensions = ['customer','circle','type', ...extraLevels.filter(l=> l.values.length>0).map(l=> l.name)];
          // Build volume combinations (only included)
          const included = combos.filter(c=> c.included!==false);
          const volumePayload = included.map(c=> ({
            dimensions: c.dimensions,
            volumes: c.volumes,
            exit_volumes: c.exit_volumes,
            existing_revenue: c.existing_revenue || {},
            included:true,
            // Ensure offsets are numeric (coerce strings like '02' -> 2)
            fresh_offset_months: Number(c.fresh_offset_months) || 0,
            cashflow_offset_months: Number(c.cashflow_offset_months) || 0,
            capex_offset_months: Number(c.capex_offset_months) || 0,
            capex_cashflow_offset_months: Number(c.capex_cashflow_offset_months) || 0
          }));
          const ratePayload = included.map(c=> {
            const key = Object.values(c.dimensions).join('|');
            const r = rates[key] || {recurring_rate:0, one_time_rate:0, existing_recurring_rate:0, existing_one_time_rate:0};
            return { dimensions: c.dimensions, recurring_rate: r.recurring_rate||0, one_time_rate: r.one_time_rate||0, existing_recurring_rate: r.existing_recurring_rate||0, existing_one_time_rate: r.existing_one_time_rate||0, one_time_month: null };
          });
          // Always use default OPEX items for backend calculation
          const opexItemsToSend = DEFAULT_OPEX_ITEMS.map(name => ({ name }));
          const opexRatesPayload = [];
          included.forEach(c => {
            const key = Object.values(c.dimensions).join('|');
            const itemMap = opexRates[key] || {};
            opexItemsToSend.forEach(it => {
              const rset = itemMap[it.name] || {existing_rate:0, fresh_rate:0};
              opexRatesPayload.push({ dimensions: c.dimensions, item: it.name, existing_rate: rset.existing_rate||0, fresh_rate: rset.fresh_rate||0 });
            });
          });
          // CAPEX rates payload
          const capexRatesPayload = [];
          included.forEach(c => {
            const key = Object.values(c.dimensions).join('|');
            const itemMap = capexRates[key] || {};
            capexItems.forEach(it => {
              const rset = itemMap[it.name] || {existing_rate:0, fresh_rate:0};
              capexRatesPayload.push({ dimensions: c.dimensions, item: it.name, existing_rate: rset.existing_rate||0, fresh_rate: rset.fresh_rate||0 });
            });
          });
          const existingOpexOverridesArr = Object.entries(existingOpexOverrides).map(([item, months])=> ({ item, fiscal_year: fiscalYear, months }));
          const existingCapexOverridesArr = Object.entries(existingCapexOverrides).map(([item, months])=> ({ item, fiscal_year: fiscalYear, months }));
          const body = { lob, fiscal_year: fiscalYear, volumes: volumePayload, rates: ratePayload, formula_recurring: formulaRecurring || null, formula_one_time: formulaOneTime || null, base_exit_year: baseExitYear || null, include_fresh_volumes: includeFresh, opex_items: opexItems, opex_rates: opexRatesPayload, capex_items: capexItems, capex_rates: capexRatesPayload };
          if(existingOpexOverridesArr.length) body.existing_opex_overrides = existingOpexOverridesArr;
          if(existingCapexOverridesArr.length) body.existing_capex_overrides = existingCapexOverridesArr;
          console.log('Revenue calculation payload:', body);
          console.log('Volume payload offsets:', volumePayload.map(v => ({ dims: v.dimensions, fresh_offset: v.fresh_offset_months })));
          const resp = await fetch('/api/revenue/calculate', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
          if(!resp.ok) {
            let errorMsg = 'Revenue API error';
            try {
              const errJson = await resp.json();
              if(errJson && errJson.detail) {
                if(typeof errJson.detail === 'string') errorMsg = errJson.detail;
                else if(errJson.detail.errors) errorMsg = errJson.detail.errors.join('\n');
              }
            } catch(e) {}
            throw new Error(errorMsg);
          }
          const rev = await resp.json();
          setRevenueResult(rev);
        } catch(e){ setError(e.message);} finally { setLoading(false);} }
  const calculate = async () => {
  setError(null); setLoading(true); setVolumeResult(null);
    try {
      const dimensions = ['customer','circle','type', ...extraLevels.filter(l=> l.values.length>0).map(l=> l.name)];
  const payload = { lob, fiscal_year: fiscalYear, prior_years: priorYears, dimensions, combinations: combos };
      const r = await fetch('/api/volume/multiyear/dynamic', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      if(!r.ok) throw new Error('API error');
  setVolumeResult(await r.json());
    } catch(e){ setError(e.message);} finally { setLoading(false);} };

  // Detect dimension changes (simple signature diff) to auto-mark dirty if user edits via direct state changes not captured above
  useEffect(()=> {
    if(!fiscalYear) return;
    const extras = extraLevels.filter(l=> l.values.length>0).map(l=> ({name:l.name, values:[...l.values].sort()}));
    const sig = JSON.stringify({customers:[...customers].sort(), circles:[...circles].sort(), extras});
    if(lastDimSignature && sig !== lastDimSignature) setDimensionDirty(true);
  },[customers,circles,extraLevels,fiscalYear]);

  return (
    <div style={{border:'1px solid #ccc', padding:20, marginTop:24}}>
      <h2>Volume Design (Dynamic)</h2>
      {step===1 && (
        <div>
          <label>Fiscal Year: <input value={fiscalYearInput} onChange={e=>setFiscalYearInput(e.target.value)} placeholder="FY25-26" /></label>
          <button style={{marginLeft:10}} onClick={lockFiscalYear}>Next</button>
          <div style={{marginTop:6, fontSize:12}}>Format FYYY-YY (e.g. FY25-26)</div>
        </div>
      )}
          {step>1 && (
        <div style={{marginBottom:8}}>
          <b>FY:</b> {fiscalYear} | Prior Years: {priorYears.join(', ')} <button onClick={()=> { if(window.confirm('Changing Fiscal Year will clear LOB and all modeling data. Continue?')){ setStep(1); setFiscalYear(null); setLob(''); resetModelState(); } }}>Change FY</button>
        </div>
      )}
      {fiscalYear && step===2 && (
        <div style={{marginBottom:16}}>
          <h3 style={{marginTop:0}}>Select LOB</h3>
          <select value={lob} onChange={e=> handleLobChange(e.target.value)}>
            <option value=''>-- Choose LOB --</option>
            {LOBS.map(l=> <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
      )}
      {/* All LOBs now supported: show modeling flow for any selected LOB */}
      {fiscalYear && step>=3 && lob && (
        <div style={{marginBottom:16}}>
          <div style={{marginBottom:8}}>
            <b>LOB:</b> {lob} <button onClick={() => setStep(2)}>Change LOB</button>
          </div>
        </div>
      )}
      {fiscalYear && lob && step>=3 && (
        <div style={{border:'1px solid #ddd', padding:12, marginBottom:16, background:'#fafafa'}}>
          <h3 style={{marginTop:0}}>Dimension Definition</h3>
          <div>
            <b>Customers</b>
            <div style={{display:'flex', gap:8, flexWrap:'wrap', marginTop:4}}>
              {customers.map(c=> <span key={c} style={{background:'#eef', padding:'4px 8px', borderRadius:4}}>{c} <button onClick={()=>removeCustomer(c)}>x</button></span>)}
            </div>
            <div style={{marginTop:6}}>
              <input value={newCustomer} onChange={e=>setNewCustomer(e.target.value)} placeholder="Add customer" /> <button onClick={addCustomer}>Add</button>
            </div>
          </div>
          <div style={{marginTop:14}}>
            <b>{isSmallCell ? 'Site Types' : 'Circles'}</b>
            <div style={{display:'flex', gap:8, flexWrap:'wrap', marginTop:4}}>
              {dimensionList.map(d=> <span key={d} style={{background:'#efe', padding:'4px 8px', borderRadius:4}}>{d} <button onClick={()=>removeDimension(d)}>x</button></span>)}
            </div>
            <div style={{marginTop:6}}>
              <input value={newDimension} onChange={e=>setNewDimension(e.target.value)} placeholder={isSmallCell ? 'Add site type' : 'Add circle'} /> <button onClick={addDimension}>Add</button>
            </div>
          </div>
          <div style={{marginTop:18}}>
            <b>Optional Extra Levels</b>
            {extraLevels.length===0 && <div style={{fontSize:12,color:'#666', marginTop:4}}>No extra levels yet.</div>}
            {extraLevels.map((lvl, idx)=>(
              <div key={idx} style={{border:'1px solid #aaa', padding:8, marginTop:8}}>
                <b>{lvl.name}</b> <button onClick={()=>deleteLevel(idx)}>Delete Level</button>
                <div style={{display:'flex', gap:6, flexWrap:'wrap', marginTop:6}}>
                  {lvl.values.map(v=> <span key={v} style={{background:'#ddd', padding:'2px 6px', borderRadius:4}}>{v} <button onClick={()=>removeValue(idx,v)}>x</button></span>)}
                </div>
                <div style={{marginTop:6}}>
                  <input value={newLevelValue} onChange={e=>setNewLevelValue(e.target.value)} placeholder={`Add value to ${lvl.name}`} /> <button onClick={()=>addValueToLevel(idx)}>Add Value</button>
                </div>
              </div>
            ))}
            <div style={{marginTop:10}}>
              <input value={newLevelName} onChange={e=>setNewLevelName(e.target.value)} placeholder="New level name" /> <button onClick={addExtraLevel}>Add Level</button>
            </div>
          </div>
          <div style={{marginTop:16}}>
            <button disabled={!(customers.length)} onClick={()=>generateCombos(true)}>{combos.length? 'Regenerate Combinations' : 'Generate Combinations'}</button>
            {dimensionDirty && <span style={{marginLeft:10, color:'#d9534f', fontSize:12}}>Dimensions changed – regenerate to apply (existing data preserved where possible)</span>}
          </div>
        </div>
      )}
  {fiscalYear && lob && combos.length>0 && (
        <div>
          <div style={{display:'flex', alignItems:'center', gap:12}}>
            <h3 style={{marginBottom:0}}>Combinations ({combos.length})</h3>
            <button onClick={()=> setCombosCollapsed(c=> !c)}>{combosCollapsed? 'Expand' : 'Collapse'}</button>
          </div>
          {!combosCollapsed && (
            <table border={1} cellPadding={4} style={{borderCollapse:'collapse', width:'100%', marginTop:8}}>
              <thead>
                <tr>
                  <th>Include</th>
                  <th>Customer</th>
                  <th>{isSmallCell ? 'Site Type' : 'Circle'}</th>
                  <th>Type</th>
                  {extraLevels.filter(l=> l.values.length>0).map(l=> <th key={l.name}>{l.name}</th>)}
                </tr>
              </thead>
              <tbody>
                {combos.map((c,i)=> (
                  <tr key={i} style={{opacity: c.included?1:0.4}}>
                    <td><input type="checkbox" checked={c.included!==false} onChange={()=>toggleInclude(i)} /></td>
                    <td>{c.dimensions.customer}</td>
                    <td>{isSmallCell ? c.dimensions.siteType : c.dimensions.circle}</td>
                    <td>{c.dimensions.type}</td>
                    {extraLevels.filter(l=> l.values.length>0).map(l=> <td key={l.name}>{c.dimensions[l.name]}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
  {fiscalYear && lob && combos.length>0 && (
        <div style={{marginTop:20}}>
          <h3>Prior Year Exit Volumes</h3>
          <div style={{fontSize:12, marginBottom:8}}>Enter cumulative exit volumes (one number per prior year, per combination).</div>
          <div style={{marginBottom:10}}>
            <label>Upload Existing Volume & Revenue?&nbsp;
              <select value={useUploadExisting? 'yes':'no'} onChange={e=> setUseUploadExisting(e.target.value==='yes')}>
                <option value='no'>No</option>
                <option value='yes'>Yes</option>
              </select>
            </label>
            {useUploadExisting && (
              <span style={{marginLeft:16}}>
                <button onClick={downloadTemplate}>Download Template</button>
                <input type="file" accept=".csv,.xlsx,.xls" style={{marginLeft:10}} onChange={handleExistingUpload} />
              </span>
            )}
            {uploadInfo && <span style={{marginLeft:12, fontSize:12, color:'#2d6'}}>Uploaded rows: {uploadInfo.rows}</span>}
          </div>
          {priorYears.length===0 && <div style={{fontSize:12, color:'#666'}}>No prior years for selected fiscal year.</div>}
          {priorYears.length>0 && (
            <div style={{overflowX:'auto'}}>
              <table border={1} cellPadding={4} style={{borderCollapse:'collapse', minWidth:'60%'}}>
                <thead>
                  <tr>
                    <th>Combination</th>
                    {priorYears.map(py=> <th key={py}>{py} Exit</th>)}
                  </tr>
                </thead>
                <tbody>
                  {combos.map((c,i)=> {
                    if(c.included===false) return null;
                    return (
                      <tr key={i}>
                        <td style={{whiteSpace:'nowrap'}}>{Object.values(c.dimensions).join(' / ')}</td>
                        {priorYears.map(py=> (
                          <td key={py}><input type="number" style={{width:100}} value={c.exit_volumes[py]||0} onChange={e=>updateExit(i,py,e.target.value)} /></td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
  {fiscalYear && lob && combos.length>0 && (
        <div style={{marginTop:20}}>
          <h3>Fresh Monthly Volumes ({fiscalYear})</h3>
          <div style={{fontSize:12, marginBottom:8}}>Enter monthly fresh volumes for each included combination.</div>
          <div style={{overflowX:'auto'}}>
            <table border={1} cellPadding={4} style={{borderCollapse:'collapse', minWidth:'80%'}}>
              <thead>
                <tr>
                  <th>Combination</th>
                  <th>P&L Offset (m)</th>
                  <th>CF Offset (m)</th>
                  <th>Capex Recog Offset (m)</th>
                  <th>Capex CF Offset (m)</th>
                  {FISCAL_MONTHS.map(m=> <th key={m}>{m}</th>)}
                </tr>
              </thead>
              <tbody>
                {combos.map((c,i)=> {
                  if(c.included===false) return null;
                  return (
                    <tr key={i}>
                      <td style={{whiteSpace:'nowrap'}}>{Object.values(c.dimensions).join(' / ')}</td>
                      <td><input title='P&L recognition offset from fresh volume month (was Fresh Offset)' type="number" min={0} style={{width:70}} value={c.fresh_offset_months||0} onChange={e=> setCombos(list=> list.map((cc,ii)=> ii===i? {...cc, fresh_offset_months: Number(e.target.value)||0}: cc))} /></td>
                      <td><input title='Cashflow (CF) timing offset applied to inflow & outflow from this combination' type="number" min={0} style={{width:70}} value={c.cashflow_offset_months||0} onChange={e=> setCombos(list=> list.map((cc,ii)=> ii===i? {...cc, cashflow_offset_months: Number(e.target.value)||0}: cc))} /></td>
                      <td><input title='CAPEX recognition offset applied to cumulative fresh volume basis for CAPEX items' type='number' min={0} style={{width:70}} value={c.capex_offset_months||0} onChange={e=> setCombos(list=> list.map((cc,ii)=> ii===i? {...cc, capex_offset_months: Number(e.target.value)||0}: cc))} /></td>
                      <td><input title='CAPEX cashflow offset added to per-item CAPEX CF offsets' type='number' min={0} style={{width:70}} value={c.capex_cashflow_offset_months||0} onChange={e=> setCombos(list=> list.map((cc,ii)=> ii===i? {...cc, capex_cashflow_offset_months: Number(e.target.value)||0}: cc))} /></td>
                      {FISCAL_MONTHS.map(m=> {
                        const v = (c.volumes[fiscalYear]||{})[m]||0; return (
                          <td key={m}><input type="number" style={{width:80}} value={v} onChange={e=>updateMonth(i,m,e.target.value)} /></td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {error && <div style={{color:'red', marginTop:8}}>Error: {error}</div>}
          {volumeResult && (
            <div style={{marginTop:18}}>
              <h3>Results</h3>
              <table border={1} cellPadding={4} style={{borderCollapse:'collapse'}}>
                <thead>
                  <tr>
                    <th>Combination</th>
                    {FISCAL_MONTHS.map(m=> <th key={m}>{m}</th>)}
                    <th>Total</th>
                    {priorYears.map(py=> <th key={py}>Exit {py}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {volumeResult.rows.map((r,i)=> (
                    <tr key={i}>
                      <td>{Object.values(r.dimensions).join(' / ')}</td>
                      {FISCAL_MONTHS.map(m=> <td key={m}>{r.months[m]}</td>)}
                      <td>{r.total}</td>
                      {priorYears.map(py=> <td key={py}>{(r.prior_exit_volumes||{})[py]||0}</td>)}
                    </tr>
                  ))}
                </tbody>
                <tfoot>
          <tr><td><b>Grand Total</b></td>{FISCAL_MONTHS.map(m=> <td key={m}>{volumeResult.totals[m]}</td>)}<td>{volumeResult.grand_total}</td>{priorYears.map(py=> <td key={py}></td> )}</tr>
                </tfoot>
              </table>
        {volumeResult.dimension_totals && Object.keys(volumeResult.dimension_totals).length>0 && (
                <div style={{marginTop:20}}>
                  <h4>Dimension Subtotals</h4>
          {Object.entries(volumeResult.dimension_totals).map(([dim, entries])=> (
                    <div key={dim} style={{marginTop:12}}>
                      <b>{dim}</b>
                      <table border={1} cellPadding={4} style={{borderCollapse:'collapse', marginTop:4}}>
                        <thead><tr><th>Value</th>{FISCAL_MONTHS.map(m=> <th key={m}>{m}</th>)}<th>Total</th></tr></thead>
                        <tbody>
                          {entries.map((e,i)=> (
                            <tr key={i}>
                              <td>{e.value}</td>
                              {FISCAL_MONTHS.map(m=> <td key={m}>{e.months[m]}</td>)}
                              <td>{e.total}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
  {fiscalYear && lob && combos.length>0 && (
        <div style={{marginTop:24}}>
          <h3>Rates (Recurring & One-Time)</h3>
          <div style={{fontSize:12, marginBottom:8}}>Specify rates. If a Base Exit Year is selected, existing volume from that year's exit will use Existing rates and fresh revenue uses cumulative fresh volumes each month.</div>
          <div style={{marginBottom:12}}>
            <label>Base Exit Year:&nbsp;
              <select value={baseExitYear} onChange={e=> setBaseExitYear(e.target.value)}>
                <option value=''>None</option>
                {priorYears.map(py=> <option key={py} value={py}>{py}</option>)}
              </select>
            </label>
            <span style={{marginLeft:24}}>
              <label><input type="checkbox" checked={includeFresh} onChange={e=> setIncludeFresh(e.target.checked)} /> Include Fresh Volumes</label>
            </span>
          </div>
          <div style={{display:'flex', flexWrap:'wrap', gap:16, marginBottom:12}}>
            <div>
              <label style={{fontSize:12}}>Recurring Formula</label><br/>
              <input style={{width:320}} value={formulaRecurring} onChange={e=> setFormulaRecurring(e.target.value)} />
            </div>
            <div>
              <label style={{fontSize:12}}>One-Time Formula</label><br/>
              <input style={{width:320}} value={formulaOneTime} onChange={e=> setFormulaOneTime(e.target.value)} />
            </div>
          </div>
          <div style={{overflowX:'auto'}}>
            <table border={1} cellPadding={4} style={{borderCollapse:'collapse', minWidth:'80%'}}>
              <thead>
                <tr>
                  <th>Combination</th>
                  <th>Fresh Recurring Rate</th>
                  <th>Fresh One-Time Rate</th>
                  <th>Existing Recurring Rate</th>
                  <th>Existing One-Time Rate</th>
                </tr>
              </thead>
              <tbody>
                {combos.filter(c=> c.included!==false).map((c,i)=> {
                  const key = Object.values(c.dimensions).join('|');
                  const r = rates[key] || {recurring_rate:0, one_time_rate:0, existing_recurring_rate:0, existing_one_time_rate:0};
                  return (
                    <tr key={i}>
                      <td style={{whiteSpace:'nowrap'}}>{Object.values(c.dimensions).join(' / ')}</td>
                      <td><input type="number" style={{width:120}} value={r.recurring_rate} onChange={e=> setRates(rs=> ({...rs, [key]: {...r, recurring_rate: Number(e.target.value)}}))} /></td>
                      <td><input type="number" style={{width:120}} value={r.one_time_rate} onChange={e=> setRates(rs=> ({...rs, [key]: {...r, one_time_rate: Number(e.target.value)}}))} /></td>
                      <td><input type="number" style={{width:120}} value={r.existing_recurring_rate} onChange={e=> setRates(rs=> ({...rs, [key]: {...r, existing_recurring_rate: Number(e.target.value)}}))} /></td>
                      <td><input type="number" style={{width:120}} value={r.existing_one_time_rate} onChange={e=> setRates(rs=> ({...rs, [key]: {...r, existing_one_time_rate: Number(e.target.value)}}))} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div style={{marginTop:12}}>
            <button onClick={()=> runRevenueCalc()} disabled={loading}>{loading? 'Calculating...' : 'Calculate Revenue'}</button>
          </div>
          {/* Opex Configuration */}
          <div style={{marginTop:30, borderTop:'1px solid #ddd', paddingTop:20}}>
            <h3>Opex</h3>
            <div style={{marginTop:12, fontSize:13}}>
              <label>Upload Existing Opex?&nbsp;
                <select value={useUploadOpexExisting? 'yes':'no'} onChange={e=> { const on = e.target.value==='yes'; setUseUploadOpexExisting(on); if(!on){ setExistingOpexOverrides({}); setOpexUploadInfo(null);} }}>
                  <option value='no'>No</option>
                  <option value='yes'>Yes</option>
                </select>
              </label>
              {useUploadOpexExisting && (
                <span style={{marginLeft:16}}>
                  <button onClick={downloadOpexTemplate}>Download Template</button>
                  <input type='file' accept='.csv,.xlsx,.xls' style={{marginLeft:10}} onChange={handleOpexExistingUpload} />
                </span>
              )}
              {opexUploadInfo && <span style={{marginLeft:12, fontSize:12, color:'#2d6'}}>Uploaded Opex Items: {opexUploadInfo.rows}</span>}
            </div>
            {/* Ensure the OpexItems editor is mounted even when the list is empty so it can initialize defaults */}
            <OpexItems opexItems={opexItems} setOpexItems={setOpexItems} />
            {opexItems.length>0 && (
              <div style={{marginTop:32}}>
                <h4>Opex Rates (Transposed View)</h4>
                {/* Existing Rates: rows = combinations, columns = items (no offsets here) */}
                <div style={{overflowX:'auto', marginBottom:28}}>
                  <table border={1} cellPadding={4} style={{borderCollapse:'collapse', minWidth:'70%'}}>
                    <thead>
                      <tr>
                        <th>Combination (Existing)</th>
                        {opexItems.map(it=> (
                          <th key={'ex-h-'+it.name} style={{whiteSpace:'nowrap'}}>{it.name}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {combos.filter(c=> c.included!==false).map((c,ci)=> {
                        const comboKeyStr = Object.values(c.dimensions).join(' / ');
                        const key = Object.values(c.dimensions).join('|');
                        return (
                          <tr key={'ex-row-'+ci}>
                            <td style={{whiteSpace:'nowrap'}}>{comboKeyStr}</td>
                            {opexItems.map(it=> {
                              const itemRates = (opexRates[key] && opexRates[key][it.name]) || {existing_rate:0,fresh_rate:0};
                              return (
                                <td key={'ex-cell-'+key+'-'+it.name}>
                                  <input type='number' style={{width:80}} value={itemRates.existing_rate} onChange={e=> setOpexRates(rs=> ({...rs, [key]: {...(rs[key]||{}), [it.name]: {...itemRates, existing_rate: Number(e.target.value)}}}))} />
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {/* Fresh Rates: rows = combinations, columns = items (offset + remove per item) */}
                <div style={{overflowX:'auto'}}>
                  <table border={1} cellPadding={4} style={{borderCollapse:'collapse', minWidth:'70%'}}>
                    <thead>
                      <tr>
                        <th>Combination (Fresh)</th>
                        {opexItems.map((it,i)=> (
                          <th key={'fr-h-'+it.name} style={{whiteSpace:'nowrap'}}>
                            {it.name}
                            <div style={{marginTop:4, display:'flex', flexDirection:'column', alignItems:'flex-start', gap:4}}>
                              <div>
                                <input title='P&L Offset (months) for this Opex item (was Fresh Offset)' type='number' min={0} style={{width:60}} value={it.fresh_offset_months||0} onChange={e=> setOpexItems(list=> list.map((o,j)=> j===i? {...o, fresh_offset_months: Number(e.target.value)||0}: o))} />
                                <span style={{fontSize:10, marginLeft:4}}>P&L</span>
                              </div>
                              <div>
                                <input title='CF Offset (months) for this Opex item (added to combination CF offset)' type='number' min={0} style={{width:60}} value={it.cashflow_offset_months||0} onChange={e=> setOpexItems(list=> list.map((o,j)=> j===i? {...o, cashflow_offset_months: Number(e.target.value)||0}: o))} />
                                <span style={{fontSize:10, marginLeft:4}}>CF</span>
                              </div>
                              <button style={{marginTop:2}} onClick={()=> setOpexItems(list=> list.filter((_,j)=> j!==i))}>X</button>
                            </div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {combos.filter(c=> c.included!==false).map((c,ci)=> {
                        const comboKeyStr = Object.values(c.dimensions).join(' / ');
                        const key = Object.values(c.dimensions).join('|');
                        return (
                          <tr key={'fr-row-'+ci}>
                            <td style={{whiteSpace:'nowrap'}}>{comboKeyStr}</td>
                            {opexItems.map(it=> {
                              const itemRates = (opexRates[key] && opexRates[key][it.name]) || {existing_rate:0,fresh_rate:0};
                              return (
                                <td key={'fr-cell-'+key+'-'+it.name}>
                                  <input type='number' style={{width:80}} value={itemRates.fresh_rate} onChange={e=> setOpexRates(rs=> ({...rs, [key]: {...(rs[key]||{}), [it.name]: {...itemRates, fresh_rate: Number(e.target.value)}}}))} />
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {/* Assumption Inputs for P&L */}
                <div style={{marginTop:20, padding:10, border:'1px solid #ccc', background:'#fafafa', display:'flex', gap:20, flexWrap:'wrap'}}>
                  <div>
                    <label style={{fontSize:12}}>Provision % (of Gross Revenue)</label><br/>
                    <input type='number' style={{width:120}} value={provisionPct} onChange={e=> setProvisionPct(Number(e.target.value)||0)} />
                  </div>
                  <div>
                    <label style={{fontSize:12}}>Customer Penalty % (of Net Revenue)</label><br/>
                    <input type='number' style={{width:120}} value={customerPenaltyPct} onChange={e=> setCustomerPenaltyPct(Number(e.target.value)||0)} />
                  </div>
                  <div>
                    <label style={{fontSize:12}}>Vendor Penalty % (of Net Revenue)</label><br/>
                    <input type='number' style={{width:120}} value={vendorPenaltyPct} onChange={e=> setVendorPenaltyPct(Number(e.target.value)||0)} />
                  </div>
                  <div style={{alignSelf:'flex-end'}}>
                    <button onClick={()=> runRevenueCalc()} disabled={loading}>{loading? 'Calculating...' : 'Recalculate (with %)'}</button>
                  </div>
                </div>
                {useUploadOpexExisting && existingOpexOverrides && Object.keys(existingOpexOverrides).length>0 && (
                  <div style={{marginTop:16, fontSize:12, background:'#f4f9ff', padding:10, border:'1px solid #bcd'}}>
                    <b>Existing Opex Overrides Applied:</b> {Object.keys(existingOpexOverrides).join(', ')}
                  </div>
                )}
              </div>
            )}
            {opexItems.length>0 && (
              <div style={{marginTop:16}}>
                <button onClick={()=> runRevenueCalc()} disabled={loading}>{loading? 'Calculating...' : 'Recalculate Opex'}</button>
              </div>
            )}
          </div>
        {/* CAPEX configuration */}
        <div style={{marginTop:50, borderTop:'2px solid #555', paddingTop:24}}>
          <h3>CAPEX Items</h3>
          <div style={{display:'flex', gap:12, flexWrap:'wrap', alignItems:'flex-end'}}>
            <div>
              <label style={{fontSize:12}}>Name</label><br/>
              <input value={newCapexName} onChange={e=> setNewCapexName(e.target.value)} placeholder='New CAPEX Item' />
            </div>
            <div>
              <label style={{fontSize:12}}>Group</label><br/>
              <select value={newCapexGroup} onChange={e=> setNewCapexGroup(e.target.value)}>
                {CAPEX_GROUPS.map(g=> <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label style={{fontSize:12}}>Add</label><br/>
              <button onClick={()=> {
                const name = newCapexName.trim(); if(!name) return;
                if(capexItems.some(i=> i.name.toLowerCase()===name.toLowerCase())) return;
                const group = newCapexGroup;
                let type='first_time';
                if(group.startsWith('Replacement')) type='replacement';
                else if(group==='Capex People') type='people';
                else if(group==='Deposit Refund') type='deposit_refund';
                const is_refund = group==='Deposit Refund';
                setCapexItems(list=> [...list, {name, group, type, is_refund, recognition_offset_months:0, cashflow_offset_months:0}]);
                setNewCapexName('');
              }}>Add CAPEX</button>
            </div>
          </div>
          {capexItems.length>0 && (
            <div style={{marginTop:18, overflowX:'auto'}}>
              <table border={1} cellPadding={4} style={{borderCollapse:'collapse', minWidth:'70%'}}>
                <thead>
                  <tr>
                    <th>Item</th><th>Group</th><th>Type</th><th>Recog Offset (m)</th><th>CF Offset (m)</th><th>Refund?</th><th>Remove</th>
                  </tr>
                </thead>
                <tbody>
                  {capexItems.map((it,i)=>(
                    <tr key={it.name}>
                      <td>{it.name}</td>
                      <td>{it.group}</td>
                      <td>{it.type}</td>
                      <td><input type='number' min={0} style={{width:70}} value={it.recognition_offset_months||0} onChange={e=> setCapexItems(list=> list.map((o,j)=> j===i? {...o, recognition_offset_months:Number(e.target.value)||0}: o))} /></td>
                      <td><input type='number' min={0} style={{width:70}} value={it.cashflow_offset_months||0} onChange={e=> setCapexItems(list=> list.map((o,j)=> j===i? {...o, cashflow_offset_months:Number(e.target.value)||0}: o))} /></td>
                      <td style={{textAlign:'center'}}>
                        <input type='checkbox' checked={!!it.is_refund} onChange={e=> setCapexItems(list=> list.map((o,j)=> j===i? {...o, is_refund: e.target.checked}: o))} />
                      </td>
                      <td><button onClick={()=> setCapexItems(list=> list.filter((_,j)=> j!==i))}>X</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {capexItems.length>0 && (
            <div style={{marginTop:28}}>
              {hasReplacementCapex && (
                <>
                  <h4>CAPEX Rates (Existing)</h4>
                  <div style={{fontSize:11, marginBottom:6}}>Shown only because at least one Replacement item exists. Non-replacement columns disabled.</div>
                  <div style={{overflowX:'auto', marginBottom:22}}>
                    <table border={1} cellPadding={4} style={{borderCollapse:'collapse', minWidth:'70%'}}>
                      <thead>
                        <tr>
                          <th>Combination</th>
                          {capexItems.map(it=> (
                            <th key={'cex-h-'+it.name} style={{whiteSpace:'nowrap'}}>{it.name}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {combos.filter(c=> c.included!==false).map((c,ci)=> {
                          const key = Object.values(c.dimensions).join('|');
                          const label = Object.values(c.dimensions).join(' / ');
                          return (
                            <tr key={'cex-row-'+ci}>
                              <td style={{whiteSpace:'nowrap'}}>{label}</td>
                              {capexItems.map(it=> {
                                const itemRates = (capexRates[key] && capexRates[key][it.name]) || {existing_rate:0,fresh_rate:0};
                                // Only disable for non-replacement items except ROW Deposit and Deposit Refund
                                const isDepositOrRefund = it.group === 'ROW Deposit' || it.group === 'Deposit Refund';
                                const disabled = it.type !== 'replacement' && !isDepositOrRefund;
                                return (
                                  <td key={'cex-cell-'+key+'-'+it.name}>
                                    <input type='number' disabled={disabled} style={{width:80}} value={itemRates.existing_rate} onChange={e=> setCapexRates(rs=> ({...rs, [key]: {...(rs[key]||{}), [it.name]: {...itemRates, existing_rate:Number(e.target.value)}}}))} />
                                  </td>
                                );
                              })}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              <h4>CAPEX Rates (Fresh)</h4>
              <div style={{overflowX:'auto'}}>
                <table border={1} cellPadding={4} style={{borderCollapse:'collapse', minWidth:'70%'}}>
                  <thead>
                    <tr>
                      <th>Combination</th>
                      {capexItems.map(it=> (
                        <th key={'cfr-h-'+it.name} style={{whiteSpace:'nowrap'}}>{it.name}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {combos.filter(c=> c.included!==false).map((c,ci)=> {
                      const key = Object.values(c.dimensions).join('|');
                      const label = Object.values(c.dimensions).join(' / ');
                      return (
                        <tr key={'cfr-row-'+ci}>
                          <td style={{whiteSpace:'nowrap'}}>{label}</td>
                          {capexItems.map(it=> {
                            const itemRates = (capexRates[key] && capexRates[key][it.name]) || {existing_rate:0,fresh_rate:0};
                            // Make ROW Deposit and Deposit Refund editable
                            const isDepositOrRefund = it.group === 'ROW Deposit' || it.group === 'Deposit Refund';
                            const disabledFresh = false;
                            return (
                              <td key={'cfr-cell-'+key+'-'+it.name}>
                                <input type='number' disabled={disabledFresh} style={{width:80}} value={itemRates.fresh_rate} onChange={e=> setCapexRates(rs=> ({...rs, [key]: {...(rs[key]||{}), [it.name]: {...itemRates, fresh_rate:Number(e.target.value)}}}))} />
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div style={{marginTop:18}}>
                <button onClick={()=> runRevenueCalc()} disabled={loading}>{loading? 'Calculating...' : 'Recalculate CAPEX'}</button>
              </div>
            </div>
          )}
        </div>
  {revenueResult && (
            <div style={{marginTop:20}}>
              {error && (
                <div style={{color:'red', marginBottom:16}}>
                  <b>Error:</b> {error}
                </div>
              )}
              <h3>Revenue Result</h3>
              {/** Helper for consistent 2-decimal formatting */}
              {(() => { /* IIFE only to keep scope local */ })()}
              <style>{`.num-cell{text-align:right;}`}</style>
              {/** Formatting function */}
              <script dangerouslySetInnerHTML={{__html:''}} />
              {/** We'll define a local formatter */}
              {/** (React JSX can't define functions inline easily for dynamic generation; using closure variable) */}
              {(() => { if(!window.__fmt2) window.__fmt2 = (v)=> (v==null? '0.00': Number(v).toFixed(2)); })()}
              {/* Table 1: Per Combination Monthly Total Revenue (months as columns) */}
              <div style={{overflowX:'auto'}}>
                <table border={1} cellPadding={4} style={{borderCollapse:'collapse', marginBottom:24}}>
                  <thead>
                    <tr>
                      <th>Combination</th>
                      {FISCAL_MONTHS.map(m=> <th key={m}>{m}</th>)}
                      <th>{fiscalYear || 'Year Total'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {revenueResult.rows.map((r,i)=> (
                      <tr key={i}>
                        <td>{Object.values(r.dimensions).join(' / ')}</td>
                        {FISCAL_MONTHS.map(m=> <td className='num-cell' key={m}>{Number((r.monthly_revenue||{})[m]||0).toFixed(2)}</td>)}
                        <td className='num-cell'>{Number(r.total_revenue).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td><b>Totals</b></td>
                      {FISCAL_MONTHS.map(m=> <td className='num-cell' key={m}>{Number(revenueResult.monthly_totals[m]).toFixed(2)}</td>)}
                      <td className='num-cell'><b>{Number(revenueResult.total_revenue).toFixed(2)}</b></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
              {/* Table 2: Monthly Summary (months as rows) */}
              <h4>Monthly Summary</h4>
              <table border={1} cellPadding={4} style={{borderCollapse:'collapse'}}>
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>One-Time Revenue</th>
                    <th>Recurring Revenue</th>
                    <th>Total Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {FISCAL_MONTHS.map(m=> (
                    <tr key={m}>
                      <td>{m}</td>
                      <td className='num-cell'>{Number(revenueResult.monthly_one_time_totals[m]).toFixed(2)}</td>
                      <td className='num-cell'>{Number(revenueResult.monthly_recurring_totals[m]).toFixed(2)}</td>
                      <td className='num-cell'>{Number(revenueResult.monthly_totals[m]).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td><b>{fiscalYear || 'Year Total'}</b></td>
                    <td className='num-cell'>{Object.values(revenueResult.monthly_one_time_totals).reduce((a,b)=> a+b,0).toFixed(2)}</td>
                    <td className='num-cell'>{Object.values(revenueResult.monthly_recurring_totals).reduce((a,b)=> a+b,0).toFixed(2)}</td>
                    <td className='num-cell'>{Number(revenueResult.total_revenue).toFixed(2)}</td>
                  </tr>
                </tfoot>
              </table>
              {/* Opex summary */}
              <div style={{marginTop:40}}>
                <h3>Opex Summary</h3>
                {revenueResult.opex_items && revenueResult.opex_items.length>0 ? (
                  <div style={{overflowX:'auto'}}>
                    <table border={1} cellPadding={4} style={{borderCollapse:'collapse'}}>
                      <thead>
                        <tr>
                          <th>Opex Item</th>
                          {FISCAL_MONTHS.map(m=> <th key={m}>{m}</th>)}
                          <th>{fiscalYear || 'Year Total'}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {revenueResult.opex_items.map((it,i)=>(
                          <tr key={i}>
                            <td>{it.name}</td>
                            {FISCAL_MONTHS.map(m=> <td className='num-cell' key={m}>{Number(it.monthly[m]||0).toFixed(2)}</td>)}
                            <td className='num-cell'>{Number(it.total||0).toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr>
                          <td><b>Total Opex</b></td>
                          {FISCAL_MONTHS.map(m=> <td className='num-cell' key={m}>{Number((revenueResult.monthly_opex_totals||{})[m]||0).toFixed(2)}</td>)}
                          <td className='num-cell'><b>{Number(revenueResult.total_opex||0).toFixed(2)}</b></td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                ) : (<div style={{fontSize:12, color:'#666'}}>No opex items defined.</div>)}
              </div>
              {/* P&L Summary */}
              <div style={{marginTop:50}}>
                <h3>Profit & Loss Summary</h3>
                {(() => {
                  const months = FISCAL_MONTHS;
                  const oneTime = revenueResult.monthly_one_time_totals || {};
                  const recurring = revenueResult.monthly_recurring_totals || {};
                  const passthrough = {}; // placeholder zeros
                  // Direct Opex is simply all opex items currently (user no longer needs to add provision/penalties as items)
                  const allOpexItems = revenueResult.opex_items || [];
                  const directOpexItems = allOpexItems; // use all defined items
                  const directOpexTotals = {};
                  months.forEach(m=> { directOpexTotals[m] = directOpexItems.reduce((a,it)=> a + (it.monthly[m]||0),0); });
                  // Provision & penalties derived from percentages (clamp base <0 to 0)
                  const provDD = {}; // based on Gross
                  const SCALE = 1_000_000; // display in millions
                  const fmt = (v, decimals=1) => (Number(v||0)/SCALE).toFixed(decimals);
                  const fmtParens = (v, decimals=1, force=false) => {
                    const num = Number(v||0);
                    const scaled = Math.abs(num)/SCALE;
                    if(force || num<0) return `(${scaled.toFixed(decimals)})`;
                    return scaled.toFixed(decimals);
                  };
                  // Pre-compute row structures
                  const gross = {}; const net = {}; const operMargin = {}; const cumOperMargin = {}; const operMarginPct = {};
                  const customerPenalty = {}; const vendorPenalty = {}; const totalPenalty = {}; const operMarginAfterPenalty = {}; const cumOperMarginAfterPenalty = {}; const operMarginPctAfterPenalty = {};
                  let running = 0;
                  let runningAfter = 0;
                  months.forEach(m => {
                    gross[m] = (oneTime[m]||0) + (recurring[m]||0) + (passthrough[m]||0);
                    // Provision % of gross (base not negative)
                    const baseGross = Math.max(gross[m],0);
                    provDD[m] = baseGross * (provisionPct/100);
                    net[m] = gross[m] - provDD[m];
                    operMargin[m] = net[m] - (directOpexTotals[m]||0); // excludes penalties
                    running += operMargin[m];
                    cumOperMargin[m] = running;
                    operMarginPct[m] = net[m] ? (operMargin[m]/net[m])*100 : 0;
                    // Penalties from % of net; clamp negative/zero net => 0
                    const baseNet = net[m] > 0 ? net[m] : 0;
                    customerPenalty[m] = baseNet * (customerPenaltyPct/100); // cost
                    vendorPenalty[m] = baseNet * (vendorPenaltyPct/100); // refund (treated positive then subtracted?)
                    totalPenalty[m] = customerPenalty[m] + vendorPenalty[m];
                    operMarginAfterPenalty[m] = operMargin[m] - totalPenalty[m];
                    runningAfter += operMarginAfterPenalty[m];
                    cumOperMarginAfterPenalty[m] = runningAfter;
                    operMarginPctAfterPenalty[m] = net[m]? (operMarginAfterPenalty[m]/net[m])*100 : 0;
                  });
                  const sum = (obj) => months.reduce((a,m)=> a + (obj[m]||0),0);
                  const yearTotals = {
                    oneTime: sum(oneTime),
                    recurring: sum(recurring),
                    passthrough: sum(passthrough),
                    gross: sum(gross),
                    provDD: sum(provDD),
                    net: sum(net),
                    opex: sum(directOpexTotals),
                    operMargin: sum(operMargin),
                    cumOperMargin: sum(cumOperMargin), // last value more meaningful
                    operMarginPct: (sum(net)? (sum(operMargin)/sum(net))*100 : 0),
                    customerPenalty: sum(customerPenalty),
                    vendorPenalty: sum(vendorPenalty),
                    totalPenalty: sum(totalPenalty),
                    operMarginAfterPenalty: sum(operMarginAfterPenalty),
                    cumOperMarginAfterPenalty: sum(cumOperMarginAfterPenalty),
                    operMarginPctAfterPenalty: (sum(net)? (sum(operMarginAfterPenalty)/sum(net))*100 : 0)
                  };
                  return (
                    <div style={{overflowX:'auto'}}>
                      <table border={1} cellPadding={4} style={{borderCollapse:'collapse', minWidth:'85%'}}>
                        <thead>
                          <tr>
                            <th>Line Item</th>
                            {months.map(m=> <th key={m}>{m}</th>)}
                            <th>{fiscalYear || 'Year Total'}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr><td>One-time Revenue</td>{months.map(m=> <td className='num-cell' key={m}>{fmt(oneTime[m])}</td>)}<td className='num-cell'>{fmt(yearTotals.oneTime)}</td></tr>
                          <tr><td>Recurring Revenue</td>{months.map(m=> <td className='num-cell' key={m}>{fmt(recurring[m])}</td>)}<td className='num-cell'>{fmt(yearTotals.recurring)}</td></tr>
                          <tr><td>Passthrough Revenue</td>{months.map(m=> <td className='num-cell' key={m}>{fmt(passthrough[m])}</td>)}<td className='num-cell'>{fmt(yearTotals.passthrough)}</td></tr>
                          <tr style={{background:'#f5f5f5'}}><td><b>Gross Revenue (Millions)</b></td>{months.map(m=> <td className='num-cell' key={m}>{fmt(gross[m])}</td>)}<td className='num-cell'><b>{fmt(yearTotals.gross)}</b></td></tr>
                          <tr><td>Provision for Doubtful Debts</td>{months.map(m=> <td className='num-cell' key={m}>{fmt(provDD[m])}</td>)}<td className='num-cell'>{fmt(yearTotals.provDD)}</td></tr>
                          <tr style={{background:'#eef'}}><td><b>Net Revenue (Millions)</b></td>{months.map(m=> <td className='num-cell' key={m}>{fmt(net[m])}</td>)}<td className='num-cell'><b>{fmt(yearTotals.net)}</b></td></tr>
                          <tr><td colSpan={months.length+2} style={{background:'#ddd', fontWeight:'bold'}}>Direct Opex</td></tr>
                          {directOpexItems.map((it,i)=> (
                            <tr key={'pl-opx-'+i}>
                              <td style={{paddingLeft:20}}>{it.name}</td>
                              {months.map(m=> <td className='num-cell' key={m}>{fmtParens(it.monthly[m],1,true)}</td>)}
                              <td className='num-cell'>{fmtParens(it.total,1,true)}</td>
                            </tr>
                          ))}
                          <tr style={{background:'#f5f5f5'}}><td><b>Grand Total Direct Opex (Millions)</b></td>{months.map(m=> <td className='num-cell' key={m}>{fmtParens(directOpexTotals[m],1,true)}</td>)}<td className='num-cell'><b>{fmtParens(yearTotals.opex,1,true)}</b></td></tr>
                          <tr style={{background:'#e8ffe8'}}><td><b>Operating Margin (Millions)</b></td>{months.map(m=> <td className='num-cell' key={m}>{fmt(operMargin[m])}</td>)}<td className='num-cell'><b>{fmt(yearTotals.operMargin)}</b></td></tr>
                          <tr><td>Cum. Operating Margin (Millions)</td>{months.map(m=> <td className='num-cell' key={m}>{fmt(cumOperMargin[m])}</td>)}<td className='num-cell'>{fmt(yearTotals.operMargin)}</td></tr>
                          <tr><td>Operating Margin %</td>{months.map(m=> <td className='num-cell' key={m}>{fmt(operMarginPct[m],1)}%</td>)}<td className='num-cell'>{fmt(yearTotals.operMarginPct,1)}%</td></tr>
                          {/* Penalties Section */}
                          <tr><td colSpan={months.length+2} style={{background:'#ddd', fontWeight:'bold'}}>Penalty</td></tr>
                          <tr><td style={{paddingLeft:20}}>Customer Penalty</td>{months.map(m=> <td className='num-cell' key={m}>{fmtParens(customerPenalty[m],1,true)}</td>)}<td className='num-cell'>{fmtParens(yearTotals.customerPenalty,1,true)}</td></tr>
                          <tr><td style={{paddingLeft:20}}>Vendor Penalty</td>{months.map(m=> <td className='num-cell' key={m}>{fmtParens(vendorPenalty[m],1,true)}</td>)}<td className='num-cell'>{fmtParens(yearTotals.vendorPenalty,1,true)}</td></tr>
                          <tr style={{background:'#f5f5f5'}}><td><b>Total Penalty (Millions)</b></td>{months.map(m=> <td className='num-cell' key={m}>{fmtParens(totalPenalty[m],1,true)}</td>)}<td className='num-cell'><b>{fmtParens(yearTotals.totalPenalty,1,true)}</b></td></tr>
                          <tr style={{background:'#d8eaff'}}><td><b>Operating Margin (After Penalty) (Millions)</b></td>{months.map(m=> <td className='num-cell' key={m}>{fmt(operMarginAfterPenalty[m])}</td>)}<td className='num-cell'><b>{fmt(yearTotals.operMarginAfterPenalty)}</b></td></tr>
                          <tr><td>Cum. Operating Margin (After Penalty) (Millions)</td>{months.map(m=> <td className='num-cell' key={m}>{fmt(cumOperMarginAfterPenalty[m])}</td>)}<td className='num-cell'>{fmt(yearTotals.operMarginAfterPenalty)}</td></tr>
                          <tr><td>Operating Margin % (After Penalty)</td>{months.map(m=> <td className='num-cell' key={m}>{fmt(operMarginPctAfterPenalty[m],1)}%</td>)}<td className='num-cell'>{fmt(yearTotals.operMarginPctAfterPenalty,1)}%</td></tr>
                        </tbody>
                      </table>
                    </div>
                  );
                })()}
              </div>
              {/* Cashflow Summary */}
              <div style={{marginTop:50}}>
                <h3>Cashflow Summary</h3>
                {(() => {
                  const months = FISCAL_MONTHS;
                  // Cash inflows (shifted) from backend
                  const cashRec = revenueResult.monthly_cash_recurring_inflow || {};
                  const cashOne = revenueResult.monthly_cash_one_time_inflow || {};
                  const cashPass = revenueResult.monthly_cash_passthrough_inflow || {};
                  const cashGross = revenueResult.monthly_cash_gross_inflow || {};
                  // Provision & penalty timing: same as P&L (unshifted) => base on P&L monthly totals & net revenue logic
                  const plGross = revenueResult.monthly_totals || {}; // unshifted gross revenue
                  const prov = {}; const netInflow = {}; // net after provision
                  months.forEach(m=> { const base = Math.max(plGross[m]||0,0); prov[m] = base * (provisionPct/100); netInflow[m] = (cashGross[m]||0) - prov[m]; });
                  // Outflows (shifted per item)
                  const itemOutList = revenueResult.monthly_cash_outflow_items || [];
                  const outflowTotals = revenueResult.monthly_cash_outflow_totals || {};
                  const netOperating = {}; months.forEach(m=> { netOperating[m] = (netInflow[m]||0) - (outflowTotals[m]||0); });
                  // Penalties base: P&L net revenue (unshifted net after provision) computed from plGross - prov
                  const penaltyBase = {}; months.forEach(m=> { const base = Math.max((plGross[m]||0) - prov[m], 0); penaltyBase[m] = base; });
                  const custPen = {}; const vendPen = {}; const totPen = {}; const netOpPost = {}; months.forEach(m=> { const b = penaltyBase[m]; custPen[m] = b * (customerPenaltyPct/100); vendPen[m] = b * (vendorPenaltyPct/100); totPen[m] = custPen[m] + vendPen[m]; netOpPost[m] = netOperating[m] - totPen[m]; });
                  const SCALE = 1_000_000; const fmt = (v, d=1)=> (Number(v||0)/SCALE).toFixed(d); const fmtParens = (v,d=1)=> { const n=Number(v||0); return n<0? `(${Math.abs(n)/SCALE.toFixed? (Math.abs(n)/SCALE).toFixed(d):fmt(Math.abs(n),d)})`: (Math.abs(n)/SCALE).toFixed(d); };
                  const sum = (obj)=> months.reduce((a,m)=> a + (obj[m]||0),0);
                  return (
                    <div style={{overflowX:'auto'}}>
                      <table border={1} cellPadding={4} style={{borderCollapse:'collapse', minWidth:'85%'}}>
                        <thead>
                          <tr>
                            <th>Line Item</th>
                            {months.map(m=> <th key={m}>{m}</th>)}
                            <th>{fiscalYear || 'Year Total'}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr><td>One-time Revenue</td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>{fmt(cashOne[m])}</td>)}<td style={{textAlign:'right'}}>{fmt(sum(cashOne))}</td></tr>
                          <tr><td>Recurring Revenue</td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>{fmt(cashRec[m])}</td>)}<td style={{textAlign:'right'}}>{fmt(sum(cashRec))}</td></tr>
                          <tr><td>Passthrough Revenue</td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>{fmt(cashPass[m])}</td>)}<td style={{textAlign:'right'}}>{fmt(sum(cashPass))}</td></tr>
                          <tr style={{background:'#f5f5f5'}}><td><b>Gross Inflow</b></td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>{fmt(cashGross[m])}</td>)}<td style={{textAlign:'right'}}><b>{fmt(sum(cashGross))}</b></td></tr>
                          <tr><td>Provision for Doubtful Debts</td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>{fmt(prov[m])}</td>)}<td style={{textAlign:'right'}}>{fmt(sum(prov))}</td></tr>
                          <tr style={{background:'#eef'}}><td><b>Net Inflow</b></td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>{fmt(netInflow[m])}</td>)}<td style={{textAlign:'right'}}><b>{fmt(sum(netInflow))}</b></td></tr>
                          <tr><td colSpan={months.length+2} style={{background:'#ddd', fontWeight:'bold'}}>Outflow</td></tr>
                          {itemOutList.map((it,i)=> (
                            <tr key={i}>
                              <td style={{paddingLeft:20}}>{it.name}</td>
                              {months.map(m=> <td key={m} style={{textAlign:'right'}}>({fmt(it.monthly[m]||0)})</td>)}
                              <td style={{textAlign:'right'}}>({fmt(it.total||0)})</td>
                            </tr>
                          ))}
                          <tr style={{background:'#f5f5f5'}}><td><b>Grand Total Outflow</b></td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>({fmt(outflowTotals[m])})</td>)}<td style={{textAlign:'right'}}><b>({fmt(sum(outflowTotals))})</b></td></tr>
                          <tr style={{background:'#e8ffe8'}}><td><b>Net Operating Flow</b></td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>{fmt(netOperating[m])}</td>)}<td style={{textAlign:'right'}}><b>{fmt(sum(netOperating))}</b></td></tr>
                          <tr><td colSpan={months.length+2} style={{background:'#dbe4f2', fontWeight:'bold'}}>Penalty</td></tr>
                          <tr><td style={{paddingLeft:20}}>Customer Penalty</td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>({fmt(custPen[m])})</td>)}<td style={{textAlign:'right'}}>({fmt(sum(custPen))})</td></tr>
                          <tr><td style={{paddingLeft:20}}>Vendor Penalty</td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>({fmt(vendPen[m])})</td>)}<td style={{textAlign:'right'}}>({fmt(sum(vendPen))})</td></tr>
                          <tr style={{background:'#f5f5f5'}}><td><b>Total Penalty</b></td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>({fmt(totPen[m])})</td>)}<td style={{textAlign:'right'}}><b>({fmt(sum(totPen))})</b></td></tr>
                          <tr style={{background:'#d8eaff'}}><td><b>Net Operating Flow (Post Penalty)</b></td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>{fmt(netOpPost[m])}</td>)}<td style={{textAlign:'right'}}><b>{fmt(sum(netOpPost))}</b></td></tr>
                        </tbody>
                      </table>
                    </div>
                  );
                })()}
              </div>
            </div>
          )}
        </div>
      )}
      {revenueResult && revenueResult.capex_items && revenueResult.capex_items.length>0 && (
        <div style={{marginTop:50}}>
          <h3>CAPEX Summary (Recognition)</h3>
          <div style={{overflowX:'auto'}}>
            <table border={1} cellPadding={4} style={{borderCollapse:'collapse'}}>
              <thead>
                <tr>
                  <th>CAPEX Item</th>
                  {FISCAL_MONTHS.map(m=> <th key={m}>{m}</th>)}
                  <th>{fiscalYear || 'Year Total'}</th>
                </tr>
              </thead>
              <tbody>
                {revenueResult.capex_items.map((it,i)=>(
                  <tr key={'cx-'+i}>
                    <td>{it.name}</td>
                    {FISCAL_MONTHS.map(m=> <td key={m} style={{textAlign:'right'}}>{Number(it.monthly[m]||0).toFixed(2)}</td>)}
                    <td style={{textAlign:'right'}}>{Number(it.total||0).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h4 style={{marginTop:30}}>CAPEX Cash (After Offsets) & Net Funding</h4>
          {(() => {
            const months = FISCAL_MONTHS;
            const netOp = revenueResult.monthly_cash_net_operating || {};
            const netCash = revenueResult.monthly_net_cashflow || {};
            const cumNet = revenueResult.monthly_cum_net_cashflow || {};
            const peakFunding = revenueResult.peak_funding || 0;
            const sum = (obj)=> months.reduce((a,m)=> a + (obj[m]||0),0);
            // Group CAPEX items by group header and sum their monthly values
            const capexItems = revenueResult.capex_items || [];
            const groupHeaders = [
              'First Time Inventory',
              'First Time Capex',
              'Replacement Inventory',
              'Replacement Capex',
              'Capex People',
              'ROW Deposit',
              'Deposit Refund'
            ];
            const capexGroupMonthly = {};
            groupHeaders.forEach(group => {
              capexGroupMonthly[group] = { total: 0 };
              months.forEach(m => {
                capexGroupMonthly[group][m] = 0;
              });
            });
            capexItems.forEach(item => {
              if (groupHeaders.includes(item.group)) {
                months.forEach(m => {
                  capexGroupMonthly[item.group][m] += item.monthly[m] || 0;
                });
                capexGroupMonthly[item.group].total += item.total || 0;
              }
            });
            return (
              <div style={{overflowX:'auto'}}>
                <table border={1} cellPadding={4} style={{borderCollapse:'collapse', minWidth:'85%'}}>
                  <thead>
                    <tr>
                      <th>Line Item</th>
                      {months.map(m=> <th key={m}>{m}</th>)}
                      <th>{fiscalYear || 'Year Total'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr><td>Net Operating Flow</td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>{(netOp[m]||0).toFixed(2)}</td>)}<td style={{textAlign:'right'}}>{sum(netOp).toFixed(2)}</td></tr>
                    {groupHeaders.map(group => (
                      <tr key={group}><td>{group}</td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>{capexGroupMonthly[group][m].toFixed(2)}</td>)}<td style={{textAlign:'right'}}>{capexGroupMonthly[group].total.toFixed(2)}</td></tr>
                    ))}
                    <tr style={{background:'#e8ffe8'}}><td><b>Net Cashflow</b></td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>{(netCash[m]||0).toFixed(2)}</td>)}<td style={{textAlign:'right'}}><b>{sum(netCash).toFixed(2)}</b></td></tr>
                    <tr><td>Cumulative Net Cashflow</td>{months.map(m=> <td key={m} style={{textAlign:'right'}}>{(cumNet[m]||0).toFixed(2)}</td>)}<td style={{textAlign:'right'}}>{(cumNet[months[months.length-1]]||0).toFixed(2)}</td></tr>
                    <tr style={{background:'#f5f5f5'}}><td><b>Peak Funding (Most Negative Cum)</b></td><td colSpan={months.length} style={{textAlign:'center'}}>{peakFunding.toFixed(2)}</td><td></td></tr>
                  </tbody>
                </table>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);
  useEffect(()=>{ (async()=>{ try { const h= await fetchHealth(); setHealth(h.status);} catch(e){ setError(e.message);} })();},[]);
  return (
    <div style={{fontFamily:'sans-serif', padding:20}}>
      <h1>Fresh Budget App</h1>
      <div style={{display:'flex', gap:12, alignItems:'center'}}>
        <div>Backend health: {health || '...'}</div>
        <button onClick={async()=>{
          try{
            // Consolidated export for all known LOBs
            const LOBS = ['FTTH','Small Cell','SDU','Dark Fiber','OHFC','Active'];
            // Build workbook
            if(!window.XLSX) { alert('XLSX library not loaded. Please ensure you have internet access to the CDN.'); return; }
            const wb = window.XLSX.utils.book_new();
            for(const lob of LOBS){
              try{
                // Try to load saved snapshot first
                const saved = await loadLobData(lob);
                // Build payload with sensible defaults so backend doesn't reject missing required fields
                const defaultFiscal = (saved && (saved.fiscal_year||saved.year||saved.fy)) || 'FY25-26';
                const payload = { lob, fiscal_year: defaultFiscal, volumes: (saved && (saved.combos || saved.volumes)) || [], rates: (saved && saved.rates) || [] };
                // Request revenue calculation from backend (returns full P&L structure)
                const rev = await calculateRevenue(lob, payload);
                // Build a simple 2D array for P&L summary similar to UI table
                const months = rev.months || ['Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec','Jan','Feb','Mar'];
                const header = ['Line Item', ...months, rev.fiscal_year || 'Year Total'];
                const rows = [];
                // One-time, Recurring, Passthrough, Gross
                rows.push(['One-time Revenue', ...months.map(m=> rev.monthly_one_time_totals?.[m] ?? 0), (Object.values(rev.monthly_one_time_totals||{}).reduce((a,b)=>a+b,0)).toFixed(2)]);
                rows.push(['Recurring Revenue', ...months.map(m=> rev.monthly_recurring_totals?.[m] ?? 0), (Object.values(rev.monthly_recurring_totals||{}).reduce((a,b)=>a+b,0)).toFixed(2)]);
                rows.push(['Passthrough Revenue', ...months.map(m=> rev.monthly_cash_passthrough_inflow?.[m] ?? 0), 0]);
                rows.push(['Gross Revenue (Millions)', ...months.map(m=> rev.monthly_totals?.[m] ?? 0), rev.total_revenue ?? 0]);
                // Opex items
                rows.push([]);
                rows.push(['Direct Opex']);
                if(rev.opex_items && rev.opex_items.length){
                  for(const it of rev.opex_items){
                    rows.push([it.name, ...months.map(m=> it.monthly?.[m] ?? 0), it.total ?? 0]);
                  }
                }
                // Totals and margins
                rows.push([]);
                rows.push(['Total Opex', ...months.map(m=> rev.monthly_opex_totals?.[m] ?? 0), rev.total_opex ?? 0]);
                rows.push(['Operating Margin (Millions)', ...months.map(m=> rev.monthly_cash_net_operating?.[m] ?? 0), rev.total_cash_net_operating ?? 0]);

                const ws = window.XLSX.utils.aoa_to_sheet([header, ...rows]);
                window.XLSX.utils.book_append_sheet(wb, ws, lob.substring(0,31));
              }catch(errL){
                console.error('Failed to build sheet for', lob, errL);
                const ws = window.XLSX.utils.aoa_to_sheet([['Error building sheet for', lob, String(errL)]]);
                window.XLSX.utils.book_append_sheet(wb, ws, lob.substring(0,31));
              }
            }
            const wbout = window.XLSX.write(wb, {bookType:'xlsx', type:'array'});
            const blob = new Blob([wbout], {type: 'application/octet-stream'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url; a.download = 'Consolidated_PnL_All_LOBs.xlsx'; a.click();
            URL.revokeObjectURL(url);
          }catch(e){ console.error(e); alert('Export failed: '+ (e.message||e)); }
        }}>Download Consolidated P&L</button>
      </div>
      {error && <div style={{color:'red'}}>Error: {error}</div>}
      <VolumeDesignFlow />
    </div>
  );
}
