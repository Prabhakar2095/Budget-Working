import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from './App';

test('renders Budget Working App title', () => {
  render(<App />);
  const title = screen.getByText(/Budget Working App/i);
  expect(title).toBeInTheDocument();
});
