/* ═══════════════════════════════════════════════════════════
   RAFALINK — APP.JS
   ═══════════════════════════════════════════════════════════ */

/* ──────────────────────────────
   ICON HELPERS (Lucide inline SVG)
   All icons: stroke="currentColor", 24×24
────────────────────────────── */
const ICONS = {
  dashboard:     `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>`,
  clients:       `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  documents:     `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
  appointments:  `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
  notifications: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`,
  leads:         `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
  reports:       `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6"  y1="20" x2="6"  y2="14"/></svg>`,
  settings:      `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
  logout:        `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>`,
  search:        `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`,
  bell:          `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`,
  user:          `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
  eye:           `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
  eyeOff:        `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`,
  lock:          `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`,
  at:            `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-3.92 7.94"/></svg>`,
  fileText:      `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
  image:         `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`,
  fileSpreadsheet:`<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/><line x1="8" y1="9"  x2="10" y2="9"/></svg>`,
  upload:        `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></svg>`,
  clock:         `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  alertTriangle: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
  alertCircle:   `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
  check:         `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
  info:          `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
  plus:          `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
  arrowRight:    `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>`,
  calendarPlus:  `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8"  y1="2" x2="8"  y2="6"/><line x1="3"  y1="10" x2="21" y2="10"/><line x1="12" y1="15" x2="12" y2="19"/><line x1="10" y1="17" x2="14" y2="17"/></svg>`,
  google:        `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.3 12.2c0-.6-.1-1.2-.2-1.8H12v3.4h4.7c-.2 1.1-.9 2-1.9 2.6v2.2h3c1.8-1.7 2.8-4.1 2.8-6.4z"/><path d="M12 21c2.4 0 4.4-.8 5.9-2.1l-3-2.2c-.8.5-1.8.9-2.9.9-2.2 0-4.1-1.5-4.8-3.5H4v2.3C5.5 19.4 8.6 21 12 21z"/><path d="M7.2 14.1c-.2-.5-.3-1-.3-1.6s.1-1.1.3-1.6V8.6H4c-.7 1.3-1 2.8-1 4.4s.4 3 1 4.4l3.2-2.3z"/><path d="M12 6.8c1.2 0 2.3.4 3.2 1.2l2.4-2.4C16.4 4.2 14.4 3.4 12 3.4 8.6 3.4 5.5 5 4 7.6l3.2 2.4c.7-2 2.6-3.2 4.8-3.2z"/></svg>`,
};

/* colour helpers for icon containers */
function iconColor(key, size = 18) {
  const svg = ICONS[key];
  if (!svg) return '';
  return svg.replace(/width="\d+"/, `width="${size}"`).replace(/height="\d+"/, `height="${size}"`);
}

/* ──────────────────────────────
   DATA STORE
────────────────────────────── */
const DB = {
  get(k)  { try { return JSON.parse(localStorage.getItem('rl_' + k)) || null; } catch(e) { return null; } },
  set(k,v){ localStorage.setItem('rl_' + k, JSON.stringify(v)); },
  del(k)  { localStorage.removeItem('rl_' + k); }
};

function initDB() {
  if (!DB.get('users')) {
    DB.set('users', [
      { id:'u1', username:'alex.rafa',   password:'admin123',   name:'Alex Rafa',   role:'admin',  email:'alex.rafa@rafalink.com',  company:'RafaLink Corp', avatar:'AR' },
      { id:'u2', username:'joao.silva',  password:'cliente123', name:'João Silva',  role:'client', email:'joao.silva@maritex.com',  company:'Maritex SA',    avatar:'JS' }
    ]);
  }
  if (!DB.get('clients')) {
    DB.set('clients', [
      { id:'c1', name:'João Silva',    company:'Maritex SA',    email:'joao.silva@maritex.com', phone:'(11) 98765-4321', status:'Ativo',    notes:'Cliente desde 2022. Módulo Enterprise.', linkedUserId:'u2' },
      { id:'c2', name:'Sofia Lima',    company:'iDesign pt',    email:'sofia@idesign.pt',        phone:'(11) 91234-5678', status:'Ativo',    notes:'Cliente VIP — Agência parceira.',         linkedUserId:null },
      { id:'c3', name:'Rodrigo Terra', company:'Eng BR',        email:'rterra@eng.br',           phone:'(21) 99876-5432', status:'Prospect', notes:'Demonstrou interesse no módulo básico.',  linkedUserId:null },
      { id:'c4', name:'Marcos Barbosa',company:'Licor Audit',   email:'marcos@licoraudit.com',   phone:'(31) 98888-7777', status:'Ativo',    notes:'',                                        linkedUserId:null }
    ]);
  }
  if (!DB.get('documents')) {
    DB.set('documents', [
      { id:'d1', name:'Contrato_2024.pdf',        type:'Contrato',  status:'Assinado',   clientId:'c1', date:'2024-10-15', size:'2.4 MB', ext:'pdf' },
      { id:'d2', name:'Identidade_Frente.jpg',    type:'Dossiê',    status:'Arquivado',  clientId:'c1', date:'2024-10-10', size:'1.7 MB', ext:'img' },
      { id:'d3', name:'Termo_Aditivo_Q4.pdf',     type:'Contrato',  status:'Assinado',   clientId:'c2', date:'2024-11-01', size:'1.1 MB', ext:'pdf' },
      { id:'d4', name:'Dossiê_Fiscal_2024.xlsx',  type:'Dossiê',    status:'Arquivado',  clientId:'c3', date:'2024-09-20', size:'800 KB', ext:'doc' },
      { id:'d5', name:'Relatório_Anual.pdf',      type:'Relatório', status:'Aguardando', clientId:'c4', date:'2024-11-05', size:'3.2 MB', ext:'pdf' }
    ]);
  }
  if (!DB.get('appointments')) {
    DB.set('appointments', [
      { id:'a1', title:'Consultoria Estratégica',   date:'2026-10-24', time:'14:30', type:'Consultoria',   clientId:'c1', notes:'Revisar métricas do Q3.',                          status:'Confirmado' },
      { id:'a2', title:'Revisão de Documentação',   date:'2026-11-02', time:'10:00', type:'Revisão',       clientId:'c1', notes:'',                                                  status:'Pendente'   },
      { id:'a3', title:'Apresentação Enterprise',   date:'2026-05-15', time:'09:00', type:'Apresentação',  clientId:'c2', notes:'Primeiro contato.',                                 status:'Confirmado' },
      { id:'a4', title:'Reunião de Kick-off',       date:'2026-05-20', time:'14:00', type:'Reunião',       clientId:'c3', notes:'',                                                  status:'Pendente'   }
    ]);
  }
  if (!DB.get('leads')) {
    DB.set('leads', [
      { id:'l1', name:'Gomes & Filhos Ltda', company:'Gomes & Filhos', email:'gomes@gfltda.com',     value:45000,  stage:'Qualificação', priority:'Alta',    createdAt:'2024-11-01' },
      { id:'l2', name:'TechNova Inc',        company:'TechNova',       email:'contact@technova.io',  value:120000, stage:'Proposta',     priority:'Normal',  createdAt:'2024-10-28' },
      { id:'l3', name:'Construtora Vega',    company:'Vega Const.',    email:'adm@vega.com',         value:85000,  stage:'Prospecção',   priority:'Normal',  createdAt:'2024-11-02' },
      { id:'l4', name:'HealthCorp Brasil',   company:'HealthCorp',     email:'ti@healthcorp.com',    value:200000, stage:'Fechamento',   priority:'Urgente', createdAt:'2024-10-25' }
    ]);
  }
  if (!DB.get('notifications')) {
    DB.set('notifications', [
      { id:'n1', title:'Novo documento disponível',                body:'Seu contrato foi assinado e está no Vault.',                              time:'2 horas',  read:false, userId:'u2' },
      { id:'n2', title:'Alteração de horário',                     body:'A reunião de amanhã foi movida para as 15h.',                             time:'Ontem',    read:false, userId:'u2' },
      { id:'n3', title:'Vencimento de Documentação — Maritex SA',  body:'O alvará de funcionamento expira em 48 horas. Ação imediata requerida.', time:'1 hora',   read:false, userId:'u1' },
      { id:'n4', title:'Novo Lead de Alta Prioridade',             body:'Gomes & Filhos Ltda demonstrou interesse no módulo Enterprise.',         time:'3 horas',  read:false, userId:'u1' },
      { id:'n5', title:'Documento assinado',                       body:'Contrato 2024 foi assinado pelo cliente João Silva.',                    time:'1 dia',    read:true,  userId:'u1' }
    ]);
  }
}

