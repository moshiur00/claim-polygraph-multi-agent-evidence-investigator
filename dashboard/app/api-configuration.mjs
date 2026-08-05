export const API_STORAGE_KEY = "claim-polygraph-api";
export const FALLBACK_API_ADDRESS = "http://127.0.0.1:8000";

export class ApiConfigurationError extends Error {
  constructor(message) {
    super(message);
    this.name = "ApiConfigurationError";
  }
}

const repairUnbracketedIpv6WithPort = (value) => {
  const match = value.match(/^(https?):\/\/(.+):(\d+)$/i);
  if (!match || !match[2].includes(":") || match[2].startsWith("[")) return value;
  return `${match[1]}://[${match[2]}]:${match[3]}`;
};

export function normalizeApiAddress(rawValue) {
  const raw = rawValue.trim();
  if (!raw) throw new ApiConfigurationError("Enter an API address.");
  if (!/^https?:\/\//i.test(raw)) {
    throw new ApiConfigurationError("The API address must start with http:// or https://.");
  }

  let parsed;
  try {
    parsed = new URL(repairUnbracketedIpv6WithPort(raw));
  } catch {
    throw new ApiConfigurationError(
      "Enter a valid API URL. IPv6 addresses must include a port or use brackets.",
    );
  }
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new ApiConfigurationError("Only HTTP and HTTPS API addresses are supported.");
  }
  if (parsed.username || parsed.password) {
    throw new ApiConfigurationError("Credentials must not be stored in the API address.");
  }
  if (parsed.search || parsed.hash) {
    throw new ApiConfigurationError("The API address cannot contain a query or fragment.");
  }
  if (parsed.pathname !== "/") {
    throw new ApiConfigurationError("Use the API origin only, without a path.");
  }
  return `${parsed.protocol}//${parsed.host}`;
}

export function inferApiAddress(locationLike) {
  const protocol = ["http:", "https:"].includes(locationLike.protocol)
    ? locationLike.protocol
    : "http:";
  const bareHostname = locationLike.hostname.replace(/^\[|\]$/g, "");
  const hostname = bareHostname.includes(":") ? `[${bareHostname}]` : bareHostname;
  if (!hostname) return FALLBACK_API_ADDRESS;
  return normalizeApiAddress(`${protocol}//${hostname}:8000`);
}

export function loadApiConfiguration(storage, locationLike) {
  const inferredAddress = inferApiAddress(locationLike);
  const saved = storage.getItem(API_STORAGE_KEY)?.trim();
  if (!saved) return { address: inferredAddress, source: "inferred", warning: null };
  try {
    return { address: normalizeApiAddress(saved), source: "saved", warning: null };
  } catch (error) {
    return {
      address: inferredAddress,
      source: "inferred",
      warning: `The saved API address was invalid and was not used. ${error.message}`,
    };
  }
}

export function saveApiConfiguration(storage, rawValue) {
  const normalized = normalizeApiAddress(rawValue);
  storage.setItem(API_STORAGE_KEY, normalized);
  return normalized;
}

export function resetApiConfiguration(storage, locationLike) {
  storage.removeItem(API_STORAGE_KEY);
  return inferApiAddress(locationLike);
}
