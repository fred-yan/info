import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import NavBar from './index';

describe('NavBar', () => {
  it('renders both navigation links', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <NavBar />
      </MemoryRouter>
    );

    expect(screen.getByText('热点分析')).toBeInTheDocument();
    expect(screen.getByText('新闻动态')).toBeInTheDocument();
  });

  it('highlights the hotspot link when on "/" route', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <NavBar />
      </MemoryRouter>
    );

    const hotspotLink = screen.getByText('热点分析');
    const feedLink = screen.getByText('新闻动态');

    expect(hotspotLink.className).toMatch(/active/);
    expect(feedLink.className).not.toMatch(/active/);
  });

  it('highlights the feed link when on "/feed" route', () => {
    render(
      <MemoryRouter initialEntries={['/feed']}>
        <NavBar />
      </MemoryRouter>
    );

    const hotspotLink = screen.getByText('热点分析');
    const feedLink = screen.getByText('新闻动态');

    expect(feedLink.className).toMatch(/active/);
    expect(hotspotLink.className).not.toMatch(/active/);
  });

  it('links point to correct routes', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <NavBar />
      </MemoryRouter>
    );

    const hotspotLink = screen.getByText('热点分析').closest('a');
    const feedLink = screen.getByText('新闻动态').closest('a');

    expect(hotspotLink).toHaveAttribute('href', '/');
    expect(feedLink).toHaveAttribute('href', '/feed');
  });

  it('has accessible navigation landmark', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <NavBar />
      </MemoryRouter>
    );

    expect(screen.getByRole('navigation', { name: '主导航' })).toBeInTheDocument();
  });
});
