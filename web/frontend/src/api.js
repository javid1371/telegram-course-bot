/**
 * API client for the admin panel backend.
 */
const API_BASE = '/api';

function getToken() {
  return localStorage.getItem('admin_token');
}

export function setToken(token) {
  localStorage.setItem('admin_token', token);
}

export function clearToken() {
  localStorage.removeItem('admin_token');
}

export function isAuthenticated() {
  return !!getToken();
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Don't set Content-Type for FormData (browser sets it with boundary)
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (resp.status === 401) {
    clearToken();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'خطای ناشناخته' }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }

  return resp.json();
}

// ── Auth ─────────────────────────────
export const auth = {
  login: (username, password) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  me: () => request('/auth/me'),
};

// ── Stats ────────────────────────────
export const stats = {
  get: () => request('/stats'),
};

// ── Courses ──────────────────────────
export const courses = {
  list: () => request('/courses'),
  get: (id) => request(`/courses/${id}`),
  create: (data) =>
    request('/courses', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) =>
    request(`/courses/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) =>
    request(`/courses/${id}`, { method: 'DELETE' }),
  lessons: (courseId) => request(`/courses/${courseId}/lessons`),
};

// ── Lessons ──────────────────────────
export const lessons = {
  get: (id) => request(`/lessons/${id}`),
  create: (data) =>
    request('/lessons', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) =>
    request(`/lessons/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) =>
    request(`/lessons/${id}`, { method: 'DELETE' }),
  getContents: (id) => request(`/lessons/${id}/contents`),
  updateContents: (id, contents) =>
    request(`/lessons/${id}/contents`, {
      method: 'PUT',
      body: JSON.stringify({ contents }),
    }),
  addContent: (id, item) =>
    request(`/lessons/${id}/contents`, {
      method: 'POST',
      body: JSON.stringify(item),
    }),
  deleteContent: (id, index) =>
    request(`/lessons/${id}/contents/${index}`, { method: 'DELETE' }),
  replaceContent: (id, index, item) =>
    request(`/lessons/${id}/contents/${index}`, {
      method: 'PUT',
      body: JSON.stringify(item),
    }),
  saveForm: (id, formData) =>
    request(`/lessons/${id}/form`, {
      method: 'PUT',
      body: JSON.stringify(formData),
    }),
  deleteForm: (id) =>
    request(`/lessons/${id}/form`, { method: 'DELETE' }),
};

// ── Users ────────────────────────────
export const users = {
  list: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/users${qs ? '?' + qs : ''}`);
  },
  get: (id) => request(`/users/${id}`),
};

// ── Registration Fields ──────────────
export const registrationFields = {
  list: () => request('/registration-fields'),
  get: (id) => request(`/registration-fields/${id}`),
  create: (data) =>
    request('/registration-fields', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) =>
    request(`/registration-fields/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) =>
    request(`/registration-fields/${id}`, { method: 'DELETE' }),
  reorder: (items) =>
    request('/registration-fields/reorder', {
      method: 'PUT',
      body: JSON.stringify({ items }),
    }),
};

// ── Upload ───────────────────────────
export const upload = {
  /**
   * Upload file with progress tracking via XMLHttpRequest.
   * @param {File} file
   * @param {string} contentType
   * @param {string} caption
   * @param {(percent: number) => void} onProgress - called with 0-100
   * @returns {Promise<{file_id: string, type: string, filename: string}>}
   */
  file: (file, contentType, caption = '', onProgress = null) => {
    return new Promise((resolve, reject) => {
      const token = getToken();
      const form = new FormData();
      form.append('file', file);
      form.append('content_type', contentType);
      if (caption) form.append('caption', caption);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/upload`);
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

      // Upload progress (local → server)
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && onProgress) {
          // 0-90% = upload to our server, 90-100% = server forwarding to Telegram
          const pct = Math.round((e.loaded / e.total) * 90);
          onProgress(pct);
        }
      });

      xhr.addEventListener('load', () => {
        if (onProgress) onProgress(100);
        if (xhr.status === 401) {
          clearToken();
          window.location.href = '/login';
          return reject(new Error('Unauthorized'));
        }
        try {
          const data = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(data);
          } else {
            reject(new Error(data.detail || `HTTP ${xhr.status}`));
          }
        } catch {
          reject(new Error(`HTTP ${xhr.status}`));
        }
      });

      xhr.addEventListener('error', () => reject(new Error('خطا در اتصال')));
      xhr.addEventListener('abort', () => reject(new Error('آپلود لغو شد')));

      xhr.send(form);
    });
  },

  /**
   * Upload a large file by splitting it on the server.
   * Returns an array of content block items (each with file_id).
   * @param {File} file
   * @param {string} contentType
   * @param {string} caption
   * @param {(percent: number, status: string) => void} onProgress
   * @returns {Promise<{parts: Array<{type: string, file_id: string}>, total_parts: number}>}
   */
  splitFile: (file, contentType, caption = '', onProgress = null) => {
    return new Promise((resolve, reject) => {
      const token = getToken();
      const form = new FormData();
      form.append('file', file);
      form.append('content_type', contentType);
      if (caption) form.append('caption', caption);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/upload/split`);
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && onProgress) {
          // 0-50% = uploading to our server
          const pct = Math.round((e.loaded / e.total) * 50);
          onProgress(pct, 'آپلود به سرور...');
        }
      });

      xhr.addEventListener('load', () => {
        if (onProgress) onProgress(100, 'تکمیل شد');
        if (xhr.status === 401) {
          clearToken();
          window.location.href = '/login';
          return reject(new Error('Unauthorized'));
        }
        try {
          const data = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(data);
          } else {
            reject(new Error(data.detail || `HTTP ${xhr.status}`));
          }
        } catch {
          reject(new Error(`HTTP ${xhr.status}`));
        }
      });

      xhr.addEventListener('error', () => reject(new Error('خطا در اتصال')));
      xhr.addEventListener('abort', () => reject(new Error('آپلود لغو شد')));

      // After upload finishes, server is splitting & uploading parts (50-99%)
      let serverPhaseStarted = false;
      xhr.upload.addEventListener('loadend', () => {
        if (!serverPhaseStarted) {
          serverPhaseStarted = true;
          if (onProgress) onProgress(55, 'تقسیم و آپلود قطعات...');
          // Simulate progress during server processing
          let fakePct = 55;
          const interval = setInterval(() => {
            if (fakePct < 95) {
              fakePct += 2;
              if (onProgress) onProgress(fakePct, 'تقسیم و آپلود قطعات...');
            } else {
              clearInterval(interval);
            }
          }, 3000);
          xhr._progressInterval = interval;
        }
      });

      xhr.addEventListener('loadend', () => {
        if (xhr._progressInterval) clearInterval(xhr._progressInterval);
      });

      xhr.send(form);
    });
  },
};
