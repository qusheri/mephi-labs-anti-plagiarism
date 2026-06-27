const API_BASE_URL = window.ANTIPLAG_API_BASE_URL || 'http://127.0.0.1:8000';

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : null;

  if (!response.ok) {
    const message = payload?.detail || `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

window.antiplagApi = {
  createCheck({ title, course, file }) {
    const formData = new FormData();
    formData.append('title', title);
    if (course) formData.append('course', course);
    formData.append('file', file);

    return requestJson('/api/v1/checks', {
      method: 'POST',
      body: formData,
    });
  },

  listChecks({ limit = 50, offset = 0 } = {}) {
    return requestJson(`/api/v1/checks?limit=${limit}&offset=${offset}`);
  },

  getCheck(taskId) {
    return requestJson(`/api/v1/checks/${encodeURIComponent(taskId)}`);
  },

  getReport(taskId) {
    return requestJson(`/api/v1/checks/${encodeURIComponent(taskId)}/report`);
  },

  compareFiles({ fileA, fileB, method = 'dfg' }) {
    const formData = new FormData();
    formData.append('file_a', fileA);
    formData.append('file_b', fileB);
    formData.append('method', method);

    return requestJson('/api/v1/similarity', {
      method: 'POST',
      body: formData,
    });
  },
};
