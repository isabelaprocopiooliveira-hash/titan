"""
TITAN BRAWL — Arena dos Deuses
Backend Flask + SQLite (biblioteca padrão, sem flask_sqlalchemy)

Rotas:
  GET  /                  jogo
  POST /api/register      { username, password }
  POST /api/login         { username, password }
  POST /api/save_match    { player1, player2, winner, duration }
  GET  /api/leaderboard
  GET  /api/health

Como rodar:
  pip install flask
  python app.py

Abra http://localhost:5000
"""

import os
import re
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "titan_brawl.db")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


# ══════════════════════════════════════════════
# BANCO (sqlite3 nativo)
# ══════════════════════════════════════════════
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            total_matches INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1 TEXT NOT NULL,
            player2 TEXT NOT NULL,
            winner TEXT NOT NULL,
            duration INTEGER NOT NULL DEFAULT 0,
            played_at TEXT NOT NULL
        );
        """
    )
    db.commit()
    db.close()


def player_dict(row):
    return {
        "username": row["username"],
        "wins": row["wins"],
        "losses": row["losses"],
        "total_matches": row["total_matches"],
    }


def find_player(username):
    return get_db().execute(
        "SELECT * FROM players WHERE username = ? COLLATE NOCASE",
        (username,),
    ).fetchone()


# ══════════════════════════════════════════════
# CORS simples (sem flask-cors)
# ══════════════════════════════════════════════
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def cors_preflight(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return ("", 204)
        return fn(*args, **kwargs)

    return wrapper


def bad_request(message, status=400):
    return jsonify({"success": False, "message": message}), status


# ══════════════════════════════════════════════
# FRONTEND
# ══════════════════════════════════════════════
@app.route("/")
def index():
    # send_from_directory evita o Jinja interpretar {{ }} do JavaScript
    return send_from_directory(os.path.join(BASE_DIR, "templates"), "index.html")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "titan-brawl-api"})


# ══════════════════════════════════════════════
# AUTENTICAÇÃO
# ══════════════════════════════════════════════
@app.route("/api/register", methods=["POST", "OPTIONS"])
@cors_preflight
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return bad_request("Preencha nome e senha.")
    if not USERNAME_RE.match(username):
        return bad_request("Nome deve ter 3-20 letras/números (sem espaços).")
    if len(password) < 4:
        return bad_request("Senha deve ter no mínimo 4 caracteres.")
    if find_player(username):
        return bad_request("Esse nome de guerreiro já está em uso.")

    db = get_db()
    db.execute(
        """
        INSERT INTO players (username, password_hash, wins, losses, total_matches, created_at)
        VALUES (?, ?, 0, 0, 0, ?)
        """,
        (username, generate_password_hash(password), datetime.utcnow().isoformat()),
    )
    db.commit()
    player = find_player(username)
    return jsonify({
        "success": True,
        "message": f"Guerreiro {username} registrado com sucesso!",
        "player": player_dict(player),
    })


@app.route("/api/login", methods=["POST", "OPTIONS"])
@cors_preflight
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return bad_request("Preencha nome e senha.")

    player = find_player(username)
    if not player or not check_password_hash(player["password_hash"], password):
        return bad_request("Nome ou senha incorretos.", status=401)

    return jsonify({
        "success": True,
        "message": f"Bem-vindo de volta, {player['username']}!",
        "player": player_dict(player),
    })


# ══════════════════════════════════════════════
# PARTIDAS / RANKING
# ══════════════════════════════════════════════
def bump_stats(username, winner):
    player = find_player(username)
    if not player:
        return
    wins = player["wins"] + (1 if winner.lower() == player["username"].lower() else 0)
    losses = player["losses"] + (0 if winner.lower() == player["username"].lower() else 1)
    get_db().execute(
        """
        UPDATE players
        SET total_matches = total_matches + 1, wins = ?, losses = ?
        WHERE id = ?
        """,
        (wins, losses, player["id"]),
    )


@app.route("/api/save_match", methods=["POST", "OPTIONS"])
@cors_preflight
def save_match():
    data = request.get_json(silent=True) or {}
    player1 = (data.get("player1") or "").strip()
    player2 = (data.get("player2") or "").strip()
    winner = (data.get("winner") or "").strip()
    duration = data.get("duration") or 0

    if not player1 or not player2 or not winner:
        return bad_request("Dados da partida incompletos.")

    try:
        duration = int(duration)
    except (TypeError, ValueError):
        duration = 0

    played_at = datetime.utcnow().isoformat()
    db = get_db()
    cur = db.execute(
        """
        INSERT INTO matches (player1, player2, winner, duration, played_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (player1, player2, winner, duration, played_at),
    )
    bump_stats(player1, winner)
    if player2.lower() != player1.lower():
        bump_stats(player2, winner)
    db.commit()

    return jsonify({
        "success": True,
        "match": {
            "player1": player1,
            "player2": player2,
            "winner": winner,
            "duration": duration,
            "played_at": played_at,
        },
    })


@app.route("/api/leaderboard", methods=["GET", "OPTIONS"])
@cors_preflight
def leaderboard():
    try:
        limit = int(request.args.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    rows = get_db().execute(
        """
        SELECT username, wins, losses, total_matches
        FROM players
        WHERE total_matches > 0
        ORDER BY wins DESC, losses ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return jsonify([player_dict(r) for r in rows])


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)