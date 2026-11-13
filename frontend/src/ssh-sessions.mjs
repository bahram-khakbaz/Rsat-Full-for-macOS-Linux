export const emptySessions = { items: [], activeId: null };

export function sessionReducer(state, action) {
  if (action.type === 'open') {
    if (state.items.some((x) => x.id === action.id)) return state;
    const { id, name, host, port, username } = action.device;
    const item = {
      id: action.id,
      baseUrl: action.baseUrl,
      device: { id, name, host, port, username },
      status: 'CONNECTING',
    };
    return { items: [...state.items, item], activeId: item.id };
  }
  if (action.type === 'select')
    return state.items.some((x) => x.id === action.id) ? { ...state, activeId: action.id } : state;
  if (action.type === 'status') {
    if (!state.items.some((x) => x.id === action.id && x.status !== action.status)) return state;
    return {
      ...state,
      items: state.items.map((x) => (x.id === action.id ? { ...x, status: action.status } : x)),
    };
  }
  if (action.type === 'close') {
    const index = state.items.findIndex((x) => x.id === action.id);
    if (index < 0) return state;
    const items = state.items.filter((x) => x.id !== action.id);
    return {
      items,
      activeId:
        state.activeId === action.id
          ? (items[Math.min(index, items.length - 1)]?.id ?? null)
          : state.activeId,
    };
  }
  return state;
}
