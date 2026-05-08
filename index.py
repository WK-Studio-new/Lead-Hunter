"""
api/index.py
Flask backend para o LeadHunter Pro — adaptado para Vercel (serverless).

Configuração via variáveis de ambiente (painel Vercel → Settings → Environment Variables):
  FERNET_KEY          — chave Fernet base64 (gere com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  SERP_API_KEY_ENC    — API Key SerpApi já criptografada (preenchida automaticamente pelo /api/setup)
  ADMIN_HASH          — SHA-256 da senha de admin
  TEAM_HASH           — SHA-256 da senha de equipe

Endpoints:
  GET  /api/status           — status do servidor
  POST /api/setup            — salva API key + senhas (1ª configuração)
  POST /api/token            — login → retorna token
  GET  /api/key              — retorna API key (requer token)
  POST /api/change-password  — troca senhas (requer admin)
  POST /api/generate-key     — gera e retorna uma nova FERNET_KEY (usar só na 1ª vez)
"""

import os, hashlib, secrets, time
from functools import wraps
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
from cryptography.fernet import Fernet

app = Flask(__name__)
CORS(app, origins=["https://lead-hunter-neon.vercel.app", "http://localhost:5000"])

# ── FERNET ───────────────────────────────────────────────────────────────────────

def get_fernet() -> Fernet:
    key = os.environ.get("FERNET_KEY", "").strip()
    if not key:
        raise RuntimeError("FERNET_KEY não definida nas variáveis de ambiente do Vercel.")
    return Fernet(key.encode())

def encrypt(text: str) -> str:
    return get_fernet().encrypt(text.encode()).decode()

def decrypt(token: str) -> str:
    return get_fernet().decrypt(token.encode()).decode()

# ── CONFIG via ENV ────────────────────────────────────────────────────────────────

def get_config() -> dict:
    return {
        "api_key_enc": os.environ.get("SERP_API_KEY_ENC", "").strip(),
        "admin_hash":  os.environ.get("ADMIN_HASH", "").strip(),
        "team_hash":   os.environ.get("TEAM_HASH", "").strip(),
    }

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ── TOKENS (memória — dura enquanto o container vive, ~5-10 min no Vercel) ────────

_tokens: dict[str, float] = {}
TOKEN_TTL = 60 * 60 * 8  # 8 horas (mas container pode reiniciar antes)

def issue_token() -> str:
    t = secrets.token_urlsafe(32)
    _tokens[t] = time.time() + TOKEN_TTL
    expired = [k for k, v in _tokens.items() if v < time.time()]
    for k in expired:
        del _tokens[k]
    return t

def valid_token(t: str) -> bool:
    exp = _tokens.get(t)
    return bool(exp and exp > time.time())

def require_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        if not valid_token(token):
            return jsonify({"error": "Não autorizado. Faça login novamente."}), 401
        return f(*args, **kwargs)
    return wrapper

# ── ROUTES ───────────────────────────────────────────────────────────────────────

@app.route("/api/status")
def status():
    cfg = get_config()
    return jsonify({
        "ok":         True,
        "setup_done": bool(cfg["api_key_enc"] and cfg["admin_hash"] and cfg["team_hash"]),
        "version":    "4.0-vercel",
        "time":       datetime.now().isoformat(),
    })


@app.route("/api/setup", methods=["POST"])
def setup():
    """
    Gera os valores das variáveis de ambiente que você deve copiar para o Vercel.
    Retorna os hashes e a key criptografada — NÃO salva nada automaticamente.
    Você precisa colar esses valores no painel do Vercel manualmente.

    Corpo JSON: { "admin_password": "...", "serp_key": "...", "team_password": "..." }
    Se ADMIN_HASH já existir no ambiente, exige a senha atual para reconfigurar.
    """
    body = request.get_json(force=True) or {}
    cfg  = get_config()

    serp_key       = (body.get("serp_key") or "").strip()
    team_password  = (body.get("team_password") or "").strip()
    admin_password = (body.get("admin_password") or "").strip()

    if not serp_key:
        return jsonify({"error": "Informe a SerpApi Key."}), 400
    if not admin_password:
        return jsonify({"error": "Informe a senha de admin."}), 400
    if not team_password:
        return jsonify({"error": "Informe a senha de acesso da equipe."}), 400

    # Se já configurado, valida senha admin atual
    if cfg["admin_hash"]:
        if hash_password(admin_password) != cfg["admin_hash"]:
            return jsonify({"error": "Senha de admin incorreta."}), 403

    try:
        api_key_enc = encrypt(serp_key)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    admin_hash = hash_password(admin_password)
    team_hash  = hash_password(team_password)

    return jsonify({
        "ok": True,
        "message": (
            "⚠️ ATENÇÃO: copie os valores abaixo para as variáveis de ambiente do Vercel "
            "(Settings → Environment Variables) e faça um novo deploy."
        ),
        "env_vars": {
            "SERP_API_KEY_ENC": api_key_enc,
            "ADMIN_HASH":       admin_hash,
            "TEAM_HASH":        team_hash,
        }
    })


@app.route("/api/token", methods=["POST"])
def get_token():
    cfg  = get_config()
    if not cfg["team_hash"]:
        return jsonify({"error": "Backend não configurado. Siga o README para configurar as variáveis de ambiente."}), 503

    body     = request.get_json(force=True) or {}
    password = (body.get("password") or "").strip()

    if hash_password(password) != cfg["team_hash"]:
        return jsonify({"error": "Senha incorreta."}), 403

    return jsonify({"ok": True, "token": issue_token(), "ttl": TOKEN_TTL})


@app.route("/api/key")
@require_token
def get_key():
    cfg = get_config()
    if not cfg["api_key_enc"]:
        return jsonify({"error": "Nenhuma API Key configurada."}), 404
    try:
        key = decrypt(cfg["api_key_enc"])
        return jsonify({"ok": True, "key": key})
    except Exception:
        return jsonify({"error": "Falha ao descriptografar a chave. Verifique FERNET_KEY e SERP_API_KEY_ENC."}), 500


@app.route("/api/change-password", methods=["POST"])
def change_password():
    """
    Retorna os novos hashes para você atualizar nas variáveis de ambiente do Vercel.
    """
    cfg  = get_config()
    body = request.get_json(force=True) or {}
    admin_pw = (body.get("admin_password") or "").strip()

    if hash_password(admin_pw) != cfg.get("admin_hash", ""):
        return jsonify({"error": "Senha de admin incorreta."}), 403

    new_env = {}
    if body.get("new_team_password"):
        new_env["TEAM_HASH"] = hash_password(body["new_team_password"].strip())
    if body.get("new_admin_password"):
        new_env["ADMIN_HASH"] = hash_password(body["new_admin_password"].strip())

    return jsonify({
        "ok": True,
        "message": "Copie os valores abaixo para as variáveis de ambiente do Vercel e faça um novo deploy.",
        "env_vars": new_env,
    })


@app.route("/api/generate-key", methods=["GET"])
def generate_key():
    """
    Gera uma nova FERNET_KEY. Use apenas uma vez, na configuração inicial.
    Depois de copiar o valor para o Vercel, este endpoint não é mais necessário.
    """
    key = Fernet.generate_key().decode()
    return jsonify({
        "ok":  True,
        "FERNET_KEY": key,
        "message": "Copie este valor para a variável FERNET_KEY no Vercel. Guarde-o em local seguro — sem ele, a API Key não pode ser descriptografada."
    })
