import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import MessageBoxLoading from '@/components/MessageBoxLoading';

describe('MessageBoxLoading', () => {
  it('renders loading skeleton', () => {
    const { container } = render(<MessageBoxLoading />);
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });
});