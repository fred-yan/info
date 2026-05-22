import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { TabSwitcher } from './index';

describe('TabSwitcher', () => {
  it('renders two tabs with correct labels', () => {
    render(<TabSwitcher activeGroup="domestic" onGroupChange={() => {}} />);

    expect(screen.getByRole('tab', { name: '国内热点' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '国际热点' })).toBeInTheDocument();
  });

  it('marks the domestic tab as active when activeGroup is domestic', () => {
    render(<TabSwitcher activeGroup="domestic" onGroupChange={() => {}} />);

    const domesticTab = screen.getByRole('tab', { name: '国内热点' });
    const internationalTab = screen.getByRole('tab', { name: '国际热点' });

    expect(domesticTab).toHaveAttribute('aria-selected', 'true');
    expect(internationalTab).toHaveAttribute('aria-selected', 'false');
    expect(domesticTab).toHaveClass('tab-switcher__tab--active');
    expect(internationalTab).not.toHaveClass('tab-switcher__tab--active');
  });

  it('marks the international tab as active when activeGroup is international', () => {
    render(<TabSwitcher activeGroup="international" onGroupChange={() => {}} />);

    const domesticTab = screen.getByRole('tab', { name: '国内热点' });
    const internationalTab = screen.getByRole('tab', { name: '国际热点' });

    expect(domesticTab).toHaveAttribute('aria-selected', 'false');
    expect(internationalTab).toHaveAttribute('aria-selected', 'true');
    expect(internationalTab).toHaveClass('tab-switcher__tab--active');
    expect(domesticTab).not.toHaveClass('tab-switcher__tab--active');
  });

  it('calls onGroupChange with "international" when international tab is clicked', async () => {
    const user = userEvent.setup();
    const onGroupChange = vi.fn();

    render(<TabSwitcher activeGroup="domestic" onGroupChange={onGroupChange} />);

    await user.click(screen.getByRole('tab', { name: '国际热点' }));

    expect(onGroupChange).toHaveBeenCalledTimes(1);
    expect(onGroupChange).toHaveBeenCalledWith('international');
  });

  it('calls onGroupChange with "domestic" when domestic tab is clicked', async () => {
    const user = userEvent.setup();
    const onGroupChange = vi.fn();

    render(<TabSwitcher activeGroup="international" onGroupChange={onGroupChange} />);

    await user.click(screen.getByRole('tab', { name: '国内热点' }));

    expect(onGroupChange).toHaveBeenCalledTimes(1);
    expect(onGroupChange).toHaveBeenCalledWith('domestic');
  });

  it('renders a tablist with accessible label', () => {
    render(<TabSwitcher activeGroup="domestic" onGroupChange={() => {}} />);

    expect(screen.getByRole('tablist', { name: '热点分组切换' })).toBeInTheDocument();
  });
});
