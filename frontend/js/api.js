// Se a página foi aberta em localhost:8000, usa caminho relativo.
// Se foi aberta por outra porta (ex.: Live Server 5500), aponta para o backend.

// Aberto pelo próprio backend (qualquer porta: 8000, 8001...): usa caminho relativo.
// Aberto por outro servidor de páginas (ex.: Live Server do VS Code na 5500) ou direto do arquivo: aponta para o backend.
const API_BASE = location.protocol.startsWith("http") && !["5500", "5501"].includes(location.port)
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

// Função central para falar com a API (todas as telas usam ela).
async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;

  let res;
  try {
    res = await fetch(API_BASE + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    // fetch só falha assim quando o servidor está desligado ou a rede caiu
    const err = new Error("Não consegui falar com o servidor. Confira se o backend está rodando e tente de novo.");
    err.code = "NETWORK_ERROR";
    err.status = 0;
    throw err;
  }

  if (res.status === 401 && !path.startsWith("/auth/login")) {
    logout();
    return;
  }

  let data = null;
  if (res.status !== 204) {
    try { data = await res.json(); } catch { data = null; }   // resposta que não é JSON (ex.: página de erro)
  }
  if (!res.ok) {
    const fallback =
      res.status >= 500 ? "O servidor teve um problema. Tente de novo; se repetir, veja o arquivo backend/data/rafalink.log."
      : res.status === 403 ? "Você não tem permissão para esta ação."
      : res.status === 404 ? "Não encontrado."
      : "Erro inesperado";
    const err = new Error(data?.message || fallback);
    err.code = data?.code;
    err.status = res.status;
    throw err;
  }
  return data;
}