import React, { useState, useEffect } from 'react';

const DEFAULT_OPEX_ITEMS = [
  "Rent",
  "Electricity",
  "People Cost",
  "Network O&M",
  "Warehouse Rental",
  "Operational Others",
  "Travelling & Sales Promotions",
  "Freight Internal & other direct",
  "Insurance",
  "Passthrough Expense",
  "Loss on Sale of Scrap",
  "Software & IT"
];

export default function OpexItems({ opexItems, setOpexItems }) {
  const [newItem, setNewItem] = useState('');

  useEffect(() => {
    if (!opexItems || opexItems.length === 0) {
      setOpexItems(DEFAULT_OPEX_ITEMS.map(name => ({ name })));
    }
  }, [opexItems, setOpexItems]);

  const handleAdd = () => {
    const name = newItem.trim();
    if (name && !opexItems.some(item => item.name === name)) {
      setOpexItems([...opexItems, { name }]);
      setNewItem('');
    }
  };

  const handleDelete = (name) => {
    setOpexItems(opexItems.filter(item => item.name !== name));
  };

  return (
    <div>
      <h3>OPEX Items</h3>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        {opexItems.map(item => (
          <div key={item.name} style={{ display: 'flex', alignItems: 'center' }}>
            <span>{item.name}</span>
            <button style={{ marginLeft: 8 }} onClick={() => handleDelete(item.name)}>Delete</button>
          </div>
        ))}
      </div>
      <input
        type="text"
        value={newItem}
        onChange={e => setNewItem(e.target.value)}
        placeholder="Add new OPEX item"
      />
      <button onClick={handleAdd}>Add</button>
    </div>
  );
}
