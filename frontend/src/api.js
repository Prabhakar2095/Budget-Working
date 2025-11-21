import API_BASE from './config';

// Always use explicit backend base to avoid depending on dev-server proxy
const base = API_BASE;

async function fetchJson(path, opts) {
  const url = `${base}${path}`;
  try {
    const r = await fetch(url, opts);
    return r;
  } catch (err) {
    // Log detailed info for debugging in the browser console
    console.error('Primary fetch failed', { url, opts, err });
    // Try fallback to localhost hostname (some environments prefer localhost over 127.0.0.1)
    try {
      const altBase = base.replace('127.0.0.1', 'localhost');
      const altUrl = `${altBase}${path}`;
      console.info('Attempting fallback fetch to', altUrl);
      const r2 = await fetch(altUrl, opts);
      return r2;
    } catch (err2) {
      console.error('Fallback fetch failed', { path, err2 });
      // Re-throw the original error to keep existing error handling paths
      throw err;
    }
  }
}

export async function healthCheck() {
  return fetchHealth();
}

export async function fetchHealth() {
  const r = await fetchJson('/api/health');
  if (!r.ok) throw new Error('Health check failed');
  return r.json();
}

export async function getVolumeModel(lob, params) {
  const r = await fetchJson('/api/volume/multiyear/dynamic', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lob, ...params })
  });
  if (!r.ok) throw new Error('Volume modeling failed');
  return r.json();
}

export async function calculateRevenue(lob, params) {
  const r = await fetchJson('/api/revenue/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lob, ...params })
  });
  if (!r.ok) {
    // Try to extract useful error text from response body for debugging
    let errMsg = 'Revenue calculation failed';
    try {
      const text = await r.text();
      if (text) {
        try {
          const j = JSON.parse(text);
          if (j && (j.detail || j.error || j.message)) errMsg = j.detail || j.error || j.message;
          else errMsg = JSON.stringify(j);
        } catch (e) {
          errMsg = text;
        }
      }
    } catch (e) {
      // ignore
    }
    throw new Error(errMsg);
  }
  return r.json();
}

export async function exportLob(lob) {
  const resp = await fetchJson('/api/lob/export');
  if (!resp.ok) throw new Error('Export failed');
  return await resp.blob();
}

export async function fetchSampleBudget() {
  const r = await fetchJson('/api/sample/budget');
  if (!r.ok) throw new Error('Sample budget failed');
  return r.json();
}

// Save full modeling state for a LOB
export async function saveLob(lob, data) {
  const r = await fetchJson('/api/lob/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lob, ...data })
  });
  if (!r.ok) throw new Error('Failed to save LOB');
  return r.json();
}

// Load modeling state for a LOB
export async function loadLobData(lob) {
  const r = await fetchJson(`/api/lob/get/${encodeURIComponent(lob)}`);
  if (!r.ok) {
    if (r.status === 404) return null; // No data yet
    throw new Error('Failed to load LOB data');
  }
  const result = await r.json();
  let data = result.data || null;
  // Backend stores snapshots as JSON strings; parse if necessary
  if (typeof data === 'string') {
    try {
      data = JSON.parse(data);
    } catch (e) {
      // leave as string if parse fails
    }
  }
  return data;
}
