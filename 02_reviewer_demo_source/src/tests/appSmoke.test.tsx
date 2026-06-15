import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import App from '../App';
import GlossaryPage from '../pages/GlossaryPage';
import MethodsPage from '../pages/MethodsPage';

describe('App smoke', () => {
  test('renders title and overview', () => {
    render(<App />);
    expect(screen.getByText('KOM Reviewer Interface')).toBeInTheDocument();
    expect(screen.getByText('Study summary')).toBeInTheDocument();
  });

  test('GlossaryPage can show naive RAG baseline', () => {
    render(<GlossaryPage />);
    expect(screen.getByText('naive RAG baseline')).toBeInTheDocument();
    expect(screen.getByText(/single-stage vector top-k retrieval/i)).toBeInTheDocument();
  });

  test('MethodsPage displays safety-critical error rate formula', () => {
    render(<MethodsPage />);
    expect(screen.getAllByText(/safety-critical error rate/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Number of safety-critical errors/i)).toBeInTheDocument();
  });
});
