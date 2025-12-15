import React, { useState } from 'react';

function LobManager({ setLob, setFeedback }) {
  const [lobInput, setLobInput] = useState('');
  const handleSelect = () => {
    if (!lobInput) {
      setFeedback({ type: 'error', message: 'Please select a LOB.' });
      return;
    }
    setLob(lobInput);
    setFeedback({ type: 'success', message: `LOB selected: ${lobInput}` });
  };
  return (
    <div style={{ marginBottom: 24 }}>
      <label>
        <strong>Select LOB:</strong>
        <select value={lobInput} onChange={e => setLobInput(e.target.value)} style={{ marginLeft: 12 }}>
          <option value=''>-- Choose --</option>
          <option value='FTTH'>FTTH</option>
          <option value='Small Cell'>Small Cell</option>
          <option value='SDU'>SDU</option>
          <option value='Dark Fiber'>Dark Fiber</option>
          <option value='OHFC'>OHFC</option>
          <option value='Active'>Active</option>
          <option value='Co Build'>Co Build</option>
          <option value='Active'>Active</option>
        </select>
      </label>
      <button style={{ marginLeft: 16 }} onClick={handleSelect}>Confirm</button>
    </div>
  );
}

export default LobManager;
