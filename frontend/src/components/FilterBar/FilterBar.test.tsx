import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { FilterBar } from './index';

const defaultProps = {
  platforms: ['apnews', 'economist', 'ftchinese'],
  sections: ['politics', 'tech', 'finance'],
  selectedPlatforms: ['apnews'],
  selectedSection: null,
  onPlatformChange: vi.fn(),
  onSectionChange: vi.fn(),
};

describe('FilterBar', () => {
  it('renders platform checkboxes for each platform', () => {
    render(<FilterBar {...defaultProps} />);

    for (const platform of defaultProps.platforms) {
      expect(screen.getByLabelText(platform)).toBeInTheDocument();
    }
  });

  it('renders the "全部平台" label', () => {
    render(<FilterBar {...defaultProps} />);
    expect(screen.getByText('全部平台')).toBeInTheDocument();
  });

  it('renders the "栏目" label', () => {
    render(<FilterBar {...defaultProps} />);
    expect(screen.getByText('栏目')).toBeInTheDocument();
  });

  it('checks selected platforms', () => {
    render(<FilterBar {...defaultProps} />);

    const apnewsCheckbox = screen.getByLabelText('apnews') as HTMLInputElement;
    const economistCheckbox = screen.getByLabelText('economist') as HTMLInputElement;

    expect(apnewsCheckbox.checked).toBe(true);
    expect(economistCheckbox.checked).toBe(false);
  });

  it('calls onPlatformChange when a platform is toggled on', async () => {
    const onPlatformChange = vi.fn();
    render(<FilterBar {...defaultProps} onPlatformChange={onPlatformChange} />);

    await userEvent.click(screen.getByLabelText('economist'));

    expect(onPlatformChange).toHaveBeenCalledWith(['apnews', 'economist']);
  });

  it('calls onPlatformChange when a platform is toggled off', async () => {
    const onPlatformChange = vi.fn();
    render(<FilterBar {...defaultProps} onPlatformChange={onPlatformChange} />);

    await userEvent.click(screen.getByLabelText('apnews'));

    expect(onPlatformChange).toHaveBeenCalledWith([]);
  });

  it('renders section select with "All" option', () => {
    render(<FilterBar {...defaultProps} />);

    const select = screen.getByLabelText('栏目') as HTMLSelectElement;
    expect(select).toBeInTheDocument();
    expect(select.value).toBe('');

    const options = select.querySelectorAll('option');
    expect(options[0].textContent).toBe('All');
    expect(options[0].value).toBe('');
  });

  it('renders section options from props', () => {
    render(<FilterBar {...defaultProps} />);

    for (const section of defaultProps.sections) {
      expect(screen.getByRole('option', { name: section })).toBeInTheDocument();
    }
  });

  it('calls onSectionChange with section value when selected', async () => {
    const onSectionChange = vi.fn();
    render(<FilterBar {...defaultProps} onSectionChange={onSectionChange} />);

    await userEvent.selectOptions(screen.getByLabelText('栏目'), 'tech');

    expect(onSectionChange).toHaveBeenCalledWith('tech');
  });

  it('calls onSectionChange with null when "All" is selected', async () => {
    const onSectionChange = vi.fn();
    render(
      <FilterBar
        {...defaultProps}
        selectedSection="tech"
        onSectionChange={onSectionChange}
      />
    );

    await userEvent.selectOptions(screen.getByLabelText('栏目'), '');

    expect(onSectionChange).toHaveBeenCalledWith(null);
  });

  it('reflects selectedSection in the select value', () => {
    render(<FilterBar {...defaultProps} selectedSection="finance" />);

    const select = screen.getByLabelText('栏目') as HTMLSelectElement;
    expect(select.value).toBe('finance');
  });
});
