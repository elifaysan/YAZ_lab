import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const USERNAME = __ENV.USERNAME || "admin";
const PASSWORD = __ENV.PASSWORD || "admin123";
const TARGET_VUS = Number(__ENV.TARGET_VUS || 50);
const STAGE_SECONDS = Number(__ENV.STAGE_SECONDS || 45);

export const options = {
  scenarios: {
    fixed_ramp: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "10s", target: TARGET_VUS },
        { duration: `${STAGE_SECONDS}s`, target: TARGET_VUS },
        { duration: "10s", target: 0 },
      ],
      gracefulRampDown: "5s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    checks: ["rate>0.95"],
  },
};

function loginAndGetToken() {
  const payload = JSON.stringify({ username: USERNAME, password: PASSWORD });
  const res = http.post(`${BASE_URL}/auth/login`, payload, {
    headers: { "Content-Type": "application/json" },
  });

  const ok = check(res, {
    "login status 200": (r) => r.status === 200,
    "login token exists": (r) => {
      try {
        return !!r.json("access_token");
      } catch (_) {
        return false;
      }
    },
  });
  if (!ok) return null;
  return res.json("access_token");
}

export default function () {
  const token = loginAndGetToken();
  if (!token) {
    sleep(1);
    return;
  }

  const authHeaders = {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  };

  const listRes = http.get(`${BASE_URL}/products`, authHeaders);
  check(listRes, { "products status 200": (r) => r.status === 200 });

  const createPayload = JSON.stringify({
    name: `k6-fixed-${TARGET_VUS}-${__VU}-${Date.now()}`,
    price: 10.0,
    stock: 5,
  });
  const createRes = http.post(`${BASE_URL}/products`, createPayload, authHeaders);
  check(createRes, { "create status 200": (r) => r.status === 200 });

  const reportRes = http.get(`${BASE_URL}/reports`, authHeaders);
  check(reportRes, { "reports status 200": (r) => r.status === 200 });

  sleep(1);
}
