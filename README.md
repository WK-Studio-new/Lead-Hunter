# ⚡ LeadHunter Pro v4 — Vercel Deploy

Sistema completo hospedado no Vercel. Backend Flask (serverless) + Frontend estático.

---

## 📁 Estrutura

```
leadhunter/
├── api/
│   └── index.py          ← Backend Flask (Vercel serverless)
├── frontend/
│   └── index.html        ← Frontend (abrir direto ou hospedar)
├── requirements.txt      ← Dependências Python
├── vercel.json           ← Roteamento Vercel
└── README.md
```

---

## 🚀 Deploy no Vercel

### 1. Subir para o GitHub

```bash
git init
git add .
git commit -m "LeadHunter v4 - Vercel"
git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
git push -u origin main
```

### 2. Importar no Vercel

1. Acesse [vercel.com](https://vercel.com) → **Add New Project**
2. Selecione o repositório do GitHub
3. Clique em **Deploy** (sem alterar nada)

---

## 🔐 Configuração inicial (obrigatório)

### Passo 1 — Gerar a FERNET_KEY

Acesse no navegador:
```
https://lead-hunter-neon.vercel.app/api/generate-key
```

Copie o valor de `FERNET_KEY` retornado. **Guarde em local seguro.**

### Passo 2 — Adicionar FERNET_KEY no Vercel

No painel do Vercel:
1. **Settings → Environment Variables**
2. Adicione: `FERNET_KEY` = *(valor copiado acima)*
3. Clique em **Save** e faça um novo **Deploy**

### Passo 3 — Configurar API Key e senhas

Faça uma requisição POST para `/api/setup`:

```bash
curl -X POST https://lead-hunter-neon.vercel.app/api/setup \
  -H "Content-Type: application/json" \
  -d '{
    "serp_key": "SUA_SERPAPI_KEY",
    "admin_password": "sua_senha_admin",
    "team_password": "senha_da_equipe"
  }'
```

A resposta vai trazer 3 valores:

```json
{
  "env_vars": {
    "SERP_API_KEY_ENC": "...",
    "ADMIN_HASH": "...",
    "TEAM_HASH": "..."
  }
}
```

### Passo 4 — Adicionar as 3 variáveis no Vercel

Em **Settings → Environment Variables**, adicione:
- `SERP_API_KEY_ENC` = *(valor retornado)*
- `ADMIN_HASH` = *(valor retornado)*
- `TEAM_HASH` = *(valor retornado)*

Faça um novo **Deploy**. Pronto! ✅

---

## 🔑 Variáveis de ambiente (resumo)

| Variável | Como obter |
|---|---|
| `FERNET_KEY` | `/api/generate-key` |
| `SERP_API_KEY_ENC` | Resposta do `/api/setup` |
| `ADMIN_HASH` | Resposta do `/api/setup` |
| `TEAM_HASH` | Resposta do `/api/setup` |

---

## ⚠️ Diferença importante vs versão local

No Vercel (serverless), os tokens de sessão ficam **em memória**. Se o container reiniciar (o que pode acontecer após inatividade), o usuário precisa fazer login novamente. Isso é normal e esperado.

---

## 🔑 Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/status` | Status + se setup foi feito |
| `GET` | `/api/generate-key` | Gera FERNET_KEY (usar só 1x) |
| `POST` | `/api/setup` | Retorna env vars para configurar |
| `POST` | `/api/token` | Login → retorna token |
| `GET` | `/api/key` | Retorna API Key (requer token) |
| `POST` | `/api/change-password` | Troca senhas (requer admin) |