/* ──────────────────────────────
   STATE
────────────────────────────── */
let currentUser    = null;
let currentSection = '';
let passVisible    = false;

/* ──────────────────────────────
   AUTH
────────────────────────────── */
function doLogin() {
  const username = document.getElementById('login-user').value.trim();
  const password = document.getElementById('login-pass').value;
  let valid = true;

  hideErr('login-user-err');
  hideErr('login-pass-err');
  document.getElementById('login-err-general').style.display = 'none';
  document.getElementById('login-user').classList.remove('error');
  document.getElementById('login-pass').classList.remove('error');

  if (!username) { showErr('login-user-err'); document.getElementById('login-user').classList.add('error'); valid = false; }
  if (!password) { showErr('login-pass-err'); document.getElementById('login-pass').classList.add('error'); valid = false; }
  if (!valid) return;

  const user = (DB.get('users') || []).find(u => u.username === username && u.password === password);
  if (!user) {
    const el = document.getElementById('login-err-general');
    el.textContent = 'Usuário ou senha incorretos. Tente: alex.rafa / admin123  ou  joao.silva / cliente123';
    el.style.display = 'block';
    return;
  }
  currentUser = user;
  DB.set('session', user.id);
  enterApp();
}

function doLogout() {
  currentUser = null;
  DB.del('session');
  document.getElementById('page-app').classList.remove('active');
  document.getElementById('page-login').classList.add('active');
  document.getElementById('login-user').value = '';
  document.getElementById('login-pass').value = '';
}

function togglePass() {
  passVisible = !passVisible;
  const inp = document.getElementById('login-pass');
  const btn = document.getElementById('eye-toggle');
  inp.type = passVisible ? 'text' : 'password';
  btn.innerHTML = passVisible ? ICONS.eyeOff : ICONS.eye;
}

/* ──────────────────────────────
   APP ENTRY
────────────────────────────── */
function enterApp() {
  document.getElementById('page-login').classList.remove('active');
  document.getElementById('page-app').classList.add('active');
  renderSidebar();
  navigate(currentUser.role === 'admin' ? 'dashboard' : 'dashboard-client');
  updateNotifDot();
}

function renderSidebar() {
  document.getElementById('sb-avatar').textContent = currentUser.avatar || currentUser.name[0];
  document.getElementById('sb-name').textContent   = currentUser.name;
  document.getElementById('sb-role').textContent   = currentUser.role === 'admin' ? 'Lead Administrator' : 'Cliente';

  const adminItems = [
    { id:'dashboard',     icon:'dashboard',     label:'Dashboard'     },
    { id:'clients',       icon:'clients',       label:'Clientes'      },
    { id:'documents',     icon:'documents',     label:'Documentos'    },
    { id:'appointments',  icon:'appointments',  label:'Agendamentos'  },
    { id:'notifications', icon:'notifications', label:'Notificações', badge:true },
    { id:'leads',         icon:'leads',         label:'Leads'         },
    { id:'reports',       icon:'reports',       label:'Relatórios'    },
    { id:'settings',      icon:'settings',      label:'Configurações' }
  ];
  const clientItems = [
    { id:'dashboard-client', icon:'dashboard',     label:'Dashboard'     },
    { id:'documents',        icon:'documents',     label:'Documentos'    },
    { id:'appointments',     icon:'appointments',  label:'Agendamentos'  },
    { id:'notifications',    icon:'notifications', label:'Notificações', badge:true },
    { id:'settings',         icon:'settings',      label:'Configurações' }
  ];

  const items = currentUser.role === 'admin' ? adminItems : clientItems;
  const unread = (DB.get('notifications') || []).filter(n => n.userId === currentUser.id && !n.read).length;

  document.getElementById('sidebar-nav').innerHTML = items.map(it => {
    const badge = it.badge && unread ? `<span class="nav-badge">${unread}</span>` : '';
    return `<div class="nav-item" id="nav-${it.id}" onclick="navigate('${it.id}')">
      <span class="nav-icon">${ICONS[it.icon] || ''}</span>${it.label}${badge}
    </div>`;
  }).join('');
}

function navigate(section) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const sec = document.getElementById('sec-' + section);
  if (sec) sec.classList.add('active');
  const nav = document.getElementById('nav-' + section);
  if (nav) nav.classList.add('active');
  currentSection = section;
  renderSection(section);
}

function renderSection(s) {
  if      (s === 'dashboard')        renderAdminDash();
  else if (s === 'dashboard-client') renderClientDash();
  else if (s === 'clients')          renderClientsTable();
  else if (s === 'documents')        renderDocsTable();
  else if (s === 'appointments')     renderAppointments();
  else if (s === 'notifications')    renderNotifications();
  else if (s === 'leads')            renderLeads();
  else if (s === 'reports')          renderReports();
  else if (s === 'settings')         renderSettingsForm();
}

