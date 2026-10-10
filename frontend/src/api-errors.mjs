export function formatApiError(data) {
  if (typeof data?.detail === 'string') return data.detail
  if (Array.isArray(data?.detail)) {
    return data.detail.map(error => {
      const field = Array.isArray(error.loc) ? error.loc.filter(x => x !== 'body').join('.') : 'Field'
      return field + ': ' + (typeof error.msg === 'string' ? error.msg : 'Invalid value')
    }).join('; ')
  }
  return 'Request failed'
}
