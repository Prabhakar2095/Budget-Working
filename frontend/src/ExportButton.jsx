import React from 'react';

function ExportButton({ lob, setFeedback }) {
  const handleExport = async () => {
    try {
      const resp = await fetch('/api/lob/export');
      if (!resp.ok) throw new Error('Export failed');
      const blob = await resp.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${lob}_export.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
      setFeedback({ type: 'success', message: 'Export successful.' });
    } catch (e) {
      setFeedback({ type: 'error', message: 'Export failed.' });
    }
  };
  return (
    <button style={{ marginTop: 16, padding: '8px 18px', fontWeight: 'bold' }} onClick={handleExport}>
      Export Data to Excel
    </button>
  );
}

export default ExportButton;