/* ──────────────────────────────
   HELPERS
────────────────────────────── */
function statusTag(s) {
  if (s === 'Assinado')   return 'tag-green';
  if (s === 'Em Revisão') return 'tag-orange';
  if (s === 'Aguardando') return 'tag-red';
  if (s === 'Arquivado')  return 'tag-gray';
  return 'tag-gold';
}
function docIcon(ext) {
  if (ext === 'pdf') return `<div class="doc-icon doc-icon-pdf" style="color:var(--red)">${ICONS.fileText}</div>`;
  if (ext === 'img') return `<div class="doc-icon doc-icon-img" style="color:var(--orange)">${ICONS.image}</div>`;
  return `<div class="doc-icon doc-icon-doc" style="color:#4a6cf7">${ICONS.fileSpreadsheet}</div>`;
}
const MONTHS = ['JAN','FEV','MAR','ABR','MAI','JUN','JUL','AGO','SET','OUT','NOV','DEZ'];
const STAGES = ['Prospecção','Qualificação','Proposta','Fechamento'];
const STAGE_COLORS = { 'Prospecção':'tag-gray','Qualificação':'tag-gold','Proposta':'tag-orange','Fechamento':'tag-green' };
const PRIORITY_CLASS = { 'Urgente':'tag-red','Alta':'tag-orange','Normal':'tag-gray' };

function showErr(id) { const el = document.getElementById(id); if (el) el.style.display = 'block'; }
function hideErr(id) { const el = document.getElementById(id); if (el) el.style.display = 'none'; }

function openModal(id) {
  if (id === 'modal-add-doc' || id === 'modal-add-appt') populateClientSelects();
  document.getElementById(id).classList.add('open');
}
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

function toast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  const icon = type === 'success' ? ICONS.check : type === 'error' ? ICONS.alertCircle : ICONS.info;
  t.innerHTML = `<span style="flex-shrink:0">${icon}</span> ${msg}`;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

function addNotif(userId, title, body) {
  const notifs = DB.get('notifications') || [];
  notifs.unshift({ id: 'n' + Date.now(), title, body, time: 'agora', read: false, userId });
  DB.set('notifications', notifs);
  if (currentUser && currentUser.id === userId) { updateNotifDot(); renderSidebar(); }
}

function updateNotifDot() {
  const count = (DB.get('notifications') || []).filter(n => n.userId === currentUser.id && !n.read).length;
  const dot = document.getElementById('notif-dot');
  if (dot) dot.style.display = count > 0 ? '' : 'none';
}

function populateClientSelects() {
  const clients = DB.get('clients') || [];
  const opts = '<option value="">— Nenhum —</option>' + clients.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  ['doc-client','appt-client'].forEach(id => { const el = document.getElementById(id); if (el) el.innerHTML = opts; });
}

