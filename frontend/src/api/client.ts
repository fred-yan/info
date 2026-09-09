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

  /** Build full URL from path + optional query params */
  private buildUrl(path: string, params?: Record<string, string>): string {
    if (this.baseUrl.startsWith('http')) {
      const url = new URL(path, this.baseUrl.endsWith('/') ? this.baseUrl : this.baseUrl + '/');
      if (params) {
        Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
      }
      return url.toString();
    }
    const base = this.baseUrl.endsWith('/') ? this.baseUrl.slice(0, -1) : this.baseUrl;
    const p = path.startsWith('/') ? path : '/' + path;
    let fullUrl = base + p;
    if (params) {
      fullUrl += '?' + new URLSearchParams(params).toString();
    }
    return fullUrl;
  }

  async get<T>(path: string, params?: Record<string, string>): Promise<T> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(this.buildUrl(path, params), {
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new ApiError(response.status, await response.text());
      }
      return await response.json() as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new ApiError(408, '请求超时，请检查网络连接');
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * POST — uses a 5-minute timeout to support long-running LLM extraction calls.
   */
  async post<T>(path: string, body?: unknown): Promise<T> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 min

    try {
      const response = await fetch(this.buildUrl(path), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new ApiError(response.status, await response.text());
      }
      return await response.json() as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new ApiError(408, '请求超时，LLM 处理时间过长');
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }
}

export const apiClient = new ApiClient();
