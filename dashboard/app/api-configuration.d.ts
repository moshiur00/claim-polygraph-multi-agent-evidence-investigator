export const API_STORAGE_KEY: string;
export const FALLBACK_API_ADDRESS: string;

export class ApiConfigurationError extends Error {}

export function normalizeApiAddress(rawValue: string): string;
export function inferApiAddress(locationLike: Pick<Location, "protocol" | "hostname">): string;
export function loadApiConfiguration(
  storage: Pick<Storage, "getItem">,
  locationLike: Pick<Location, "protocol" | "hostname">,
): { address: string; source: "saved" | "inferred"; warning: string | null };
export function saveApiConfiguration(
  storage: Pick<Storage, "setItem">,
  rawValue: string,
): string;
export function resetApiConfiguration(
  storage: Pick<Storage, "removeItem">,
  locationLike: Pick<Location, "protocol" | "hostname">,
): string;
