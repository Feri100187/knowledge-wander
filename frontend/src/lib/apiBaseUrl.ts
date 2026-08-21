const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL
  ?.trim()
  .replace(/\/+$/, "");

const developmentApiBaseUrl =
  process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : "";

const apiBaseUrl = configuredApiBaseUrl || developmentApiBaseUrl;

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${apiBaseUrl}${normalizedPath}`;
}
