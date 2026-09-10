/**
 * The single HTTP client.
 *
 * Everything the app sends goes through here: it attaches the bearer token,
 * refreshes it once on a 401 and replays the request, and turns error bodies into
 * a consistent Error with a `status`. No component builds its own fetch.
 */

const STORAGE_KEY = 'lm.auth';
const API_URL_KEY = 'lm.apiBaseUrl';

const DEFAULT_BASE =
  import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function getApiBaseUrl() {
  try {
    return localStorage.getItem(API_URL_KEY) || DEFAULT_BASE;
  } catch {
    return DEFAULT_BASE;
  }
}

export function setApiBaseUrl(url) {
  try {
    if (url) localStorage.setItem(API_URL_KEY, url.replace(/\/$/, ''));
    else localStorage.removeItem(API_URL_KEY);
  } catch {
    /* private browsing - fall back to the default for this session */
  }
}

export function loadSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  try {
    if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore - the in-memory session still works for this tab */
  }
}

let session = loadSession();
let onUnauthorized = null;

export function setSession(next) {
  session = next;
  saveSession(next);
}

export function getSession() {
  return session;
}

/** Called when a refresh fails, so the app can route back to the login screen. */
export function onSessionExpired(handler) {
  onUnauthorized = handler;
}

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

async function parseError(response) {
  let detail = response.statusText || 'Request failed';
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') detail = body.detail;
    else if (Array.isArray(body?.detail)) {
      // FastAPI validation errors
      detail = body.detail
        .map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`)
        .join('; ');
    }
    return new ApiError(detail, response.status, body);
  } catch {
    return new ApiError(detail, response.status, null);
  }
}

async function refreshAccessToken() {
  if (!session?.refresh_token) return false;
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: session.refresh_token }),
    });
    if (!response.ok) return false;
    setSession(await response.json());
    return true;
  } catch {
    return false;
  }
}

async function request(path, { method = 'GET', body, formData, raw = false, signal } = {}) {
  const send = async () => {
    const headers = {};
    if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';

    return fetch(`${getApiBaseUrl()}${path}`, {
      method,
      headers,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
      signal,
    });
  };

  let response = await send();

  // One transparent refresh-and-replay, then give up.
  if (response.status === 401 && session?.refresh_token) {
    if (await refreshAccessToken()) {
      response = await send();
    } else {
      setSession(null);
      onUnauthorized?.();
    }
  }

  if (!response.ok) throw await parseError(response);
  if (raw) return response;
  if (response.status === 204) return null;
  return response.json();
}

/** Triggers a browser download for an endpoint that returns a file. */
async function download(path, fallbackName) {
  const response = await request(path, { raw: true });
  const blob = await response.blob();

  const disposition = response.headers.get('content-disposition') || '';
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const filename = match ? match[1] : fallbackName;

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoke on the next tick so Safari has started the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return filename;
}

function query(params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined) search.set(key, value);
  });
  const string = search.toString();
  return string ? `?${string}` : '';
}

export const api = {
  health: () => request('/api/v1/health'),

  auth: {
    login: (email, password) =>
      request('/api/v1/auth/login', { method: 'POST', body: { email, password } }),
    register: (payload) =>
      request('/api/v1/auth/register', { method: 'POST', body: payload }),
    me: () => request('/api/v1/auth/me'),
    users: () => request('/api/v1/auth/users'),
    setRole: (id, role) =>
      request(`/api/v1/auth/users/${id}/role${query({ role })}`, { method: 'PATCH' }),
    setActive: (id, active) =>
      request(`/api/v1/auth/users/${id}/active${query({ active })}`, { method: 'PATCH' }),
  },

  scan: {
    images: (files, { ocrLang = 'auto', aiEngine = 'rapidocr' } = {}) => {
      const form = new FormData();
      files.forEach((file) => form.append('images', file, file.name));
      return request(
        `/api/v1/analyze-package${query({ ocr_lang: ocrLang, ai_engine: aiEngine })}`,
        { method: 'POST', formData: form },
      );
    },
    text: (payload) => request('/api/v1/analyze-text', { method: 'POST', body: payload }),
    listing: (payload) => request('/api/v1/analyze-listing', { method: 'POST', body: payload }),
    verify: (payload) => request('/api/v1/verify-and-audit', { method: 'POST', body: payload }),
  },

  inspections: {
    search: (filters) => request(`/api/v1/inspections${query(filters)}`),
    get: (id) => request(`/api/v1/inspections/${id}`),
    evidenceUrl: (id) => `${getApiBaseUrl()}/api/v1/evidence/${id}`,
    /** Evidence is behind auth, so images are fetched as blobs rather than <img src>. */
    evidenceBlob: async (id) => {
      const response = await request(`/api/v1/evidence/${id}`, { raw: true });
      return URL.createObjectURL(await response.blob());
    },
  },

  dashboard: {
    stats: (days = 30) => request(`/api/v1/dashboard/stats${query({ days })}`),
  },

  reports: {
    download: (id, format = 'pdf') =>
      download(`/api/v1/reports/${id}${query({ format })}`, `compliance_report.${format}`),
    bulk: (filters) =>
      download(`/api/v1/reports${query(filters)}`, 'compliance_export.xlsx'),
  },

  rules: {
    database: () => request('/api/v1/rules/database'),
    reload: () => request('/api/v1/rules/reload', { method: 'POST' }),
    auditLog: (limit = 100) => request(`/api/v1/rules/audit-log${query({ limit })}`),
  },
};
