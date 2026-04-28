// Auto-detect API base URL:
// - In Docker via nginx (port 80 or 443): use relative /api path
// - In local dev (any other port like 8000, 5500, etc.): use localhost:8000
const { hostname, port, protocol } = window.location;
const isNginx = port === "" || port === "80" || port === "443";
const API_BASE_URL = isNginx
  ? `${protocol}//${hostname}/api`
  : "http://localhost:8000";

export default API_BASE_URL;
