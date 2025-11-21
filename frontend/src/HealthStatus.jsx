import React from 'react';

function HealthStatus({ health }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <strong>Backend Health:</strong> <span style={{ color: health === 'ok' ? 'green' : 'red' }}>{health}</span>
    </div>
  );
}

export default HealthStatus;