/* ──────────────────────────────
   ADMIN DASHBOARD
────────────────────────────── */
function renderAdminDash() {
  const clients = DB.get('clients') || [];
  const docs    = DB.get('documents') || [];
  const leads   = DB.get('leads') || [];
  const appts   = DB.get('appointments') || [];
  const notifs  = (DB.get('notifications') || []).filter(n => n.userId === 'u1' && !n.read);

  document.getElementById('sec-dashboard').innerHTML = `
    <div class="page-title">Bem-vindo, ${currentUser.name.split(' ')[0]} — Lead Administrator</div>
    <div class="page-sub" style="margin-bottom:24px">Aqui está o resumo operacional para hoje.</div>

    <div class="grid-4" style="margin-bottom:20px">
      <div class="stat-card"><div class="stat-value">${clients.length}</div><div class="stat-label">Total Clientes</div></div>
      <div class="stat-card"><div class="stat-value">${docs.length}</div><div class="stat-label">Doc. Ativos</div></div>
      <div class="stat-card accent"><div class="stat-value">${leads.length}</div><div class="stat-label">Leads</div></div>
      <div class="stat-card"><div class="stat-value">${appts.filter(a => a.status === 'Confirmado').length}</div><div class="stat-label">Agend. Confirmados</div></div>
    </div>

    <div class="grid-2">
      <div>
        <div class="card">
          <div class="card-title">Alertas Críticos ${notifs.length ? `<span class="tag tag-red">${notifs.length} PENDENTES</span>` : ''}</div>
          ${notifs.slice(0,3).map(n => `
            <div class="alert ${n.title.includes('Vencimento') ? 'alert-red' : 'alert-orange'}">
              <span class="alert-icon" style="color:${n.title.includes('Vencimento') ? 'var(--red)' : 'var(--orange)'}">
                ${n.title.includes('Vencimento') ? ICONS.alertTriangle : ICONS.alertCircle}
              </span>
              <div>
                <div class="alert-title">${n.title}</div>
                <div class="alert-sub">${n.body}</div>
                <a class="alert-action" onclick="navigate('notifications')">Resolver Agora ${ICONS.arrowRight}</a>
              </div>
            </div>
          `).join('') || '<div style="color:var(--text-light);font-size:14px;padding:8px">Nenhum alerta crítico.</div>'}
        </div>

        <div class="card">
          <div class="card-title">Documentos Responsáveis <a href="#" style="font-size:12px;color:var(--gold);font-weight:500;display:flex;align-items:center;gap:4px" onclick="navigate('documents')">Ver todos ${ICONS.arrowRight}</a></div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            ${docs.slice(0,4).map(d => `
              <div class="doc-item" onclick='openDocModal(${JSON.stringify(d)})'>
                ${docIcon(d.ext)}
                <div>
                  <div class="doc-name" style="font-size:12px">${d.name}</div>
                  <div class="doc-meta">${d.date}</div>
                  <span class="tag ${statusTag(d.status)}" style="margin-top:4px;display:inline-block">${d.status}</span>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>

      <div>
        <div class="card">
          <div class="card-title">Ações Rápidas</div>
          <div style="display:flex;flex-direction:column;gap:10px">
            <button class="btn btn-gold" style="justify-content:center" onclick="openModal('modal-add-doc')">${ICONS.fileText} Novo Documento</button>
            <button class="btn btn-outline" style="justify-content:center" onclick="openModal('modal-add-client')">${ICONS.user} Adicionar Cliente</button>
            <button class="btn btn-outline" style="justify-content:center" onclick="openModal('modal-add-lead')">${ICONS.leads} Novo Lead</button>
            <button class="btn btn-outline" style="justify-content:center" onclick="openModal('modal-add-appt')">${ICONS.calendarPlus} Agendar Reunião</button>
          </div>
          <div style="margin-top:20px;border-top:1px solid var(--cream-dark);padding-top:16px;display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div><div style="font-size:11px;color:var(--text-light);text-transform:uppercase;letter-spacing:.6px">Clientes</div>
              <div style="font-family:'Playfair Display',serif;font-size:26px;font-weight:700;color:var(--gold)">${clients.length}</div></div>
            <div><div style="font-size:11px;color:var(--text-light);text-transform:uppercase;letter-spacing:.6px">Documentos</div>
              <div style="font-family:'Playfair Display',serif;font-size:26px;font-weight:700;color:var(--gold)">${docs.length}</div></div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Agendamentos Recentes</div>
          ${appts.slice(0,2).map(a => schedCard(a)).join('') || emptyState('appointments','Nenhum agendamento ativo')}
        </div>

        <div class="card">
          <div class="card-title">Leads Recentes</div>
          ${(DB.get('leads') || []).slice(0,3).map(l => `
            <div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--cream-dark)">
              <div class="client-row-avatar">${l.name[0]}</div>
              <div style="flex:1"><div style="font-size:13px;font-weight:600">${l.name}</div><div style="font-size:11px;color:var(--text-light)">${l.email}</div></div>
              <span class="tag tag-gold">${l.stage}</span>
            </div>
          `).join('')}
          <div style="margin-top:12px">
            <button class="btn btn-outline" style="width:100%;justify-content:center" onclick="navigate('leads')">Explorar Leads</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

/* ──────────────────────────────
   CLIENT DASHBOARD
────────────────────────────── */
function renderClientDash() {
  const clients  = DB.get('clients') || [];
  const myClient = clients.find(c => c.linkedUserId === currentUser.id);
  const docs     = (DB.get('documents') || []).filter(d => myClient && d.clientId === myClient.id);
  const appts    = (DB.get('appointments') || []).filter(a => myClient && a.clientId === myClient.id);
  const myNotifs = (DB.get('notifications') || []).filter(n => n.userId === currentUser.id && !n.read);

  document.getElementById('sec-dashboard-client').innerHTML = `
    <div class="page-title">Olá, ${currentUser.name.split(' ')[0]}!</div>
    <div class="page-sub" style="margin-bottom:24px">Bem-vindo ao seu portal. Aqui está o que precisa de sua atenção hoje.</div>

    <div class="grid-2">
      <div>
        <div class="card">
          <div class="card-title">Meus Agendamentos
            <button class="btn btn-gold btn-sm" onclick="openModal('modal-add-appt')">${ICONS.calendarPlus} Agendar</button>
          </div>
          ${appts.length ? appts.slice(0,3).map(a => schedCard(a)).join('') : `
            <div class="empty">
              <div class="empty-icon">${ICONS.appointments.replace('18','48')}</div>
              <div class="empty-text">Nenhum agendamento ativo</div>
              <div style="margin-top:12px">
                <a href="#" style="color:var(--gold);font-size:13px;font-weight:600;display:inline-flex;align-items:center;gap:6px" onclick="openModal('modal-add-appt')">
                  ${ICONS.calendarPlus} Agendar nova reunião
                </a>
              </div>
            </div>`}
        </div>
        <div class="grid-2">
          <div class="stat-card"><div class="stat-value">${appts.filter(a => a.status === 'Confirmado').length}</div><div class="stat-label">Projetos Ativos</div></div>
          <div class="stat-card accent"><div class="stat-value">4.9</div><div class="stat-label">Satisfação</div></div>
        </div>
      </div>

      <div>
        <div class="card">
          <div class="card-title">Alertas Recentes</div>
          ${myNotifs.slice(0,3).map(n => `
            <div class="notif-item" onclick="markRead('${n.id}')">
              <div class="notif-dot2"></div>
              <div>
                <div class="notif-title">${n.title}</div>
                <div class="notif-sub">${n.body}</div>
                <div class="notif-time">Há ${n.time}</div>
              </div>
            </div>
          `).join('') || '<div style="color:var(--text-light);font-size:13px;padding:8px">Sem alertas novos.</div>'}
        </div>

        <div class="card">
          <div class="card-title">Seus Documentos</div>
          ${docs.slice(0,2).map(d => `
            <div class="doc-item" onclick='openDocModal(${JSON.stringify(d)})'>
              ${docIcon(d.ext)}
              <div>
                <div class="doc-name">${d.name}</div>
                <div class="doc-meta">${d.ext.toUpperCase()} · ${d.size}</div>
              </div>
            </div>
          `).join('')}
          <div class="upload-btn" onclick="openModal('modal-add-doc')" style="margin-top:8px">
            ${ICONS.upload}
            <span>Upload Documento</span>
          </div>
        </div>
      </div>
    </div>
  `;
}

/* ──────────────────────────────
   SCHEDULE CARD (shared helper)
────────────────────────────── */
function schedCard(a, clickable = false) {
  const d = new Date(a.date + 'T00:00');
  return `<div class="sched-card" ${clickable ? `style="cursor:pointer" onclick="viewAppt('${a.id}')"` : ''}>
    <div class="sched-date"><div class="sched-month">${MONTHS[d.getMonth()]}</div><div class="sched-day">${String(d.getDate()).padStart(2,'0')}</div></div>
    <div class="sched-info">
      <div class="sched-title">${a.title}</div>
      <div class="sched-time">${ICONS.clock} ${a.time} — ${a.type}</div>
    </div>
    <span class="tag ${a.status === 'Confirmado' ? 'tag-green' : 'tag-orange'}">${a.status}</span>
  </div>`;
}

function emptyState(iconKey, text) {
  return `<div class="empty"><div class="empty-icon">${(ICONS[iconKey] || ICONS.info).replace(/width="\d+"/, 'width="48"').replace(/height="\d+"/, 'height="48"')}</div><div class="empty-text">${text}</div></div>`;
}

/* ──────────────────────────────
   CLIENTS
────────────────────────────── */
function renderClientsTable() {
  const q = (document.getElementById('client-search')?.value || '').toLowerCase();
  const clients = (DB.get('clients') || []).filter(c =>
    c.name.toLowerCase().includes(q) || c.email.toLowerCase().includes(q) || (c.company||'').toLowerCase().includes(q)
  );
  const appts = DB.get('appointments') || [];
  const tbody = document.getElementById('clients-tbody');
  if (!tbody) return;
  tbody.innerHTML = clients.map(c => `
    <tr>
      <td><div style="display:flex;align-items:center;gap:10px">
        <div class="client-row-avatar">${c.name[0]}</div>
        <div><div style="font-weight:600">${c.name}</div><div style="font-size:12px;color:var(--text-light)">${c.phone||'—'}</div></div>
      </div></td>
      <td>${c.company||'—'}</td>
      <td>${c.email}</td>
      <td><span class="tag ${c.status==='Ativo'?'tag-green':c.status==='Inativo'?'tag-red':'tag-gold'}">${c.status}</span></td>
      <td>${appts.filter(a => a.clientId === c.id).length}</td>
      <td><button class="btn btn-outline btn-sm" onclick="openEditClient('${c.id}')">Editar</button></td>
    </tr>
  `).join('') || `<tr><td colspan="6">${emptyState('clients','Nenhum cliente encontrado.')}</td></tr>`;
}

function openEditClient(id) {
  const c = (DB.get('clients')||[]).find(x => x.id === id);
  if (!c) return;
  ['edit-cl-id','edit-cl-name','edit-cl-company','edit-cl-email','edit-cl-phone','edit-cl-notes'].forEach(fid => {
    const map = {'edit-cl-id':'id','edit-cl-name':'name','edit-cl-company':'company','edit-cl-email':'email','edit-cl-phone':'phone','edit-cl-notes':'notes'};
    document.getElementById(fid).value = c[map[fid]] || '';
  });
  document.getElementById('edit-cl-status').value = c.status;
  openModal('modal-edit-client');
}

function saveClient() {
  const name    = document.getElementById('cl-name').value.trim();
  const company = document.getElementById('cl-company').value.trim();
  const email   = document.getElementById('cl-email').value.trim();
  let valid = true;
  if (!name)             { showErr('cl-name-err');    document.getElementById('cl-name').classList.add('error');    valid = false; } else { hideErr('cl-name-err');    document.getElementById('cl-name').classList.remove('error'); }
  if (!company)          { showErr('cl-company-err'); document.getElementById('cl-company').classList.add('error'); valid = false; } else { hideErr('cl-company-err'); document.getElementById('cl-company').classList.remove('error'); }
  if (!email || !email.includes('@')) { showErr('cl-email-err'); document.getElementById('cl-email').classList.add('error'); valid = false; } else { hideErr('cl-email-err'); document.getElementById('cl-email').classList.remove('error'); }
  if (!valid) return;

  const clients = DB.get('clients') || [];
  clients.push({ id:'c'+Date.now(), name, company, email, phone:document.getElementById('cl-phone').value, status:document.getElementById('cl-status').value, notes:document.getElementById('cl-notes').value, linkedUserId:null });
  DB.set('clients', clients);
  ['cl-name','cl-company','cl-email','cl-phone','cl-notes'].forEach(id => document.getElementById(id).value = '');
  closeModal('modal-add-client');
  renderClientsTable();
  addNotif('u1', 'Novo cliente adicionado', `${name} foi cadastrado com sucesso.`);
  toast('Cliente adicionado!', 'success');
}

function updateClient() {
  const id = document.getElementById('edit-cl-id').value;
  const clients = DB.get('clients') || [];
  const idx = clients.findIndex(c => c.id === id);
  if (idx < 0) return;
  clients[idx] = { ...clients[idx], name:document.getElementById('edit-cl-name').value, company:document.getElementById('edit-cl-company').value, email:document.getElementById('edit-cl-email').value, phone:document.getElementById('edit-cl-phone').value, status:document.getElementById('edit-cl-status').value, notes:document.getElementById('edit-cl-notes').value };
  DB.set('clients', clients);
  closeModal('modal-edit-client');
  renderClientsTable();
  if (currentSection === 'dashboard') renderAdminDash();
  toast('Cliente atualizado!', 'success');
}

function deleteClient() {
  const id = document.getElementById('edit-cl-id').value;
  DB.set('clients', (DB.get('clients')||[]).filter(c => c.id !== id));
  closeModal('modal-edit-client');
  renderClientsTable();
  toast('Cliente removido.', 'info');
}

/* ──────────────────────────────
   DOCUMENTS
────────────────────────────── */
function renderDocsTable() {
  const q = (document.getElementById('doc-search')?.value || '').toLowerCase();
  let docs = DB.get('documents') || [];
  if (currentUser.role === 'client') {
    const myC = (DB.get('clients')||[]).find(c => c.linkedUserId === currentUser.id);
    docs = myC ? docs.filter(d => d.clientId === myC.id) : [];
  }
  docs = docs.filter(d => d.name.toLowerCase().includes(q) || (d.type||'').toLowerCase().includes(q));
  populateClientSelects();
  const clients = DB.get('clients') || [];
  const tbody = document.getElementById('docs-tbody');
  if (!tbody) return;
  tbody.innerHTML = docs.map(d => {
    const cl = clients.find(c => c.id === d.clientId);
    return `<tr>
      <td><div style="display:flex;align-items:center;gap:10px">
        ${docIcon(d.ext)}
        <div><div style="font-weight:600;font-size:13px">${d.name}</div><div style="font-size:11px;color:var(--text-light)">${d.size||''}</div></div>
      </div></td>
      <td><span class="tag tag-gold">${d.type}</span></td>
      <td>${cl ? cl.name : '—'}</td>
      <td><span class="tag ${statusTag(d.status)}">${d.status}</span></td>
      <td>${d.date}</td>
      <td><button class="btn btn-outline btn-sm" onclick='openDocModal(${JSON.stringify(d)})'>Visualizar</button></td>
    </tr>`;
  }).join('') || `<tr><td colspan="6">${emptyState('documents','Nenhum documento encontrado.')}</td></tr>`;
}

function simulateUpload() {
  const names = ['contrato_novo.pdf','documento_fiscal.pdf','proposta_comercial.pdf','relatorio.xlsx'];
  const hint  = document.getElementById('upload-hint');
  hint.textContent = names[Math.floor(Math.random()*names.length)] + ' — selecionado';
  hint.style.color = 'var(--green)';
}

function saveDoc() {
  const name = document.getElementById('doc-name').value.trim();
  if (!name) { showErr('doc-name-err'); document.getElementById('doc-name').classList.add('error'); return; }
  hideErr('doc-name-err'); document.getElementById('doc-name').classList.remove('error');

  const type     = document.getElementById('doc-type').value;
  const ext      = type === 'Dossiê' ? 'doc' : 'pdf';
  const clientId = document.getElementById('doc-client').value;
  const docs     = DB.get('documents') || [];
  docs.push({ id:'d'+Date.now(), name, type, status:document.getElementById('doc-status').value, clientId, date:new Date().toISOString().slice(0,10), size:'—', ext });
  DB.set('documents', docs);

  if (clientId) {
    const cl = (DB.get('clients')||[]).find(c => c.id === clientId);
    if (cl && cl.linkedUserId) addNotif(cl.linkedUserId, 'Novo documento disponível', `O documento "${name}" foi adicionado à sua conta.`);
  }
  document.getElementById('doc-name').value = '';
  closeModal('modal-add-doc');
  renderDocsTable();
  if (currentSection.startsWith('dashboard')) renderSection(currentSection);
  toast('Documento adicionado!', 'success');
}

function openDocModal(d) {
  if (typeof d === 'string') d = JSON.parse(d);
  const cl = (DB.get('clients')||[]).find(c => c.id === d.clientId);
  document.getElementById('vdoc-title').textContent = d.name;
  document.getElementById('vdoc-body').innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
      <div><div class="form-label">Tipo</div><div style="font-size:14px;font-weight:600">${d.type}</div></div>
      <div><div class="form-label">Status</div><span class="tag ${statusTag(d.status)}">${d.status}</span></div>
      <div><div class="form-label">Cliente</div><div style="font-size:14px">${cl ? cl.name : '—'}</div></div>
      <div><div class="form-label">Data</div><div style="font-size:14px">${d.date}</div></div>
      <div><div class="form-label">Tamanho</div><div style="font-size:14px">${d.size||'—'}</div></div>
    </div>
    <div style="background:var(--cream);border-radius:var(--radius-sm);padding:40px;text-align:center;color:var(--text-light)">
      <div style="display:flex;justify-content:center;margin-bottom:12px;opacity:.4">
        ${(ICONS[d.ext==='pdf'?'fileText':d.ext==='img'?'image':'fileSpreadsheet']).replace('18','48').replace('18','48')}
      </div>
      <div style="font-weight:600;font-size:14px">${d.name}</div>
      <div style="margin-top:8px;font-size:12px">Pré-visualização simulada</div>
    </div>
  `;
  const nextStatuses = { 'Aguardando':'Em Revisão','Em Revisão':'Assinado','Assinado':'Arquivado','Arquivado':'Aguardando' };
  const btn = document.getElementById('vdoc-status-btn');
  btn.textContent = '→ ' + nextStatuses[d.status];
  btn.onclick = () => {
    const docs = DB.get('documents') || [];
    const idx  = docs.findIndex(x => x.id === d.id);
    if (idx >= 0) { docs[idx].status = nextStatuses[d.status]; DB.set('documents', docs); }
    closeModal('modal-view-doc');
    renderDocsTable();
    if (currentSection.startsWith('dashboard')) renderSection(currentSection);
    toast('Status atualizado!', 'success');
  };
  const delBtn = document.getElementById('vdoc-delete-btn');
  if (currentUser.role === 'admin') {
    delBtn.style.display = '';
    delBtn.onclick = () => {
      DB.set('documents', (DB.get('documents')||[]).filter(x => x.id !== d.id));
      closeModal('modal-view-doc');
      renderDocsTable();
      toast('Documento removido.', 'info');
    };
  } else { delBtn.style.display = 'none'; }
  openModal('modal-view-doc');
}

/* ──────────────────────────────
   APPOINTMENTS
────────────────────────────── */
function renderAppointments() {
  renderMiniCal();
  renderApptList();
  populateClientSelects();
}

function renderMiniCal() {
  const cal = document.getElementById('mini-cal');
  if (!cal) return;
  const today    = new Date();
  const y = today.getFullYear(), m = today.getMonth();
  const firstDay = new Date(y,m,1).getDay();
  const daysInM  = new Date(y,m+1,0).getDate();
  let appts = DB.get('appointments') || [];
  if (currentUser.role === 'client') {
    const myC = (DB.get('clients')||[]).find(c => c.linkedUserId === currentUser.id);
    appts = myC ? appts.filter(a => a.clientId === myC.id) : [];
  }
  const eventDays = new Set(appts.filter(a => {
    const d = new Date(a.date+'T00:00');
    return d.getFullYear() === y && d.getMonth() === m;
  }).map(a => new Date(a.date+'T00:00').getDate()));

  let html = '';
  for (let i = 0; i < firstDay; i++) html += `<div class="cal-day empty"></div>`;
  for (let d = 1; d <= daysInM; d++) {
    html += `<div class="cal-day ${d === today.getDate() ? 'today' : eventDays.has(d) ? 'has-event' : ''}">${d}</div>`;
  }
  cal.innerHTML = html;
}

function renderApptList() {
  let appts = DB.get('appointments') || [];
  if (currentUser.role === 'client') {
    const myC = (DB.get('clients')||[]).find(c => c.linkedUserId === currentUser.id);
    appts = myC ? appts.filter(a => a.clientId === myC.id) : [];
  }
  appts.sort((a,b) => a.date.localeCompare(b.date));
  const list = document.getElementById('appt-list');
  if (!list) return;
  list.innerHTML = appts.map(a => schedCard(a, true)).join('') || emptyState('appointments','Nenhum agendamento ativo.');
}

function saveAppt() {
  const title = document.getElementById('appt-title').value.trim();
  const date  = document.getElementById('appt-date').value;
  if (!title) { showErr('appt-title-err'); document.getElementById('appt-title').classList.add('error'); return; }
  hideErr('appt-title-err'); document.getElementById('appt-title').classList.remove('error');

  const clientId = document.getElementById('appt-client').value;
  const appts = DB.get('appointments') || [];
  appts.push({ id:'a'+Date.now(), title, date: date || new Date().toISOString().slice(0,10), time:document.getElementById('appt-time').value, type:document.getElementById('appt-type').value, clientId, notes:document.getElementById('appt-notes').value, status:'Pendente' });
  DB.set('appointments', appts);

  if (clientId) {
    const cl = (DB.get('clients')||[]).find(c => c.id === clientId);
    if (cl && cl.linkedUserId) addNotif(cl.linkedUserId, 'Novo agendamento', `Você tem uma reunião agendada: "${title}".`);
  }
  document.getElementById('appt-title').value = '';
  document.getElementById('appt-notes').value = '';
  closeModal('modal-add-appt');
  renderAppointments();
  if (currentSection.startsWith('dashboard')) renderSection(currentSection);
  toast('Agendamento criado!', 'success');
}

function viewAppt(id) {
  const a = (DB.get('appointments')||[]).find(x => x.id === id);
  if (!a) return;
  const cl = (DB.get('clients')||[]).find(c => c.id === a.clientId);
  document.getElementById('vappt-title').textContent = a.title;
  document.getElementById('vappt-body').innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div><div class="form-label">Data</div><div style="font-size:14px;font-weight:600">${a.date}</div></div>
      <div><div class="form-label">Horário</div><div style="font-size:14px;font-weight:600">${a.time}</div></div>
      <div><div class="form-label">Tipo</div><div style="font-size:14px">${a.type}</div></div>
      <div><div class="form-label">Status</div><span class="tag ${a.status==='Confirmado'?'tag-green':'tag-orange'}">${a.status}</span></div>
      <div><div class="form-label">Cliente</div><div style="font-size:14px">${cl ? cl.name : '—'}</div></div>
    </div>
    ${a.notes ? `<div style="margin-top:16px;background:var(--cream);border-radius:var(--radius-sm);padding:14px;font-size:13px;color:var(--text-mid)">${a.notes}</div>` : ''}
  `;
  const footer = document.getElementById('vappt-footer');
  if (currentUser.role === 'admin') {
    footer.innerHTML = `
      <button class="btn btn-danger btn-sm" onclick="deleteAppt('${id}')">Excluir</button>
      <button class="btn btn-outline" onclick="closeModal('modal-view-appt')">Fechar</button>
      <button class="btn btn-gold" onclick="confirmAppt('${id}')">Confirmar</button>
    `;
  } else {
    footer.innerHTML = `<button class="btn btn-outline" onclick="closeModal('modal-view-appt')">Fechar</button>`;
  }
  openModal('modal-view-appt');
}

function confirmAppt(id) {
  const appts = DB.get('appointments') || [];
  const idx = appts.findIndex(a => a.id === id);
  if (idx >= 0) appts[idx].status = 'Confirmado';
  DB.set('appointments', appts);
  closeModal('modal-view-appt');
  renderAppointments();
  toast('Agendamento confirmado!', 'success');
}

function deleteAppt(id) {
  DB.set('appointments', (DB.get('appointments')||[]).filter(a => a.id !== id));
  closeModal('modal-view-appt');
  renderAppointments();
  toast('Agendamento removido.', 'info');
}

/* ──────────────────────────────
   NOTIFICATIONS
────────────────────────────── */
function renderNotifications() {
  const all  = (DB.get('notifications') || []).filter(n => n.userId === currentUser.id);
  const list = document.getElementById('notif-list');
  if (!list) return;
  list.innerHTML = all.map(n => `
    <div class="notif-item" onclick="markRead('${n.id}')">
      <div class="notif-dot2 ${n.read ? 'read' : ''}"></div>
      <div style="flex:1">
        <div class="notif-title">${n.title}</div>
        <div class="notif-sub">${n.body}</div>
        <div class="notif-time">Há ${n.time}</div>
      </div>
      ${!n.read ? '<span class="tag tag-gold">Nova</span>' : ''}
    </div>
  `).join('') || emptyState('notifications','Sem notificações.');
}

function markRead(id) {
  const notifs = DB.get('notifications') || [];
  const idx = notifs.findIndex(n => n.id === id);
  if (idx >= 0) notifs[idx].read = true;
  DB.set('notifications', notifs);
  renderNotifications();
  updateNotifDot();
  renderSidebar();
}

function markAllRead() {
  const notifs = (DB.get('notifications') || []).map(n => n.userId === currentUser.id ? {...n, read:true} : n);
  DB.set('notifications', notifs);
  renderNotifications();
  updateNotifDot();
  renderSidebar();
  toast('Todas marcadas como lidas.', 'success');
}

/* ──────────────────────────────
   LEADS
────────────────────────────── */
function renderLeads() {
  const leads = DB.get('leads') || [];
  const board = document.getElementById('kanban-board');
  if (!board) return;
  board.innerHTML = STAGES.map(stage => {
    const stageLeads = leads.filter(l => l.stage === stage);
    const total = stageLeads.reduce((s,l) => s + Number(l.value||0), 0);
    return `
      <div class="kanban-col">
        <div class="kanban-col-title">${stage}<span class="pipeline-total">R$ ${total.toLocaleString('pt-BR')}</span></div>
        ${stageLeads.map(l => `
          <div class="kanban-card" onclick="viewLead('${l.id}')">
            <div class="kanban-card-title">${l.name}</div>
            <div class="kanban-card-sub">${l.company || l.email}</div>
            <div class="kanban-card-footer">
              <span class="tag ${PRIORITY_CLASS[l.priority]||'tag-gray'}">${l.priority}</span>
              <span style="font-size:12px;font-weight:600;color:var(--gold)">R$ ${Number(l.value||0).toLocaleString('pt-BR')}</span>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }).join('');
}

function viewLead(id) {
  const l = (DB.get('leads')||[]).find(x => x.id === id);
  if (!l) return;
  document.getElementById('vlead-title').textContent = l.name;
  document.getElementById('vlead-body').innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div><div class="form-label">Empresa</div><div style="font-size:14px;font-weight:600">${l.company||'—'}</div></div>
      <div><div class="form-label">E-mail</div><div style="font-size:14px">${l.email||'—'}</div></div>
      <div><div class="form-label">Valor Estimado</div><div style="font-size:20px;font-weight:700;color:var(--gold)">R$ ${Number(l.value||0).toLocaleString('pt-BR')}</div></div>
      <div><div class="form-label">Prioridade</div><span class="tag ${PRIORITY_CLASS[l.priority]||'tag-gray'}">${l.priority}</span></div>
      <div><div class="form-label">Estágio Atual</div><span class="tag ${STAGE_COLORS[l.stage]}">${l.stage}</span></div>
    </div>
    <div style="margin-top:20px">
      <div class="form-label">Mover para estágio</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
        ${STAGES.filter(s => s !== l.stage).map(s => `<button class="btn btn-outline btn-sm" onclick="moveLeadStage('${l.id}','${s}')">${s}</button>`).join('')}
      </div>
    </div>
  `;
  document.getElementById('vlead-footer').innerHTML = `
    <button class="btn btn-danger btn-sm" onclick="deleteLead('${l.id}')">Excluir</button>
    <button class="btn btn-outline" onclick="closeModal('modal-view-lead')">Fechar</button>
    <button class="btn btn-gold" onclick="convertLead('${l.id}')">Converter em Cliente</button>
  `;
  openModal('modal-view-lead');
}

function moveLeadStage(id, stage) {
  const leads = DB.get('leads') || [];
  const idx = leads.findIndex(l => l.id === id);
  if (idx >= 0) leads[idx].stage = stage;
  DB.set('leads', leads);
  closeModal('modal-view-lead');
  renderLeads();
  toast(`Lead movido para ${stage}!`, 'success');
}

function convertLead(id) {
  const leads = DB.get('leads') || [];
  const l = leads.find(x => x.id === id);
  if (!l) return;
  const clients = DB.get('clients') || [];
  clients.push({ id:'c'+Date.now(), name:l.name, company:l.company||'', email:l.email||'', phone:'', status:'Ativo', notes:`Convertido de lead. Valor: R$ ${Number(l.value||0).toLocaleString('pt-BR')}`, linkedUserId:null });
  DB.set('clients', clients);
  DB.set('leads', leads.filter(x => x.id !== id));
  closeModal('modal-view-lead');
  renderLeads();
  addNotif('u1', 'Lead convertido', `${l.name} foi convertido em cliente.`);
  toast(`${l.name} convertido em cliente!`, 'success');
}

function deleteLead(id) {
  DB.set('leads', (DB.get('leads')||[]).filter(l => l.id !== id));
  closeModal('modal-view-lead');
  renderLeads();
  toast('Lead removido.', 'info');
}

function saveLead() {
  const name = document.getElementById('lead-name').value.trim();
  if (!name) { showErr('lead-name-err'); document.getElementById('lead-name').classList.add('error'); return; }
  hideErr('lead-name-err'); document.getElementById('lead-name').classList.remove('error');

  const leads = DB.get('leads') || [];
  leads.push({ id:'l'+Date.now(), name, company:document.getElementById('lead-company').value, email:document.getElementById('lead-email').value, value:document.getElementById('lead-value').value||0, stage:document.getElementById('lead-stage').value, priority:document.getElementById('lead-priority').value, createdAt:new Date().toISOString().slice(0,10) });
  DB.set('leads', leads);
  ['lead-name','lead-company','lead-email','lead-value'].forEach(id => document.getElementById(id).value = '');
  closeModal('modal-add-lead');
  renderLeads();
  if (currentSection === 'dashboard') renderAdminDash();
  toast('Lead adicionado!', 'success');
}

/* ──────────────────────────────
   REPORTS
────────────────────────────── */
function renderReports() {
  const clients = DB.get('clients') || [];
  const docs    = DB.get('documents') || [];
  const leads   = DB.get('leads') || [];
  const appts   = DB.get('appointments') || [];
  const totalLeadValue = leads.reduce((s,l) => s + Number(l.value||0), 0);

  const bars = [
    {label:'Jan',v:40},{label:'Fev',v:65},{label:'Mar',v:50},{label:'Abr',v:80},
    {label:'Mai',v:95},{label:'Jun',v:70},{label:'Jul',v:88},{label:'Ago',v:60},
    {label:'Set',v:75},{label:'Out',v:100},{label:'Nov',v:85},{label:'Dez',v:55}
  ];
  const maxV = Math.max(...bars.map(b => b.v));

  document.getElementById('reports-content').innerHTML = `
    <div class="grid-4" style="margin-bottom:20px">
      <div class="stat-card"><div class="stat-value">${clients.length}</div><div class="stat-label">Clientes Totais</div></div>
      <div class="stat-card"><div class="stat-value">${docs.length}</div><div class="stat-label">Documentos</div></div>
      <div class="stat-card accent"><div class="stat-value">R$ ${(totalLeadValue/1000).toFixed(0)}K</div><div class="stat-label">Pipeline Total</div></div>
      <div class="stat-card"><div class="stat-value">${appts.length}</div><div class="stat-label">Agendamentos</div></div>
    </div>
    <div class="grid-2">
      <div class="card">
        <div class="card-title">Atividade Mensal (Leads)</div>
        <div class="chart-bar-wrap">
          ${bars.map((b,i) => `<div class="chart-bar-col">
            <div class="chart-bar ${i===9?'active':''}" style="height:${(b.v/maxV)*100}%"></div>
            <div class="chart-bar-label">${b.label}</div>
          </div>`).join('')}
        </div>
      </div>
      <div class="card">
        <div class="card-title">Documentos por Status</div>
        ${['Assinado','Em Revisão','Aguardando','Arquivado'].map(s => {
          const count = docs.filter(d => d.status === s).length;
          const pct   = docs.length ? Math.round(count/docs.length*100) : 0;
          return `<div style="margin-bottom:14px">
            <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px">
              <span style="font-weight:500">${s}</span>
              <span style="color:var(--text-light)">${count} (${pct}%)</span>
            </div>
            <div style="background:var(--cream-dark);border-radius:99px;height:8px">
              <div style="background:linear-gradient(90deg,var(--gold),var(--gold-bright));height:100%;border-radius:99px;width:${pct}%;transition:width .5s"></div>
            </div>
          </div>`;
        }).join('')}
      </div>
      <div class="card">
        <div class="card-title">Pipeline por Estágio</div>
        ${STAGES.map(s => {
          const sLeads = leads.filter(l => l.stage === s);
          const total  = sLeads.reduce((sum,l) => sum + Number(l.value||0), 0);
          return `<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--cream-dark)">
            <span class="tag ${STAGE_COLORS[s]}">${s}</span>
            <div style="text-align:right">
              <div style="font-size:14px;font-weight:600;color:var(--gold)">R$ ${total.toLocaleString('pt-BR')}</div>
              <div style="font-size:11px;color:var(--text-light)">${sLeads.length} lead(s)</div>
            </div>
          </div>`;
        }).join('')}
      </div>
      <div class="card">
        <div class="card-title">Status dos Clientes</div>
        ${['Ativo','Prospect','Inativo'].map(s => {
          const count = clients.filter(c => c.status === s).length;
          return `<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--cream-dark)">
            <span class="tag ${s==='Ativo'?'tag-green':s==='Inativo'?'tag-red':'tag-gold'}">${s}</span>
            <span style="font-size:22px;font-weight:700;font-family:'Playfair Display',serif;color:var(--gold)">${count}</span>
          </div>`;
        }).join('')}
      </div>
    </div>
  `;
}

/* ──────────────────────────────
   SETTINGS
────────────────────────────── */
function renderSettingsForm() {
  document.getElementById('settings-avatar').textContent = currentUser.avatar || currentUser.name[0];
  document.getElementById('settings-name').textContent   = currentUser.name;
  document.getElementById('settings-email').textContent  = currentUser.email || currentUser.username;
  document.getElementById('cfg-name').value    = currentUser.name;
  document.getElementById('cfg-email').value   = currentUser.email || '';
  document.getElementById('cfg-company').value = currentUser.company || '';
}

function saveSettings() {
  const users = DB.get('users') || [];
  const idx   = users.findIndex(u => u.id === currentUser.id);
  if (idx >= 0) {
    users[idx].name    = document.getElementById('cfg-name').value    || users[idx].name;
    users[idx].email   = document.getElementById('cfg-email').value   || users[idx].email;
    users[idx].company = document.getElementById('cfg-company').value || users[idx].company;
    DB.set('users', users);
    currentUser = users[idx];
    renderSidebar();
    renderSettingsForm();
  }
  toast('Configurações salvas!', 'success');
}

/* ──────────────────────────────
   MODAL OVERLAY DISMISS
────────────────────────────── */
document.querySelectorAll('.modal-overlay').forEach(o => {
  o.addEventListener('click', e => { if (e.target === o) o.classList.remove('open'); });
});

/* ──────────────────────────────
   INIT
────────────────────────────── */
initDB();

// Inject icons into login form
document.getElementById('login-icon-at').innerHTML   = ICONS.at;
document.getElementById('login-icon-lock').innerHTML = ICONS.lock;
document.getElementById('eye-toggle').innerHTML      = ICONS.eye;

// Set default appt date
const apptDateEl = document.getElementById('appt-date');
if (apptDateEl) apptDateEl.value = new Date().toISOString().slice(0,10);

// Login keyboard shortcuts
document.getElementById('login-user')?.addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('login-pass').focus(); });
document.getElementById('login-pass')?.addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });
