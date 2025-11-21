import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';

const el = document.getElementById('root');
if (el) {
  const root = createRoot(el);
  root.render(<App />);
} else {
  console.error('Root element not found');
}
