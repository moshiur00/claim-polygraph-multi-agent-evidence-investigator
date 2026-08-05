export type WorkspaceView = "investigations" | "review_queue" | "system_health";
export function parseNavigationState(search: string): { view: WorkspaceView; investigationId: string | null };
export function serializeNavigationState(state: { view: WorkspaceView; investigationId: string | null }): string;
