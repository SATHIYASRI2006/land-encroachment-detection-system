import axios from "axios";

export const BASE_URL =
  process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:5000";

export const SOCKET_URL =
  process.env.REACT_APP_SOCKET_URL || BASE_URL;

let authToken = "";

export function setAuthToken(token) {
  authToken = token || "";
}

const client = axios.create({
  baseURL: BASE_URL,
});

client.interceptors.request.use((config) => {
  const nextConfig = { ...config };
  nextConfig.headers = { ...(config.headers || {}) };
  if (authToken) {
    nextConfig.headers.Authorization = `Bearer ${authToken}`;
  }
  return nextConfig;
});

export const loginUser = async (payload) => {
  const res = await client.post("/api/v1/login", payload);
  return res.data;
};

export const registerUser = async (payload) => {
  const res = await client.post("/api/v1/register", payload);
  return res.data;
};

export const getPlots = async () => {
  const res = await client.get("/api/v1/plots");
  return res.data;
};

export const analyzePlot = async (plotId) => {
  const res = await client.get(`/api/v1/analyze/${plotId}`);
  return res.data;
};

export const getAlerts = async () => {
  const res = await client.get("/api/v1/alerts");
  return res.data;
};

export const getRealtimeStatus = async () => {
  const res = await client.get("/api/v1/realtime/status");
  return res.data;
};

export const getClaims = async () => {
  const res = await client.get("/api/v1/claims");
  return res.data;
};

export const getRegistrationSamples = async () => {
  const res = await client.get("/api/v1/verify-registration/sample-requests");
  return res.data;
};

export const getRegistrationRecords = async () => {
  const res = await client.get("/api/v1/verify-registration/records");
  return res.data;
};

export const verifyRegistration = async (payload) => {
  const res = await client.post("/api/v1/verify-registration", payload);
  return res.data;
};

export const createClaim = async (payload) => {
  const res = await client.post("/api/v1/claims", payload);
  return res.data;
};

export const updateClaim = async (claimId, payload) => {
  const res = await client.patch(`/api/v1/claims/${claimId}`, payload);
  return res.data;
};

export const generatePlotReport = async (plotId) => {
  const res = await client.get(`/api/v1/report/${plotId}`);
  return res.data;
};

export const getReportDownloadUrl = (downloadUrl) => {
  if (!downloadUrl) {
    return "";
  }
  return downloadUrl.startsWith("http") ? downloadUrl : `${BASE_URL}${downloadUrl}`;
};

export const getImageUrl = (filename) => {
  return `${BASE_URL}/static/data/${filename}`;
};

export const uploadPlotBundle = async (payload) => {
  const formData = new FormData();

  Object.entries(payload.fields).forEach(([key, value]) => {
    formData.append(key, value ?? "");
  });

  Object.entries(payload.images).forEach(([year, file]) => {
    if (file) {
      formData.append(`image_${year}`, file);
    }
  });

  const res = await client.post("/api/v1/admin/upload-plot", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return res.data;
};
