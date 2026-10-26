export async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: options.body instanceof FormData
      ? options.headers
      : { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(payload.detail || `Request failed (${response.status})`)
    error.status = response.status
    throw error
  }
  return payload
}

export const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body) })
