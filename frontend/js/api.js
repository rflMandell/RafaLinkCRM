// Se a página foi aberta em localhost:8000, usa caminho relativo.
// Se foi aberta por outra porta (ex.: Live Server 5500), aponta para o backend.
const API_BASE = location.origin.startsWith("http://localhost:8000") ||
                 location.origin.startsWith("http://127.0.0.1:8000")
  ? "/api/v1"
  : "http://localhost:8000/api/v1";

const TOKEN_KEY = "rafalink_token";
const USER_KEY = "rafalink_user";

function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function getUser() {
  try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
}

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  location.href = "login.html";
}

// Protege páginas internas: chame no topo de cada página que exige login.
function requireAuth() {
  if (!getToken()) location.href = "login.html";
}

// Função central para falar com a API (todas as próximas etapas usam ela).
async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;

  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && !path.startsWith("/auth/login")) {
    logout();
    return;
  }

  const data = res.status === 204 ? null : await res.json();
  if (!res.ok) {
    const err = new Error(data?.message || "Erro inesperado");
    err.code = data?.code;
    err.status = res.status;
    throw err;
  }
  return data;
}