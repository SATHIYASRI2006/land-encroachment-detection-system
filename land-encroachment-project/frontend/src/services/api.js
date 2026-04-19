import axios from "axios";

export const BASE_URL =
  process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:5000";

export const SOCKET_URL =
  process.env.REACT_APP_SOCKET_URL || BASE_URL;

let authToken = "";
let authFailureHandler = null;

function getStoredAuthToken() {
  if (typeof window === "undefined") {
    return "";
  }

  try {
    const rawSession = window.localStorage.getItem("lem-session");
    if (!rawSession) {
      return "";
    }

    const parsedSession = JSON.parse(rawSession);
    return parsedSession?.token || "";
  } catch (error) {
    console.error("Failed to restore auth token from storage", error);
    return "";
  }
}

export function setAuthToken(token) {
  authToken = token || "";
}

export function setAuthFailureHandler(handler) {
  authFailureHandler = typeof handler === "function" ? handler : null;
}

const client = axios.create({
  baseURL: BASE_URL,
});

client.interceptors.request.use((config) => {
  const nextConfig = { ...config };
  nextConfig.headers = { ...(config.headers || {}) };
  const activeToken = authToken || getStoredAuthToken();
  if (activeToken) {
    nextConfig.headers.Authorization = `Bearer ${activeToken}`;
  }
  return nextConfig;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const message = error?.response?.data?.error?.message || "";
    if (status === 401) {
      authToken = "";
      if (typeof window !== "undefined") {
        window.localStorage.removeItem("lem-session");
      }
      if (authFailureHandler) {
        authFailureHandler(message || "Your session expired. Please sign in again.");
      }
    }
    return Promise.reject(error);
  }
);

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

export const getOfficialParcelBySurvey = async (surveyNumber) => {
  const res = await client.get(`/api/v1/official-parcels/${encodeURIComponent(surveyNumber)}`);
  return res.data;
};

export const extractRegistrationFromDeed = async (file) => {
  const formData = new FormData();
  formData.append("uploaded_sale_deed", file);
  const res = await client.post("/api/v1/verify-registration/extract", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return res.data;
};

export const verifyRegistration = async (payload) => {
  const hasFile = Boolean(payload?.uploaded_sale_deed);
  let requestBody = payload;
  let config = undefined;

  if (hasFile) {
    const formData = new FormData();
    Object.entries(payload).forEach(([key, value]) => {
      if (key === "uploaded_sale_deed") {
        if (value) {
          formData.append(key, value);
        }
        return;
      }
      if (key === "boundary_coordinates") {
        formData.append(key, JSON.stringify(value || []));
        return;
      }
      formData.append(key, value ?? "");
    });
    requestBody = formData;
    config = {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    };
  }

  const res = await client.post("/api/v1/verify-registration", requestBody, config);
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
