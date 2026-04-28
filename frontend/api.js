const API_BASE_URL =
  window.API_BASE_URL ||
  (import.meta && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  "http://localhost:8000";

export default API_BASE_URL;
