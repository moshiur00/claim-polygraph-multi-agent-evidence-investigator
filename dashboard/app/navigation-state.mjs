export const WORKSPACE_VIEWS = ["investigations", "review_queue", "system_health"];

export function parseNavigationState(search) {
  const params = new URLSearchParams(search);
  const requestedView = params.get("view");
  const view = WORKSPACE_VIEWS.includes(requestedView) ? requestedView : "investigations";
  const investigationId = params.get("investigation")?.trim() || null;
  return { view, investigationId };
}

export function serializeNavigationState({ view, investigationId }) {
  const params = new URLSearchParams();
  if (view !== "investigations") params.set("view", view);
  if (investigationId) params.set("investigation", investigationId);
  const query = params.toString();
  return query ? `?${query}` : "/";
}
