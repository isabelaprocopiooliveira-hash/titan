#!/usr/bin/env python3
"""
TITAN BRAWL - Backend Server
Flask + SQLite authentication system
Run: python server.py
Access: http://localhost:5000
"""

from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import hashlib
import os
import json
from datetime import datetime

app = Flask(__name__, static_folder='.')

DB_PATH = 'titan_brawl.db'

# ─── Database Setup ───────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            total_matches INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS match_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1 TEXT NOT NULL,
            player2 TEXT NOT NULL,
            winner TEXT NOT NULL,
            duration_seconds INTEGER,
            played_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("✓ Database initialized: titan_brawl.db")


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'success': False, 'message': 'Usuário e senha obrigatórios'}), 400

    if len(username) < 3 or len(username) > 20:
        return jsonify({'success': False, 'message': 'Usuário deve ter entre 3 e 20 caracteres'}), 400

    if len(password) < 4:
        return jsonify({'success': False, 'message': 'Senha deve ter no mínimo 4 caracteres'}), 400

    if not username.isalnum():
        return jsonify({'success': False, 'message': 'Usuário só pode conter letras e números'}), 400

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO players (username, password_hash, last_login) VALUES (?, ?, ?)',
            (username, hash_password(password), datetime.now().isoformat())
        )
        conn.commit()
        player = conn.execute('SELECT * FROM players WHERE username=?', (username,)).fetchone()
        return jsonify({
            'success': True,
            'message': f'Guerreiro {username} registrado!',
            'player': {
                'id': player['id'],
                'username': player['username'],
                'wins': player['wins'],
                'losses': player['losses'],
                'total_matches': player['total_matches']
            }
        })
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Nome de guerreiro já existe!'}), 409
    finally:
        conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    conn = get_db()
    try:
        player = conn.execute(
            'SELECT * FROM players WHERE username=? AND password_hash=?',
            (username, hash_password(password))
        ).fetchone()

        if not player:
            return jsonify({'success': False, 'message': 'Usuário ou senha incorretos'}), 401

        conn.execute(
            'UPDATE players SET last_login=? WHERE id=?',
            (datetime.now().isoformat(), player['id'])
        )
        conn.commit()

        return jsonify({
            'success': True,
            'message': f'Bem-vindo de volta, {username}!',
            'player': {
                'id': player['id'],
                'username': player['username'],
                'wins': player['wins'],
                'losses': player['losses'],
                'total_matches': player['total_matches']
            }
        })
    finally:
        conn.close()


@app.route('/api/save_match', methods=['POST'])
def save_match():
    data = request.get_json()
    player1 = data.get('player1')
    player2 = data.get('player2')
    winner = data.get('winner')
    duration = data.get('duration', 0)

    if not all([player1, player2, winner]):
        return jsonify({'success': False, 'message': 'Dados incompletos'}), 400

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO match_history (player1, player2, winner, duration_seconds) VALUES (?,?,?,?)',
            (player1, player2, winner, duration)
        )
        # Update stats for registered players
        for p in [player1, player2]:
            if p != 'Convidado':
                if p == winner:
                    conn.execute('UPDATE players SET wins=wins+1, total_matches=total_matches+1 WHERE username=?', (p,))
                else:
                    conn.execute('UPDATE players SET losses=losses+1, total_matches=total_matches+1 WHERE username=?', (p,))
        conn.commit()
        return jsonify({'success': True})
    finally:
        conn.close()


@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    conn = get_db()
    try:
        rows = conn.execute(
            'SELECT username, wins, losses, total_matches FROM players ORDER BY wins DESC LIMIT 10'
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route('/api/player/<username>', methods=['GET'])
def get_player(username):
    conn = get_db()
    try:
        player = conn.execute('SELECT * FROM players WHERE username=?', (username,)).fetchone()
        if not player:
            return jsonify({'success': False, 'message': 'Jogador não encontrado'}), 404
        return jsonify({'success': True, 'player': dict(player)})
    finally:
        conn.close()


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print("╔══════════════════════════════════════╗")
    print("║       TITAN BRAWL - SERVER           ║")
    print("║  Acesse: http://localhost:5000        ║")
    print("╚══════════════════════════════════════╝")
    app.run(debug=True, port=5000, host='0.0.0.0')