const isLocal =
  window.location.protocol === "file:" ||
  ["localhost", "127.0.0.1"].includes(window.location.hostname);

const runtimeBaseUrl =
  window.API_BASE_URL || (window.__ENV__ && window.__ENV__.API_BASE_URL);
const buildTimeBaseUrl =
  typeof process !== "undefined" && process.env && process.env.API_BASE_URL
    ? process.env.API_BASE_URL
    : "";

export const API_BASE_URL = (
  runtimeBaseUrl ||
  buildTimeBaseUrl ||
  (isLocal
    ? "http://localhost:8000"
    : "https://proactive-supply-chain-disruption.onrender.com")
).replace(/\/$/, "");

export default API_BASE_URL;
