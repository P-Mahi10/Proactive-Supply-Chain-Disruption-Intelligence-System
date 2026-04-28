const isLocal = window.location.protocol === "file:"
  || ["localhost", "127.0.0.1"].includes(window.location.hostname);

export const API_BASE_URL  = (window.API_BASE_URL  || (isLocal ? "http://localhost:8000" : "/api")).replace(/\/$/, "");
export const NODE_BASE_URL = (window.NODE_BASE_URL || (isLocal ? "http://localhost:5000" : "/node")).replace(/\/$/, "");

export default API_BASE_URL;