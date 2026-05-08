"""
backend/server.py
Flask local backend para o LeadHunter Pro.

Endpoints:
  POST /api/setup       — salva API key (requer senha de admin)
  POST /api/token       — autentica usuário, retorna JWT
  GET  /api/key         — retorna API key (requer JWT válido)
  GET  /api/status      — status do servidor
  POST /api/change-password — troca senha de admin
"""

import os, json, hashlib, secrets, time
from pathlib import Path
from functools import wraps
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
from cryptography.fernet import Fernet

# ── CONFIG ──────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
KEY_FILE    = BASE_DIR / ".fernet.key"

app = Flask(__name__)
CORS(app, origins=["*"])   # equipe local — liberar todas as origens

# ── FERNET (criptografia simétrica) ─────────────────────────────────────────────
def get_fernet() -> Fernet:
    if not KEY_FILE.exists():
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
        KEY_FILE.chmod(0o600)
    return Fernet(KEY_FILE.read_bytes())

def encrypt(text: str) -> str:
    return get_fernet().encrypt(text.encode()).decode()

def decrypt(token: str) -> str:
    return get_fernet().decrypt(token.encode()).decode()

# ── CONFIG JSON ──────────────────────────────────────────────────────────────────
def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    return json.loads(CONFIG_FILE.read_text())

def save_config(data: dict):
    CONFIG_FILE.write_text(json.dumps(data, indent=2))
    CONFIG_FILE.chmod(0o600)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ── JWT SIMPLES (sem dependência) ────────────────────────────────────────────────
_tokens: dict[str, float] = {}   # token → expiry timestamp
TOKEN_TTL = 60 * 60 * 8          # 8 horas

def issue_token() -> str:
    t = secrets.token_urlsafe(32)
    _tokens[t] = time.time() + TOKEN_TTL
    # limpar expirados
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
    cfg = load_config()
    return jsonify({
        "ok":        True,
        "setup_done": bool(cfg.get("api_key_enc")),
        "version":   "4.0",
        "time":      datetime.now().isoformat(),
    })


@app.route("/api/setup", methods=["POST"])
def setup():
    """
    Salva a SerpApi key e define a senha de admin.
    Corpo JSON: { "admin_password": "...", "serp_key": "...", "team_password": "..." }
    Se já existir configuração, exige a senha de admin atual.
    """
    body = request.get_json(force=True) or {}
    cfg  = load_config()

    serp_key      = (body.get("serp_key") or "").strip()
    team_password = (body.get("team_password") or "").strip()
    admin_password= (body.get("admin_password") or "").strip()

    if not serp_key:
        return jsonify({"error": "Informe a SerpApi Key."}), 400
    if not admin_password:
        return jsonify({"error": "Informe a senha de admin."}), 400
    if not team_password:
        return jsonify({"error": "Informe a senha de acesso da equipe."}), 400

    # Se já existe configuração, validar senha de admin atual
    if cfg.get("admin_hash"):
        if hash_password(admin_password) != cfg["admin_hash"]:
            return jsonify({"error": "Senha de admin incorreta."}), 403

    cfg["api_key_enc"]   = encrypt(serp_key)
    cfg["admin_hash"]    = hash_password(admin_password)
    cfg["team_hash"]     = hash_password(team_password)
    cfg["updated_at"]    = datetime.now().isoformat()
    save_config(cfg)

    return jsonify({"ok": True, "message": "Configuração salva com sucesso."})


@app.route("/api/token", methods=["POST"])
def get_token():
    """
    Autentica com senha de equipe e retorna JWT.
    Corpo JSON: { "password": "..." }
    """
    cfg  = load_config()
    if not cfg.get("team_hash"):
        return jsonify({"error": "Backend não configurado. Acesse /setup primeiro."}), 503

    body     = request.get_json(force=True) or {}
    password = (body.get("password") or "").strip()

    if hash_password(password) != cfg["team_hash"]:
        return jsonify({"error": "Senha incorreta."}), 403

    return jsonify({"ok": True, "token": issue_token(), "ttl": TOKEN_TTL})


@app.route("/api/key")
@require_token
def get_key():
    """Retorna a SerpApi key descriptografada (requer token válido)."""
    cfg = load_config()
    if not cfg.get("api_key_enc"):
        return jsonify({"error": "Nenhuma API Key configurada."}), 404
    try:
        key = decrypt(cfg["api_key_enc"])
        return jsonify({"ok": True, "key": key})
    except Exception:
        return jsonify({"error": "Falha ao descriptografar a chave."}), 500


@app.route("/api/change-password", methods=["POST"])
def change_password():
    """
    Troca senha de equipe ou de admin.
    Corpo JSON: { "admin_password": "...", "new_team_password": "...", "new_admin_password": "..." }
    """
    cfg  = load_config()
    body = request.get_json(force=True) or {}
    admin_pw = (body.get("admin_password") or "").strip()

    if hash_password(admin_pw) != cfg.get("admin_hash", ""):
        return jsonify({"error": "Senha de admin incorreta."}), 403

    if body.get("new_team_password"):
        cfg["team_hash"] = hash_password(body["new_team_password"].strip())
    if body.get("new_admin_password"):
        cfg["admin_hash"] = hash_password(body["new_admin_password"].strip())

    cfg["updated_at"] = datetime.now().isoformat()
    save_config(cfg)
    return jsonify({"ok": True, "message": "Senha atualizada."})


# ── MAIN ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n⚡ LeadHunter Backend rodando em http://localhost:{port}")
    print(f"   Config: {CONFIG_FILE}")
    print(f"   Acesse http://localhost:{port}/api/status para verificar\n")
    app.run(host="0.0.0.0", port=port, debug=False)
