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
  funnel: (courseId) => request(`/stats/funnel${courseId ? `?course_id=${courseId}` : ''}`),
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
  saveQuiz: (id, quizData) =>
    request(`/lessons/${id}/quiz`, {
      method: 'PUT',
      body: JSON.stringify(quizData),
    }),
  deleteQuiz: (id) =>
    request(`/lessons/${id}/quiz`, { method: 'DELETE' }),
};

// ── Users ────────────────────────────
export const users = {
  list: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/users${qs ? '?' + qs : ''}`);
  },
  get: (id) => request(`/users/${id}`),
  byLesson: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/users/by-lesson${qs ? '?' + qs : ''}`);
  },
  byLessonDetail: (lessonId) => request(`/users/by-lesson/${lessonId}`),
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
   * Get upload config (platform, max size, split settings)
   */
  config: () => request('/upload/config'),

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
      let serverWaitTimer = null;
      let serverPct = 90;

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && onProgress) {
          // 0-90% = upload to our server
          const pct = Math.round((e.loaded / e.total) * 90);
          onProgress(pct);
        }
      });

      // When upload to server finishes, animate 90→98% while waiting for server to forward to Telegram
      xhr.upload.addEventListener('load', () => {
        if (onProgress) {
          onProgress(90);
          serverWaitTimer = setInterval(() => {
            if (serverPct < 98) {
              serverPct += 0.5;
              onProgress(Math.round(serverPct));
            }
          }, 2000);
        }
      });

      xhr.addEventListener('load', () => {
        if (serverWaitTimer) clearInterval(serverWaitTimer);
        if (xhr.status === 401) {
          clearToken();
          window.location.href = '/login';
          return reject(new Error('Unauthorized'));
        }
        try {
          const data = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) {
            if (onProgress) onProgress(100);
            resolve(data);
          } else {
            reject(new Error(data.detail || `HTTP ${xhr.status}`));
          }
        } catch {
          reject(new Error(`HTTP ${xhr.status}`));
        }
      });

      xhr.addEventListener('error', () => {
        if (serverWaitTimer) clearInterval(serverWaitTimer);
        reject(new Error('خطا در اتصال'));
      });
      xhr.addEventListener('abort', () => {
        if (serverWaitTimer) clearInterval(serverWaitTimer);
        reject(new Error('آپلود لغو شد'));
      });

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

// ── Media Library ────────────────────
export const media = {
  list: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/media${qs ? '?' + qs : ''}`);
  },
  get: (id) => request(`/media/${id}`),
  delete: (id) => request(`/media/${id}`, { method: 'DELETE' }),
  platform: () => request('/media/platform'),
};

// ── Settings ─────────────────────────────
export const settings = {
  // Company info
  getCompany: () => request('/settings/company'),
  updateCompany: (items) => request('/settings/company', {
    method: 'PUT',
    body: JSON.stringify(items),
  }),
  // Webhooks
  getWebhooks: () => request('/settings/webhooks'),
  createWebhook: (data) => request('/settings/webhooks', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateWebhook: (id, data) => request(`/settings/webhooks/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteWebhook: (id) => request(`/settings/webhooks/${id}`, { method: 'DELETE' }),
  testWebhook: (id) => request(`/settings/webhooks/${id}/test`, { method: 'POST' }),
  // Bot texts
  getBotTexts: () => request('/settings/bot-texts'),
  updateBotText: (id, value) => request(`/settings/bot-texts/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ value }),
  }),
  // Scoring rules
  getScoringRules: () => request('/settings/scoring-rules'),
  updateScoringRule: (id, data) => request(`/settings/scoring-rules/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  // SMS & Engagement
  getSmsStatus: () => request('/settings/sms-status'),
};

// ── Messaging ─────────────────────────
export const messaging = {
  broadcast: (data) => request('/messaging/broadcast', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  broadcastHistory: (page = 1, perPage = 10) =>
    request(`/messaging/broadcast/history?page=${page}&per_page=${perPage}`),
  broadcastPreview: (target = 'all', tags = '') =>
    request(`/messaging/broadcast/preview?target=${target}&tags=${tags}`),
  sendDirect: (userId, message) => request(`/messaging/send/${userId}`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  }),
};

// ── User Actions ──────────────────────
export const userActions = {
  updateTags: (userId, tags) => request(`/users/${userId}/tags`, {
    method: 'PUT',
    body: JSON.stringify({ tags }),
  }),
  block: (userId, blocked) => request(`/users/${userId}/block`, {
    method: 'PUT',
    body: JSON.stringify({ blocked }),
  }),
  resetProgress: (userId) => request(`/users/${userId}/reset`, {
    method: 'POST',
  }),
  deleteUser: (userId) => request(`/users/${userId}`, {
    method: 'DELETE',
  }),
};

// ── Exports ───────────────────────────
export const exports = {
  users: (status) => {
    const qs = status ? `?status=${status}` : '';
    return `/api/messaging/export/users${qs}`;
  },
  progress: () => '/api/messaging/export/progress',
  analytics: () => '/api/messaging/export/analytics',
};