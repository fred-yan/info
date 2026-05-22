/**
 * Centralized API client with timeout, error handling, and base URL configuration.
 */

export class ApiError extends Error {
  public readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export class ApiClient {
  private baseUrl: string;
  private timeout: number;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || import.meta.env.VITE_API_BASE_URL || '/api';
    this.timeout = 10000;
  }

  async get<T>(path: string, params?: Record<string, string>): Promise<T> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      // Build URL: if baseUrl is relative (e.g., "/api"), concatenate with path
      // If baseUrl is absolute (e.g., "http://localhost:8000/api"), use URL constructor
      let fullUrl: string;
      if (this.baseUrl.startsWith('http')) {
        const url = new URL(path, this.baseUrl.endsWith('/') ? this.baseUrl : this.baseUrl + '/');
        if (params) {
          Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
        }
        fullUrl = url.toString();
      } else {
        // Relative base URL — simple string concatenation
        const base = this.baseUrl.endsWith('/') ? this.baseUrl.slice(0, -1) : this.baseUrl;
        const p = path.startsWith('/') ? path : '/' + path;
        fullUrl = base + p;
        if (params) {
          const searchParams = new URLSearchParams(params);
          fullUrl += '?' + searchParams.toString();
        }
      }

      const response = await fetch(fullUrl, { signal: controller.signal });

      if (!response.ok) {
        throw new ApiError(response.status, await response.text());
      }

      return await response.json() as T;
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new ApiError(408, '请求超时，请检查网络连接');
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }
}

export const apiClient = new ApiClient();
