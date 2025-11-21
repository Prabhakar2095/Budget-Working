import React from 'react';

function Feedback({ feedback }) {
  if (!feedback.message) return null;
  return (
    <div style={{ marginBottom: 16, color: feedback.type === 'error' ? 'red' : 'green', fontWeight: 'bold' }}>
      {feedback.message}
    </div>
  );
}

export default Feedback;
