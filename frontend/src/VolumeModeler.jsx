import React, { useState } from 'react';

function VolumeModeler({ lob, setFeedback, getVolumeModel }) {
  const [volume, setVolume] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!volume || isNaN(volume) || Number(volume) <= 0) {
      setFeedback({ type: 'error', message: 'Please enter a valid volume.' });
      return;
    }
    setLoading(true);
    setFeedback({ type: '', message: '' });
    try {
      const res = await getVolumeModel(lob, { volume: Number(volume) });
      setResult(res);
      setFeedback({ type: 'success', message: 'Volume model calculated.' });
    } catch (err) {
      setFeedback({ type: 'error', message: 'Volume modeling failed.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ marginBottom: 24 }}>
      <h2>Volume Modeler</h2>
      <div>Model volumes for LOB: <strong>{lob}</strong></div>
      <form onSubmit={handleSubmit} style={{ marginTop: 12 }}>
        <label>
          Enter Volume:&nbsp;
          <input
            type="number"
            value={volume}
            onChange={e => setVolume(e.target.value)}
            min="1"
            required
            style={{ width: 120 }}
          />
        </label>
        <button type="submit" style={{ marginLeft: 12 }} disabled={loading}>
          {loading ? 'Calculating...' : 'Calculate'}
        </button>
      </form>
      {result && (
        <div style={{ marginTop: 16 }}>
          <strong>Result:</strong> {JSON.stringify(result)}
        </div>
      )}
    </div>
  );
}

export default VolumeModeler;
