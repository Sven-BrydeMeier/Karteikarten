"""
Smart Study Cards — Chrome Extension API Server

Lightweight REST API that runs alongside the Streamlit app,
providing endpoints for the Chrome extension to read/write flashcard data.

Usage:
    python chrome_api.py                    # Runs on port 8502
    python chrome_api.py --port 8510        # Custom port

The API shares the same SQLite database as the Streamlit app.
"""

import json
import sqlite3
import datetime as dt
import argparse
from contextlib import contextmanager
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ---- Config ----
DB_PATH = "study_app.db"
DEFAULT_PORT = 8502
APP_VERSION = "1.0.0"


# ---- Database helpers ----
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row):
    """Convert a sqlite3.Row to a dict."""
    return dict(row)


# ---- API Handler ----
class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Chrome extension API."""

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self._send_cors_headers()
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        routes = {
            "/api/health": self._health,
            "/api/decks": self._get_decks,
            "/api/cards/due": self._get_due_cards,
            "/api/stats": self._get_stats,
        }

        handler = routes.get(path)
        if handler:
            handler(params)
        else:
            self._json_response({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_length > 0:
            raw = self.rfile.read(content_length)
            body = json.loads(raw.decode("utf-8"))

        # POST /api/cards/<id>/answer
        if path.startswith("/api/cards/") and path.endswith("/answer"):
            parts = path.split("/")
            try:
                card_id = int(parts[3])
            except (IndexError, ValueError):
                self._json_response({"error": "Invalid card ID"}, 400)
                return
            self._submit_answer(card_id, body)
            return

        routes = {
            "/api/cards": self._create_card,
            "/api/decks": self._create_deck,
        }

        handler = routes.get(path)
        if handler:
            handler(body)
        else:
            self._json_response({"error": "Not found"}, 404)

    # ---- Route handlers ----

    def _health(self, params):
        self._json_response({
            "status": "ok",
            "version": APP_VERSION,
            "timestamp": dt.datetime.now().isoformat(),
        })

    def _get_decks(self, params):
        user_id = int(params.get("user_id", [1])[0])
        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT * FROM decks WHERE user_id=? ORDER BY id DESC",
                (user_id,),
            )
            decks = []
            for row in c.fetchall():
                d = row_to_dict(row)
                # Get card count and mastery percentage
                c2 = conn.cursor()
                c2.execute(
                    "SELECT COUNT(*) as total, "
                    "SUM(CASE WHEN box >= 4 THEN 1 ELSE 0 END) as mastered "
                    "FROM cards WHERE deck_id=? AND user_id=?",
                    (d["id"], user_id),
                )
                stats = c2.fetchone()
                d["card_count"] = stats["total"] or 0
                total = stats["total"] or 0
                mastered = stats["mastered"] or 0
                d["mastery_pct"] = round((mastered / total * 100) if total > 0 else 0)
                decks.append(d)

        self._json_response(decks)

    def _get_due_cards(self, params):
        user_id = int(params.get("user_id", [1])[0])
        max_cards = int(params.get("max_cards", [10])[0])
        deck_id = params.get("deck_id", [None])[0]

        today_str = dt.date.today().isoformat()

        with get_db() as conn:
            c = conn.cursor()

            sql = (
                "SELECT * FROM cards WHERE user_id=? AND due_date<=?"
            )
            sql_params = [user_id, today_str]

            if deck_id is not None:
                sql += " AND deck_id=?"
                sql_params.append(int(deck_id))

            sql += " ORDER BY box ASC, due_date ASC LIMIT ?"
            sql_params.append(max_cards)

            c.execute(sql, sql_params)
            cards = []
            for row in c.fetchall():
                card = row_to_dict(row)
                # Parse choices JSON
                if card.get("choices_json"):
                    card["choices"] = json.loads(card["choices_json"])
                else:
                    card["choices"] = None
                # Parse tags
                if card.get("tags_json"):
                    card["tags"] = json.loads(card["tags_json"])
                else:
                    card["tags"] = []
                # Clean up internal fields
                card.pop("choices_json", None)
                card.pop("tags_json", None)
                cards.append(card)

        self._json_response(cards)

    def _get_stats(self, params):
        user_id = int(params.get("user_id", [1])[0])
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM user_stats WHERE user_id=?", (user_id,))
            row = c.fetchone()
            if row:
                stats = row_to_dict(row)
                if stats.get("achievements_json"):
                    stats["achievements"] = json.loads(stats["achievements_json"])
                stats.pop("achievements_json", None)
                self._json_response(stats)
            else:
                self._json_response({
                    "user_id": user_id,
                    "total_xp": 0,
                    "level": 1,
                    "current_streak": 0,
                    "longest_streak": 0,
                    "total_cards_learned": 0,
                    "total_correct": 0,
                    "total_sessions": 0,
                })

    def _submit_answer(self, card_id, body):
        result = body.get("result", "wrong")  # "correct", "hard", "wrong"

        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM cards WHERE id=?", (card_id,))
            row = c.fetchone()

            if not row:
                self._json_response({"error": "Card not found"}, 404)
                return

            box = row["box"]
            streak = row["success_streak"]
            in_special = row["in_special_bucket"]

            # Spaced repetition logic — matches app.py BOX_INTERVALS and update_card_after_result
            BOX_INTERVALS = {1: 1, 2: 2, 3: 4, 4: 7, 5: 15}

            if result == "correct":
                in_special = 0
                streak += 1
                box = min(box + 1, max(BOX_INTERVALS.keys()))
            else:  # wrong or hard
                in_special = 1
                streak = 0
                box = 1

            interval_days = BOX_INTERVALS.get(box, 1)
            new_due = (dt.date.today() + dt.timedelta(days=interval_days)).isoformat()
            today_str = dt.date.today().isoformat()

            c.execute(
                "UPDATE cards SET box=?, due_date=?, last_reviewed=?, "
                "success_streak=?, in_special_bucket=? WHERE id=?",
                (box, new_due, today_str, streak, in_special, card_id),
            )

            # Update stats
            user_id = row["user_id"]
            if result == "correct":
                c.execute(
                    "UPDATE cards SET times_correct = COALESCE(times_correct, 0) + 1 WHERE id=?",
                    (card_id,),
                )
                c.execute(
                    "UPDATE user_stats SET total_correct = total_correct + 1, "
                    "total_cards_learned = total_cards_learned + 1, "
                    "total_xp = total_xp + 10 "
                    "WHERE user_id=?",
                    (user_id,),
                )
            else:
                c.execute(
                    "UPDATE cards SET times_wrong = COALESCE(times_wrong, 0) + 1 WHERE id=?",
                    (card_id,),
                )
                c.execute(
                    "UPDATE user_stats SET total_cards_learned = total_cards_learned + 1 "
                    "WHERE user_id=?",
                    (user_id,),
                )

        self._json_response({"ok": True, "box": box, "due_date": new_due})

    def _create_card(self, body):
        required = ["deck_id", "question", "answer"]
        for field in required:
            if not body.get(field):
                self._json_response({"error": f"Missing field: {field}"}, 400)
                return

        deck_id = int(body["deck_id"])
        question = body["question"]
        answer = body["answer"]
        explanation = body.get("explanation", "")
        subject = body.get("subject", "Allgemein")

        with get_db() as conn:
            c = conn.cursor()

            # Verify deck exists and get user_id
            c.execute("SELECT user_id FROM decks WHERE id=?", (deck_id,))
            deck_row = c.fetchone()
            if not deck_row:
                self._json_response({"error": "Deck not found"}, 404)
                return

            user_id = deck_row["user_id"]

            c.execute(
                "INSERT INTO cards "
                "(deck_id, user_id, subject, question, answer, explanation, "
                "box, due_date, success_streak, in_special_bucket, card_type) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?, 0, 0, 'standard')",
                (deck_id, user_id, subject, question, answer, explanation,
                 dt.date.today().isoformat()),
            )
            card_id = c.lastrowid

        self._json_response({"ok": True, "card_id": card_id}, 201)

    def _create_deck(self, body):
        name = body.get("name", "").strip()
        if not name:
            self._json_response({"error": "Missing field: name"}, 400)
            return

        subject = body.get("subject", "Allgemein")
        topic = body.get("topic", "Allgemein")
        user_id = int(body.get("user_id", 1))

        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO decks (user_id, name, subject, topic) VALUES (?, ?, ?, ?)",
                (user_id, name, subject, topic),
            )
            deck_id = c.lastrowid

        self._json_response({"ok": True, "deck_id": deck_id}, 201)

    # ---- HTTP helpers ----

    def _json_response(self, data, status=200):
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        """Override to add prefix to log messages."""
        print(f"[Chrome API] {args[0]} {args[1]} {args[2]}")


# ---- Main ----
def main():
    parser = argparse.ArgumentParser(description="Smart Study Cards Chrome API Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), APIHandler)
    print(f"Smart Study Cards Chrome API running on http://{args.host}:{args.port}")
    print(f"Database: {DB_PATH}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
