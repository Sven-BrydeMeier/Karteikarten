import os
import re
import json
import sqlite3
import datetime as dt
import random
import base64
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from io import BytesIO
from collections import defaultdict

import streamlit as st
from openai import OpenAI, RateLimitError as OpenAIRateLimitError, APIError as OpenAIAPIError
from anthropic import Anthropic, RateLimitError as AnthropicRateLimitError, APIError as AnthropicAPIError
from PIL import Image
import pdfplumber
from docx import Document
import pytesseract
from dotenv import load_dotenv

# ============================================================
# 0. Grund-Konfiguration Streamlit & .env
# ============================================================

# App-Version
APP_VERSION = "2.0.0"
APP_LAST_UPDATE = "2025-12-14 12:00"

load_dotenv()  # .env-Datei laden, falls vorhanden

st.set_page_config(
    page_title="Smart Study Cards",
    page_icon="📚",
    layout="wide",
)

# Erweiterte Styles für Karten und Gamification
st.markdown("""
<style>
.question-card {
    background-color: #ffffff;
    padding: 1rem 1.25rem;
    border-radius: 0.75rem;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.16);
    border: 1px solid rgba(148, 163, 184, 0.35);
    margin-bottom: 1rem;
}
.xp-bar {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    height: 20px;
    border-radius: 10px;
    transition: width 0.5s ease;
}
.streak-badge {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 20px;
    font-weight: bold;
    display: inline-block;
}
.achievement-card {
    background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
    padding: 1rem;
    border-radius: 10px;
    text-align: center;
    margin: 0.5rem;
}
.achievement-locked {
    background: #e0e0e0;
    filter: grayscale(100%);
    opacity: 0.6;
}
.cloze-blank {
    background-color: #fff3cd;
    padding: 2px 8px;
    border-radius: 4px;
    border-bottom: 2px solid #ffc107;
    min-width: 100px;
    display: inline-block;
}
.pomodoro-timer {
    font-size: 4rem;
    font-weight: bold;
    text-align: center;
    font-family: monospace;
}
.heatmap-cell {
    width: 12px;
    height: 12px;
    border-radius: 2px;
    display: inline-block;
    margin: 1px;
}
</style>
""", unsafe_allow_html=True)

# Gamification Konstanten
LEVEL_XP_REQUIREMENTS = [0, 100, 250, 500, 1000, 2000, 3500, 5500, 8000, 12000, 18000, 26000, 36000, 50000]
XP_PER_CORRECT = 10
XP_PER_PARTIAL = 5
XP_STREAK_BONUS = 5  # Extra XP pro Streak-Tag

ACHIEVEMENTS = {
    "first_card": {"name": "Erste Schritte", "desc": "Erste Karteikarte gelernt", "icon": "🎯", "xp": 50},
    "streak_3": {"name": "Auf Kurs", "desc": "3 Tage Streak", "icon": "🔥", "xp": 100},
    "streak_7": {"name": "Wochenkrieger", "desc": "7 Tage Streak", "icon": "⚡", "xp": 250},
    "streak_30": {"name": "Monatsmeister", "desc": "30 Tage Streak", "icon": "🏆", "xp": 1000},
    "cards_50": {"name": "Fleißig", "desc": "50 Karten gelernt", "icon": "📚", "xp": 150},
    "cards_100": {"name": "Bücherwurm", "desc": "100 Karten gelernt", "icon": "🐛", "xp": 300},
    "cards_500": {"name": "Wissensriese", "desc": "500 Karten gelernt", "icon": "🦸", "xp": 750},
    "perfect_session": {"name": "Perfektionist", "desc": "Session ohne Fehler", "icon": "💯", "xp": 200},
    "night_owl": {"name": "Nachteule", "desc": "Nach 22 Uhr gelernt", "icon": "🦉", "xp": 50},
    "early_bird": {"name": "Frühaufsteher", "desc": "Vor 7 Uhr gelernt", "icon": "🐦", "xp": 50},
    "deck_master": {"name": "Deckmeister", "desc": "Ein Deck komplett gemeistert", "icon": "👑", "xp": 500},
    "audio_learner": {"name": "Hörer", "desc": "Audio-Lernmodus genutzt", "icon": "🎧", "xp": 75},
    "exam_passed": {"name": "Prüfungsbereit", "desc": "Erste Prüfungssimulation", "icon": "🎓", "xp": 150},
}

# Fach-Farbcode
SUBJECT_COLORS = {
    "Rechtswissenschaften": "#e0f2fe",  # hellblau
    "Medizin": "#dcfce7",              # hellgrün
    "Informatik": "#fef9c3",           # hellgelb
    "Physik": "#fae8ff",               # helllila
    "Andere": "#f5f5f5",
}


# ============================================================
# 1. Datenmodelle (Dataclasses)
# ============================================================

@dataclass
class Card:
    id: int
    deck_id: int
    user_id: int
    subject: str = "Allgemein"
    question: str = ""
    answer: str = ""
    explanation: str = ""
    choices: Optional[List[str]] = None
    correct_choice_index: Optional[int] = None

    # Spaced Repetition
    box: int = 1
    due_date: dt.date = field(default_factory=lambda: dt.date.today())
    last_reviewed: Optional[dt.date] = None
    success_streak: int = 0
    in_special_bucket: bool = False
    tags: List[str] = field(default_factory=list)


@dataclass
class CardDeck:
    id: int
    user_id: int
    name: str
    subject: str
    topic: str
    source_documents: List[int] = field(default_factory=list)
    card_ids: List[int] = field(default_factory=list)


@dataclass
class StudyPlan:
    id: int
    user_id: int
    start_date: dt.date
    end_date: dt.date
    topic_weights: Dict[str, float]
    free_days: List[dt.date] = field(default_factory=list)
    target_cards_per_day: int = 30


@dataclass
class StudySession:
    id: int
    user_id: int
    date: dt.date
    mode: str  # "cards", "audio", "video", "exam"
    cards_seen: int = 0
    cards_correct: int = 0
    cards_incorrect: int = 0
    cards_skipped: int = 0
    time_spent_minutes: int = 0


@dataclass
class UserStats:
    user_id: int
    total_xp: int = 0
    level: int = 1
    current_streak: int = 0
    longest_streak: int = 0
    last_activity_date: Optional[dt.date] = None
    total_cards_learned: int = 0
    total_correct: int = 0
    total_sessions: int = 0
    achievements: List[str] = field(default_factory=list)


@dataclass
class CardNote:
    id: int
    card_id: int
    user_id: int
    note_text: str
    created_at: dt.datetime


@dataclass
class ClozeCard:
    """Lückentext-Karte mit {{c1::verstecktem Text}}"""
    id: int
    deck_id: int
    user_id: int
    subject: str
    cloze_text: str  # "Der {{c1::Bundestag}} wählt den {{c2::Bundeskanzler}}"
    explanation: str = ""
    box: int = 1
    due_date: dt.date = field(default_factory=lambda: dt.date.today())


# ============================================================
# 2. SQLite-Datenbank-Helfer
# ============================================================

DB_PATH = "study_app.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db_schema():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            share_code TEXT,
            is_public INTEGER DEFAULT 0
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            explanation TEXT,
            choices_json TEXT,
            correct_choice_index INTEGER,
            box INTEGER NOT NULL DEFAULT 1,
            due_date TEXT NOT NULL,
            last_reviewed TEXT,
            success_streak INTEGER NOT NULL DEFAULT 0,
            in_special_bucket INTEGER NOT NULL DEFAULT 0,
            tags_json TEXT,
            card_type TEXT DEFAULT 'standard',
            times_correct INTEGER DEFAULT 0,
            times_wrong INTEGER DEFAULT 0,
            FOREIGN KEY(deck_id) REFERENCES decks(id)
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS study_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            topic_weights_json TEXT,
            free_days_json TEXT,
            target_cards_per_day INTEGER NOT NULL
        )
        """)
        # Gamification: User Stats
        c.execute("""
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER PRIMARY KEY,
            total_xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0,
            last_activity_date TEXT,
            total_cards_learned INTEGER DEFAULT 0,
            total_correct INTEGER DEFAULT 0,
            total_sessions INTEGER DEFAULT 0,
            achievements_json TEXT DEFAULT '[]'
        )
        """)
        # Study Sessions für Analytik
        c.execute("""
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            mode TEXT NOT NULL,
            cards_seen INTEGER DEFAULT 0,
            cards_correct INTEGER DEFAULT 0,
            cards_incorrect INTEGER DEFAULT 0,
            cards_skipped INTEGER DEFAULT 0,
            time_spent_minutes INTEGER DEFAULT 0,
            xp_earned INTEGER DEFAULT 0
        )
        """)
        # Notizen zu Karten
        c.execute("""
        CREATE TABLE IF NOT EXISTS card_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            note_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(card_id) REFERENCES cards(id)
        )
        """)
        # Lückentext-Karten (Cloze)
        c.execute("""
        CREATE TABLE IF NOT EXISTS cloze_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            cloze_text TEXT NOT NULL,
            explanation TEXT,
            box INTEGER DEFAULT 1,
            due_date TEXT NOT NULL,
            times_correct INTEGER DEFAULT 0,
            times_wrong INTEGER DEFAULT 0,
            FOREIGN KEY(deck_id) REFERENCES decks(id)
        )
        """)
        # Chat-Verlauf für KI-Tutor
        c.execute("""
        CREATE TABLE IF NOT EXISTS tutor_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            topic TEXT
        )
        """)
        conn.commit()


def row_to_card(row: sqlite3.Row) -> Card:
    return Card(
        id=row["id"],
        deck_id=row["deck_id"],
        user_id=row["user_id"],
        subject=row["subject"],
        question=row["question"],
        answer=row["answer"],
        explanation=row["explanation"] or "",
        choices=json.loads(row["choices_json"]) if row["choices_json"] else None,
        correct_choice_index=row["correct_choice_index"],
        box=row["box"],
        due_date=dt.date.fromisoformat(row["due_date"]),
        last_reviewed=dt.date.fromisoformat(row["last_reviewed"]) if row["last_reviewed"] else None,
        success_streak=row["success_streak"],
        in_special_bucket=bool(row["in_special_bucket"]),
        tags=json.loads(row["tags_json"]) if row["tags_json"] else [],
    )


def db_create_deck(user_id: int, name: str, subject: str, topic: str) -> CardDeck:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO decks (user_id, name, subject, topic) VALUES (?, ?, ?, ?)",
            (user_id, name, subject, topic),
        )
        deck_id = c.lastrowid
        conn.commit()
    return CardDeck(id=deck_id, user_id=user_id, name=name, subject=subject, topic=topic)


def db_get_decks(user_id: int) -> List[CardDeck]:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM decks WHERE user_id=? ORDER BY id DESC", (user_id,))
        rows = c.fetchall()
    decks: List[CardDeck] = []
    for r in rows:
        decks.append(CardDeck(
            id=r["id"],
            user_id=r["user_id"],
            name=r["name"],
            subject=r["subject"],
            topic=r["topic"],
        ))
    return decks


def db_insert_card(card: Card) -> int:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO cards (
                deck_id, user_id, subject, question, answer, explanation,
                choices_json, correct_choice_index, box, due_date,
                last_reviewed, success_streak, in_special_bucket, tags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            card.deck_id,
            card.user_id,
            card.subject,
            card.question,
            card.answer,
            card.explanation,
            json.dumps(card.choices) if card.choices is not None else None,
            card.correct_choice_index,
            card.box,
            card.due_date.isoformat(),
            card.last_reviewed.isoformat() if card.last_reviewed else None,
            card.success_streak,
            1 if card.in_special_bucket else 0,
            json.dumps(card.tags) if card.tags else None,
        ))
        card_id = c.lastrowid
        conn.commit()
    return card_id


def db_get_cards_by_deck(deck_id: int, user_id: int) -> List[Card]:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM cards WHERE deck_id=? AND user_id=? ORDER BY id",
            (deck_id, user_id),
        )
        rows = c.fetchall()
    return [row_to_card(r) for r in rows]


def db_get_all_cards(user_id: int) -> List[Card]:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM cards WHERE user_id=?", (user_id,))
        rows = c.fetchall()
    return [row_to_card(r) for r in rows]


def db_update_card_spaced(card: Card):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE cards
            SET box=?, due_date=?, last_reviewed=?, success_streak=?, in_special_bucket=?
            WHERE id=?
        """, (
            card.box,
            card.due_date.isoformat(),
            card.last_reviewed.isoformat() if card.last_reviewed else None,
            card.success_streak,
            1 if card.in_special_bucket else 0,
            card.id,
        ))
        conn.commit()


def db_select_next_due_cards(user_id: int, deck_id: Optional[int], max_cards: int, include_special_bucket: bool) -> List[Card]:
    today_str = dt.date.today().isoformat()
    cards: List[Card] = []
    seen_ids = set()

    with get_db_connection() as conn:
        c = conn.cursor()

        params = [user_id]
        deck_filter = ""
        if deck_id is not None:
            deck_filter = " AND deck_id=?"
            params.append(deck_id)

        if include_special_bucket:
            c.execute(
                f"SELECT * FROM cards WHERE user_id=?{deck_filter} AND in_special_bucket=1 ORDER BY due_date ASC, id ASC",
                params,
            )
            for row in c.fetchall():
                card = row_to_card(row)
                cards.append(card)
                seen_ids.add(card.id)

        c.execute(
            f"""
            SELECT * FROM cards
            WHERE user_id=?{deck_filter}
              AND in_special_bucket=0
              AND due_date<=?
            ORDER BY due_date ASC, id ASC
            """,
            params + [today_str],
        )
        for row in c.fetchall():
            card = row_to_card(row)
            if card.id not in seen_ids:
                cards.append(card)
                seen_ids.add(card.id)

    return cards[:max_cards]


def get_or_create_study_plan(user_id: int) -> StudyPlan:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM study_plan WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row:
            plan = StudyPlan(
                id=row["id"],
                user_id=row["user_id"],
                start_date=dt.date.fromisoformat(row["start_date"]),
                end_date=dt.date.fromisoformat(row["end_date"]),
                topic_weights=json.loads(row["topic_weights_json"]) if row["topic_weights_json"] else {},
                free_days=[dt.date.fromisoformat(d) for d in json.loads(row["free_days_json"])] if row["free_days_json"] else [],
                target_cards_per_day=row["target_cards_per_day"],
            )
            return plan
        else:
            today = dt.date.today()
            plan = StudyPlan(
                id=0,
                user_id=user_id,
                start_date=today,
                end_date=today + dt.timedelta(days=90),
                topic_weights={},
                free_days=[],
                target_cards_per_day=30,
            )
            c.execute(
                """
                INSERT INTO study_plan (user_id, start_date, end_date, topic_weights_json, free_days_json, target_cards_per_day)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    plan.start_date.isoformat(),
                    plan.end_date.isoformat(),
                    json.dumps(plan.topic_weights),
                    json.dumps([d.isoformat() for d in plan.free_days]),
                    plan.target_cards_per_day,
                ),
            )
            plan.id = c.lastrowid
            conn.commit()
            return plan


def db_update_study_plan(plan: StudyPlan):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE study_plan
            SET start_date=?, end_date=?, topic_weights_json=?, free_days_json=?, target_cards_per_day=?
            WHERE id=?
            """,
            (
                plan.start_date.isoformat(),
                plan.end_date.isoformat(),
                json.dumps(plan.topic_weights),
                json.dumps([d.isoformat() for d in plan.free_days]),
                plan.target_cards_per_day,
                plan.id,
            ),
        )
        conn.commit()


# ============================================================
# 2b. Gamification & Analytics Datenbank-Funktionen
# ============================================================

def get_or_create_user_stats(user_id: int) -> UserStats:
    """Holt oder erstellt User-Statistiken für Gamification."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM user_stats WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row:
            return UserStats(
                user_id=row["user_id"],
                total_xp=row["total_xp"],
                level=row["level"],
                current_streak=row["current_streak"],
                longest_streak=row["longest_streak"],
                last_activity_date=dt.date.fromisoformat(row["last_activity_date"]) if row["last_activity_date"] else None,
                total_cards_learned=row["total_cards_learned"],
                total_correct=row["total_correct"],
                total_sessions=row["total_sessions"],
                achievements=json.loads(row["achievements_json"]) if row["achievements_json"] else [],
            )
        else:
            c.execute(
                "INSERT INTO user_stats (user_id) VALUES (?)",
                (user_id,)
            )
            conn.commit()
            return UserStats(user_id=user_id)


def db_update_user_stats(stats: UserStats):
    """Speichert aktualisierte User-Statistiken."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE user_stats SET
                total_xp=?, level=?, current_streak=?, longest_streak=?,
                last_activity_date=?, total_cards_learned=?, total_correct=?,
                total_sessions=?, achievements_json=?
            WHERE user_id=?
        """, (
            stats.total_xp, stats.level, stats.current_streak, stats.longest_streak,
            stats.last_activity_date.isoformat() if stats.last_activity_date else None,
            stats.total_cards_learned, stats.total_correct, stats.total_sessions,
            json.dumps(stats.achievements), stats.user_id
        ))
        conn.commit()


def calculate_level(xp: int) -> int:
    """Berechnet das Level basierend auf XP."""
    for i, required_xp in enumerate(LEVEL_XP_REQUIREMENTS):
        if xp < required_xp:
            return max(1, i)
    return len(LEVEL_XP_REQUIREMENTS)


def get_xp_for_next_level(current_xp: int) -> Tuple[int, int]:
    """Gibt (XP für aktuelles Level, XP für nächstes Level) zurück."""
    level = calculate_level(current_xp)
    current_level_xp = LEVEL_XP_REQUIREMENTS[level - 1] if level > 0 else 0
    next_level_xp = LEVEL_XP_REQUIREMENTS[level] if level < len(LEVEL_XP_REQUIREMENTS) else current_xp
    return current_level_xp, next_level_xp


def update_streak(stats: UserStats) -> bool:
    """Aktualisiert den Streak und gibt True zurück wenn neuer Tag."""
    today = dt.date.today()
    if stats.last_activity_date is None:
        stats.current_streak = 1
        stats.last_activity_date = today
        return True

    days_diff = (today - stats.last_activity_date).days

    if days_diff == 0:
        return False  # Gleicher Tag
    elif days_diff == 1:
        stats.current_streak += 1
        stats.last_activity_date = today
        if stats.current_streak > stats.longest_streak:
            stats.longest_streak = stats.current_streak
        return True
    else:
        stats.current_streak = 1
        stats.last_activity_date = today
        return True


def check_and_award_achievements(stats: UserStats) -> List[str]:
    """Prüft und vergibt neue Achievements. Gibt Liste neuer Achievements zurück."""
    new_achievements = []

    # Erste Karte
    if "first_card" not in stats.achievements and stats.total_cards_learned >= 1:
        stats.achievements.append("first_card")
        new_achievements.append("first_card")

    # Streak Achievements
    if "streak_3" not in stats.achievements and stats.current_streak >= 3:
        stats.achievements.append("streak_3")
        new_achievements.append("streak_3")
    if "streak_7" not in stats.achievements and stats.current_streak >= 7:
        stats.achievements.append("streak_7")
        new_achievements.append("streak_7")
    if "streak_30" not in stats.achievements and stats.current_streak >= 30:
        stats.achievements.append("streak_30")
        new_achievements.append("streak_30")

    # Karten-Meilensteine
    if "cards_50" not in stats.achievements and stats.total_cards_learned >= 50:
        stats.achievements.append("cards_50")
        new_achievements.append("cards_50")
    if "cards_100" not in stats.achievements and stats.total_cards_learned >= 100:
        stats.achievements.append("cards_100")
        new_achievements.append("cards_100")
    if "cards_500" not in stats.achievements and stats.total_cards_learned >= 500:
        stats.achievements.append("cards_500")
        new_achievements.append("cards_500")

    # Zeit-basierte Achievements
    current_hour = dt.datetime.now().hour
    if "night_owl" not in stats.achievements and current_hour >= 22:
        stats.achievements.append("night_owl")
        new_achievements.append("night_owl")
    if "early_bird" not in stats.achievements and current_hour < 7:
        stats.achievements.append("early_bird")
        new_achievements.append("early_bird")

    # XP für neue Achievements hinzufügen
    for ach_id in new_achievements:
        stats.total_xp += ACHIEVEMENTS[ach_id]["xp"]

    return new_achievements


def award_xp(stats: UserStats, xp_amount: int, result: str = "correct"):
    """Vergibt XP und aktualisiert Level."""
    bonus = stats.current_streak * XP_STREAK_BONUS if stats.current_streak > 1 else 0
    total_xp = xp_amount + bonus
    stats.total_xp += total_xp
    stats.level = calculate_level(stats.total_xp)
    return total_xp


def db_save_study_session(user_id: int, mode: str, cards_seen: int, cards_correct: int,
                          cards_incorrect: int, cards_skipped: int, time_minutes: int, xp_earned: int):
    """Speichert eine Lernsession in der Datenbank."""
    with get_db_connection() as conn:
        c = conn.cursor()
        now = dt.datetime.now()
        c.execute("""
            INSERT INTO study_sessions
            (user_id, date, start_time, mode, cards_seen, cards_correct, cards_incorrect, cards_skipped, time_spent_minutes, xp_earned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, now.date().isoformat(), now.isoformat(), mode,
            cards_seen, cards_correct, cards_incorrect, cards_skipped, time_minutes, xp_earned
        ))
        conn.commit()


def db_get_study_sessions(user_id: int, days: int = 30) -> List[Dict]:
    """Holt Lernsessions der letzten X Tage."""
    with get_db_connection() as conn:
        c = conn.cursor()
        cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        c.execute("""
            SELECT * FROM study_sessions
            WHERE user_id=? AND date >= ?
            ORDER BY date DESC
        """, (user_id, cutoff))
        return [dict(row) for row in c.fetchall()]


def db_get_activity_heatmap(user_id: int, days: int = 365) -> Dict[str, int]:
    """Holt Aktivitätsdaten für Heatmap (Datum -> Anzahl Karten)."""
    with get_db_connection() as conn:
        c = conn.cursor()
        cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        c.execute("""
            SELECT date, SUM(cards_seen) as total
            FROM study_sessions
            WHERE user_id=? AND date >= ?
            GROUP BY date
        """, (user_id, cutoff))
        return {row["date"]: row["total"] for row in c.fetchall()}


def db_get_weakness_analysis(user_id: int) -> List[Dict]:
    """Analysiert Schwächen basierend auf Fehlerquote pro Thema."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT subject,
                   COUNT(*) as total,
                   SUM(times_wrong) as wrong,
                   SUM(times_correct) as correct,
                   AVG(CASE WHEN times_correct + times_wrong > 0
                       THEN CAST(times_wrong AS FLOAT) / (times_correct + times_wrong)
                       ELSE 0 END) as error_rate
            FROM cards
            WHERE user_id=? AND (times_correct > 0 OR times_wrong > 0)
            GROUP BY subject
            ORDER BY error_rate DESC
        """, (user_id,))
        return [dict(row) for row in c.fetchall()]


def db_get_best_study_times(user_id: int) -> Dict[int, float]:
    """Analysiert die besten Lernzeiten basierend auf Erfolgsquote."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT start_time, cards_correct, cards_seen
            FROM study_sessions
            WHERE user_id=? AND cards_seen > 0
        """, (user_id,))

        hour_stats = defaultdict(lambda: {"correct": 0, "total": 0})
        for row in c.fetchall():
            if row["start_time"]:
                hour = dt.datetime.fromisoformat(row["start_time"]).hour
                hour_stats[hour]["correct"] += row["cards_correct"]
                hour_stats[hour]["total"] += row["cards_seen"]

        return {
            hour: stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            for hour, stats in hour_stats.items()
        }


# ============================================================
# 2c. Notizen & Chat Funktionen
# ============================================================

def db_save_card_note(card_id: int, user_id: int, note_text: str):
    """Speichert eine Notiz zu einer Karte."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO card_notes (card_id, user_id, note_text, created_at)
            VALUES (?, ?, ?, ?)
        """, (card_id, user_id, note_text, dt.datetime.now().isoformat()))
        conn.commit()


def db_get_card_notes(card_id: int, user_id: int) -> List[CardNote]:
    """Holt alle Notizen zu einer Karte."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT * FROM card_notes WHERE card_id=? AND user_id=?
            ORDER BY created_at DESC
        """, (card_id, user_id))
        return [CardNote(
            id=row["id"],
            card_id=row["card_id"],
            user_id=row["user_id"],
            note_text=row["note_text"],
            created_at=dt.datetime.fromisoformat(row["created_at"])
        ) for row in c.fetchall()]


def db_save_tutor_message(user_id: int, role: str, content: str, topic: str = None):
    """Speichert eine Chat-Nachricht mit dem KI-Tutor."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO tutor_chat (user_id, role, content, timestamp, topic)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, role, content, dt.datetime.now().isoformat(), topic))
        conn.commit()


def db_get_tutor_chat(user_id: int, limit: int = 20) -> List[Dict]:
    """Holt die letzten Chat-Nachrichten."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT * FROM tutor_chat WHERE user_id=?
            ORDER BY timestamp DESC LIMIT ?
        """, (user_id, limit))
        return [dict(row) for row in c.fetchall()][::-1]  # Umkehren für chronologische Reihenfolge


def db_clear_tutor_chat(user_id: int):
    """Löscht den Chat-Verlauf."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM tutor_chat WHERE user_id=?", (user_id,))
        conn.commit()


# ============================================================
# 2d. Import/Export Funktionen
# ============================================================

def export_deck_to_json(deck_id: int, user_id: int) -> str:
    """Exportiert ein Deck als JSON."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM decks WHERE id=? AND user_id=?", (deck_id, user_id))
        deck_row = c.fetchone()
        if not deck_row:
            return None

        c.execute("SELECT * FROM cards WHERE deck_id=? AND user_id=?", (deck_id, user_id))
        cards = [dict(row) for row in c.fetchall()]

        export_data = {
            "version": "1.0",
            "deck": {
                "name": deck_row["name"],
                "subject": deck_row["subject"],
                "topic": deck_row["topic"]
            },
            "cards": [{
                "question": card["question"],
                "answer": card["answer"],
                "explanation": card["explanation"],
                "choices": json.loads(card["choices_json"]) if card["choices_json"] else None,
                "correct_choice_index": card["correct_choice_index"],
                "tags": json.loads(card["tags_json"]) if card["tags_json"] else []
            } for card in cards]
        }
        return json.dumps(export_data, ensure_ascii=False, indent=2)


def export_deck_to_csv(deck_id: int, user_id: int) -> str:
    """Exportiert ein Deck als CSV."""
    cards = db_get_cards_by_deck(deck_id, user_id)
    lines = ["Frage;Antwort;Erklärung;Tags"]
    for card in cards:
        tags = ",".join(card.tags) if card.tags else ""
        line = f'"{card.question}";"{card.answer}";"{card.explanation}";"{tags}"'
        lines.append(line)
    return "\n".join(lines)


def import_deck_from_json(json_str: str, user_id: int) -> Tuple[bool, str]:
    """Importiert ein Deck aus JSON. Gibt (Erfolg, Nachricht) zurück."""
    try:
        data = json.loads(json_str)
        deck_info = data.get("deck", {})
        cards_data = data.get("cards", [])

        if not deck_info or not cards_data:
            return False, "Ungültiges JSON-Format"

        deck = db_create_deck(
            user_id,
            deck_info.get("name", "Importiertes Deck"),
            deck_info.get("subject", "Andere"),
            deck_info.get("topic", "Import")
        )

        for card_data in cards_data:
            card = Card(
                id=0,
                deck_id=deck.id,
                user_id=user_id,
                subject=deck_info.get("subject", "Andere"),
                question=card_data.get("question", ""),
                answer=card_data.get("answer", ""),
                explanation=card_data.get("explanation", ""),
                choices=card_data.get("choices"),
                correct_choice_index=card_data.get("correct_choice_index"),
                tags=card_data.get("tags", [])
            )
            db_insert_card(card)

        return True, f"Deck '{deck.name}' mit {len(cards_data)} Karten importiert!"
    except Exception as e:
        return False, f"Import-Fehler: {str(e)}"


def generate_share_code(deck_id: int) -> str:
    """Generiert einen eindeutigen Share-Code für ein Deck."""
    code = hashlib.md5(f"{deck_id}-{dt.datetime.now().isoformat()}".encode()).hexdigest()[:8].upper()
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE decks SET share_code=? WHERE id=?", (code, deck_id))
        conn.commit()
    return code


def import_deck_by_share_code(share_code: str, user_id: int) -> Tuple[bool, str]:
    """Importiert ein Deck über einen Share-Code."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM decks WHERE share_code=?", (share_code,))
        source_deck = c.fetchone()

        if not source_deck:
            return False, "Share-Code nicht gefunden."

        # Deck und Karten kopieren
        new_deck = db_create_deck(
            user_id,
            f"{source_deck['name']} (kopiert)",
            source_deck["subject"],
            source_deck["topic"]
        )

        c.execute("SELECT * FROM cards WHERE deck_id=?", (source_deck["id"],))
        cards = c.fetchall()

        for card_row in cards:
            card = Card(
                id=0,
                deck_id=new_deck.id,
                user_id=user_id,
                subject=card_row["subject"],
                question=card_row["question"],
                answer=card_row["answer"],
                explanation=card_row["explanation"] or "",
                choices=json.loads(card_row["choices_json"]) if card_row["choices_json"] else None,
                correct_choice_index=card_row["correct_choice_index"]
            )
            db_insert_card(card)

        return True, f"Deck '{new_deck.name}' mit {len(cards)} Karten importiert!"


# ============================================================
# 2e. Cloze (Lückentext) Funktionen
# ============================================================

def parse_cloze_text(cloze_text: str) -> List[Tuple[str, str]]:
    """Parst Lückentext und gibt [(id, versteckter_text), ...] zurück."""
    pattern = r'\{\{c(\d+)::([^}]+)\}\}'
    return re.findall(pattern, cloze_text)


def render_cloze_with_blanks(cloze_text: str, reveal_ids: List[str] = None) -> str:
    """Rendert Lückentext mit Lücken oder aufgedeckten Antworten."""
    if reveal_ids is None:
        reveal_ids = []

    def replace_cloze(match):
        cloze_id = match.group(1)
        cloze_content = match.group(2)
        if cloze_id in reveal_ids:
            return f'<span style="background-color:#90EE90;padding:2px 6px;border-radius:4px;">{cloze_content}</span>'
        else:
            return f'<span class="cloze-blank">[...]</span>'

    return re.sub(r'\{\{c(\d+)::([^}]+)\}\}', replace_cloze, cloze_text)


def db_insert_cloze_card(deck_id: int, user_id: int, subject: str, cloze_text: str, explanation: str = "") -> int:
    """Fügt eine Lückentext-Karte hinzu."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO cloze_cards (deck_id, user_id, subject, cloze_text, explanation, due_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (deck_id, user_id, subject, cloze_text, explanation, dt.date.today().isoformat()))
        conn.commit()
        return c.lastrowid


def db_get_cloze_cards(deck_id: int, user_id: int) -> List[Dict]:
    """Holt alle Lückentext-Karten eines Decks."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM cloze_cards WHERE deck_id=? AND user_id=?", (deck_id, user_id))
        return [dict(row) for row in c.fetchall()]


# ============================================================
# 3. Session-State Initialisierung (User & KI)
# ============================================================

def init_state():
    if "user_id" not in st.session_state:
        st.session_state.user_id = 1  # Dummy-User
    if "study_plan" not in st.session_state:
        st.session_state.study_plan = None


def init_llm_state():
    if "llm_provider" not in st.session_state:
        st.session_state.llm_provider = "openai"  # "openai" oder "anthropic"
    if "openai_api_key" not in st.session_state:
        # Aus .env vorbelegen, kann im UI überschrieben werden
        st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
    if "anthropic_api_key" not in st.session_state:
        st.session_state.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if "llm_connection_status" not in st.session_state:
        st.session_state.llm_connection_status = None
    if "current_cards" not in st.session_state:
        st.session_state.current_cards: List[Card] = []
    if "current_card_index" not in st.session_state:
        st.session_state.current_card_index = 0
    if "current_exam" not in st.session_state:
        st.session_state.current_exam = None
    if "study_answer_mode" not in st.session_state:
        st.session_state.study_answer_mode = "Freitext"  # "Freitext" oder "Multiple Choice"


def init_gamification_state():
    """Initialisiert Gamification-bezogene Session States."""
    if "user_stats" not in st.session_state:
        st.session_state.user_stats = None
    if "session_xp_earned" not in st.session_state:
        st.session_state.session_xp_earned = 0
    if "session_cards_correct" not in st.session_state:
        st.session_state.session_cards_correct = 0
    if "session_cards_wrong" not in st.session_state:
        st.session_state.session_cards_wrong = 0
    if "new_achievements" not in st.session_state:
        st.session_state.new_achievements = []


def init_pomodoro_state():
    """Initialisiert Pomodoro-Timer Session States."""
    if "pomodoro_running" not in st.session_state:
        st.session_state.pomodoro_running = False
    if "pomodoro_start_time" not in st.session_state:
        st.session_state.pomodoro_start_time = None
    if "pomodoro_duration" not in st.session_state:
        st.session_state.pomodoro_duration = 25  # Minuten
    if "pomodoro_break" not in st.session_state:
        st.session_state.pomodoro_break = False
    if "pomodoro_sessions_completed" not in st.session_state:
        st.session_state.pomodoro_sessions_completed = 0


def init_tutor_state():
    """Initialisiert KI-Tutor Session States."""
    if "tutor_messages" not in st.session_state:
        st.session_state.tutor_messages = []
    if "tutor_topic" not in st.session_state:
        st.session_state.tutor_topic = None


init_db_schema()
init_state()
init_llm_state()
init_gamification_state()
init_pomodoro_state()
init_tutor_state()

# Study-Plan aus DB holen (oder anlegen)
st.session_state.study_plan = get_or_create_study_plan(st.session_state.user_id)
# User-Stats für Gamification laden
st.session_state.user_stats = get_or_create_user_stats(st.session_state.user_id)


# ============================================================
# 4. KI-Client & Verbindungstest
# ============================================================

def get_llm_client():
    provider = st.session_state.llm_provider

    if provider == "openai":
        api_key = st.session_state.openai_api_key.strip()
        if not api_key:
            raise ValueError("Kein OpenAI-API-Key hinterlegt.")
        client = OpenAI(api_key=api_key)
        return client, "openai"

    elif provider == "anthropic":
        api_key = st.session_state.anthropic_api_key.strip()
        if not api_key:
            raise ValueError("Kein Anthropic-API-Key hinterlegt.")
        client = Anthropic(api_key=api_key)
        return client, "anthropic"

    else:
        raise ValueError(f"Unbekannter Provider: {provider}")


def test_llm_connection():
    """
    Mini-Anfrage an den gewählten Provider, setzt llm_connection_status.
    """
    try:
        client, provider = get_llm_client()

        if provider == "openai":
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Du bist ein Kurzbefehlstester."},
                    {"role": "user", "content": "Antworte nur mit: OK"}
                ],
                max_tokens=5,
            )
            text = resp.choices[0].message.content.strip()
        else:
            resp = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=16,
                messages=[
                    {"role": "user", "content": "Antworte nur mit: OK"}
                ],
            )
            text = resp.content[0].text.strip()

        if "OK" in text.upper():
            st.session_state.llm_connection_status = "ok"
            st.success(f"✅ KI-Verbindung ({provider}) erfolgreich hergestellt.")
        else:
            st.session_state.llm_connection_status = "Antwort unerwartet"
            st.warning("Verbindung hergestellt, aber Antwort unerwartet. Prüfe Modell/Prompt.")

    except Exception as e:
        st.session_state.llm_connection_status = str(e)
        st.error(f"❌ Fehler bei der KI-Verbindung: {e}")


class LLMError(Exception):
    """Custom exception for LLM API errors with user-friendly messages."""
    pass


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    Zentrale Stelle für alle LLM-Aufrufe mit umfassendem Error-Handling.
    """
    try:
        client, provider = get_llm_client()
    except ValueError as e:
        raise LLMError(f"Konfigurationsfehler: {e}")

    try:
        if provider == "openai":
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            return resp.choices[0].message.content

        else:  # anthropic
            resp = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=4096,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt},
                ],
            )
            return resp.content[0].text

    except OpenAIRateLimitError:
        raise LLMError(
            "OpenAI Rate-Limit erreicht. Moegliche Ursachen:\n"
            "- Kein Guthaben auf dem OpenAI-Account\n"
            "- Zu viele Anfragen in kurzer Zeit\n\n"
            "Loesungen:\n"
            "1. Guthaben pruefen: https://platform.openai.com/usage\n"
            "2. Zahlungsmethode hinzufuegen\n"
            "3. Alternativ zu Claude (Anthropic) wechseln"
        )
    except OpenAIAPIError as e:
        raise LLMError(f"OpenAI API-Fehler: {e}")
    except AnthropicRateLimitError:
        raise LLMError(
            "Anthropic Rate-Limit erreicht. Moegliche Ursachen:\n"
            "- Kein Guthaben auf dem Anthropic-Account\n"
            "- Zu viele Anfragen in kurzer Zeit\n\n"
            "Loesungen:\n"
            "1. Guthaben pruefen: https://console.anthropic.com/\n"
            "2. Alternativ zu OpenAI wechseln"
        )
    except AnthropicAPIError as e:
        raise LLMError(f"Anthropic API-Fehler: {e}")
    except Exception as e:
        raise LLMError(f"Unerwarteter Fehler bei der KI-Anfrage: {e}")


# ============================================================
# 5. Prompt-Konstanten (System- & User-Prompts)
# ============================================================

FLASHCARD_SYSTEM_PROMPT = """
Du bist ein hochspezialisierter KI-Tutor, der aus Fachtexten didaktisch hochwertige Karteikarten erzeugt.

Ziele:
- Erzeuge präzise, prüfungsrelevante Lernkarten.
- Formuliere kurz, klar und fachlich korrekt.
- Baue Verständnisfragen ein, nicht nur reine Wissensabfragen.
- Nutze konsequent die Terminologie des jeweiligen Fachgebiets.

Format:
- Du antwortest ausschließlich mit einem JSON-Array.
- Jedes Element ist ein Objekt mit den Schlüsseln "question", "answer", "explanation",
  "choices" (oder null) und "correct_choice_index" (oder null).
- Kein anderer Text außerhalb dieses JSON-Arrays.
""".strip()

JURA_FLASHCARD_USER_PROMPT = """
FACH: Rechtswissenschaften
SCHWERPUNKT: {topic}
NIVEAU: {difficulty}

AUFGABE:
Erzeuge aus dem folgenden juristischen Fachtext hochwertige Karteikarten für Jurastudierende.

TEXT:
{text}

Didaktische Anforderungen:
- Definitionen, Schemata, Mini-Fälle, Abgrenzungen und Klausurtaktik mischen.
- Schwierigkeitsgrad an {difficulty} anpassen.
- Multiple Choice nur mit sinnvollen Distraktoren (4 Optionen, 1 richtig), sonst Freitextkarten.

Rückgabe:
Nur das JSON-Array der Karten gemäß System-Anweisung.
""".strip()

MED_FLASHCARD_USER_PROMPT = """
FACH: Medizin
SCHWERPUNKT: {topic}
NIVEAU: {difficulty}

AUFGABE:
Erzeuge aus dem folgenden medizinischen Fachtext hochwertige Karteikarten für Medizinstudierende.

TEXT:
{text}

Didaktische Anforderungen:
- Leitsymptome, Pathophysiologie, Diagnostik, TherapiePRINZIPIEN und Komplikationen.
- Keine Dosierungen oder individuellen Therapiepläne.
- Multiple Choice vor allem bei Diagnosen/DD (4 Optionen, 1 richtig).

Rückgabe:
Nur das JSON-Array der Karten gemäß System-Anweisung.
""".strip()

GENERIC_FLASHCARD_USER_PROMPT = """
FACH: {subject}
SCHWERPUNKT / THEMA: {topic}
NIVEAU: {difficulty}

AUFGABE:
Erzeuge aus dem folgenden Fachtext hochwertige Karteikarten für Studierende.

TEXT:
{text}

Didaktische Anforderungen:
- Zentrale Begriffe, Konzepte, Algorithmen, Formeln, Anwendungsfälle.
- Mischung aus Definitions-, Konzept-, Anwendungs- und Vergleichskarten.
- Schwierigkeitsgrad an {difficulty} anpassen.

Rückgabe:
Nur das JSON-Array der Karten gemäß System-Anweisung.
""".strip()

SYSTEM_JURA_EVAL = """
Du bist ein erfahrener juristischer Korrektor.

Aufgabe:
- Bewerte die Freitextantwort eines Studierenden auf eine Lernkarte als "correct", "partial" oder "wrong".

Ausgabe:
- JSON-Objekt mit "grade" und "explanation".
""".strip()

USER_JURA_EVAL = """
FACH: Rechtswissenschaften
THEMA: {topic}

FRAGE:
{card_question}

MUSTERLÖSUNG:
{card_answer}

ERWEITERTE ERKLÄRUNG:
{card_explanation}

ANTWORT DES STUDIERENDEN:
{user_answer}

Bitte:
- Ordne in "correct", "partial" oder "wrong" ein.
- Erkläre kurz warum.
- Gib in der Erklärung eine knappe Musterlösung.

Rückgabe:
Nur JSON mit "grade" und "explanation".
""".strip()

SYSTEM_MED_EVAL = """
Du bist ein erfahrener medizinischer Prüfer.

Aufgabe:
- Bewerte eine Freitextantwort eines Medizinstudierenden als "correct", "partial" oder "wrong".

Ausgabe:
- JSON-Objekt mit "grade" und "explanation".
""".strip()

USER_MED_EVAL = """
FACH: Medizin
THEMA: {topic}

FRAGE:
{card_question}

MUSTERLÖSUNG:
{card_answer}

ERWEITERTE ERKLÄRUNG:
{card_explanation}

ANTWORT DES STUDIERENDEN:
{user_answer}

Bitte:
- Ordne in "correct", "partial" oder "wrong" ein.
- Erkläre kurz warum.
- Fasse die korrekte Kernaussage knapp zusammen.

Rückgabe:
Nur JSON mit "grade" und "explanation".
""".strip()

SYSTEM_GENERIC_EVAL = """
Du bist ein fachkundiger Prüfer und bewertest Freitextantworten.

Ausgabe:
- JSON-Objekt mit "grade" ("correct", "partial", "wrong") und "explanation".
""".strip()

USER_GENERIC_EVAL = """
FACH: {subject}
THEMA: {topic}

FRAGE:
{card_question}

MUSTERLÖSUNG:
{card_answer}

ERWEITERTE ERKLÄRUNG:
{card_explanation}

ANTWORT DES STUDIERENDEN:
{user_answer}

Bitte:
- Bewerte die Antwort als "correct", "partial" oder "wrong".
- Begründe kurz.
- Gib eine kurze Musterlösung in der Erklärung.

Rückgabe:
Nur JSON mit "grade" und "explanation".
""".strip()

SYSTEM_JURA_EXAM = """
Du bist Prüfer im Fach Rechtswissenschaften und erstellst realistische fallbasierte Prüfungssimulationen.

Format:
- JSON-Objekt mit "questions": Liste von Fragenobjekten mit "prompt", "sub_prompts", "difficulty", "estimated_time_minutes".
- Keine Lösungen ausgeben.
""".strip()

USER_JURA_EXAM = """
FACH: Rechtswissenschaften
SCHWERPUNKT: {topic}
NIVEAU: {level}
DAUER: {duration_minutes} Minuten
MODUS: {mode}

Erzeuge eine juristische Prüfungssimulation mit mindestens einem Fall und mehreren Teilfragen (sub_prompts).

Rückgabe:
Nur JSON mit "questions".
""".strip()

SYSTEM_MED_EXAM = """
Du bist Prüfer im Fach Medizin und erstellst klinische Prüfungssimulationen.

Format:
- JSON-Objekt mit "questions": Liste von Fragenobjekten mit "prompt", "sub_prompts", "difficulty", "estimated_time_minutes".
- Keine Lösungen.
""".strip()

USER_MED_EXAM = """
FACH: Medizin
SCHWERPUNKT: {topic}
NIVEAU: {level}
DAUER: {duration_minutes} Minuten
MODUS: {mode}

Erzeuge eine klinische Prüfungssimulation (Fallvignetten + Teilfragen).

Rückgabe:
Nur JSON mit "questions".
""".strip()

SYSTEM_GENERIC_EXAM = """
Du bist Prüfer und erstellst realistische Klausuraufgaben zu einem Fachthema.

Ausgabe:
- JSON mit "questions": Liste von Aufgaben.
""".strip()

USER_GENERIC_EXAM = """
FACH: {subject}
SCHWERPUNKT: {topic}
NIVEAU: {level}
DAUER: {duration_minutes} Minuten
MODUS: {mode}

Erzeuge eine Prüfungssimulation mit mehreren Aufgaben und Teilfragen.

Rückgabe:
Nur JSON mit "questions".
""".strip()


# ============================================================
# 6. KI-Funktionen (Karten, Bewertung, Exam)
# ============================================================

def extract_json_from_response(raw: str) -> Any:
    """
    Extrahiert JSON aus einer KI-Antwort, auch wenn diese in Markdown
    Code-Bloecken oder mit zusaetzlichem Text umgeben ist.
    """
    if not raw or not raw.strip():
        raise ValueError("Leere Antwort von der KI erhalten.")

    text = raw.strip()

    # Versuch 1: Direktes Parsen
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Versuch 2: JSON aus Markdown Code-Block extrahieren (```json ... ```)
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Versuch 3: JSON-Array finden ([...])
    array_match = re.search(r'\[[\s\S]*\]', text)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass

    # Versuch 4: JSON-Objekt finden ({...})
    obj_match = re.search(r'\{[\s\S]*\}', text)
    if obj_match:
        try:
            return json.loads(obj_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Kein gueltiges JSON in der Antwort gefunden. Antwort beginnt mit: {text[:100]}...")


def llm_generate_flashcards(text: str, subject: str, topic: str, difficulty: str) -> List[Dict[str, Any]]:
    if subject == "Rechtswissenschaften":
        user_prompt = JURA_FLASHCARD_USER_PROMPT.format(
            topic=topic,
            difficulty=difficulty,
            text=text,
        )
    elif subject == "Medizin":
        user_prompt = MED_FLASHCARD_USER_PROMPT.format(
            topic=topic,
            difficulty=difficulty,
            text=text,
        )
    else:
        user_prompt = GENERIC_FLASHCARD_USER_PROMPT.format(
            subject=subject,
            topic=topic,
            difficulty=difficulty,
            text=text,
        )

    try:
        raw = call_llm(FLASHCARD_SYSTEM_PROMPT, user_prompt)
    except LLMError as e:
        st.error(f"KI-Fehler: {e}")
        return []

    try:
        cards = extract_json_from_response(raw)
        if not isinstance(cards, list):
            raise ValueError("Antwort ist kein JSON-Array.")
        return cards
    except ValueError as e:
        st.error(f"Fehler beim Parsen der Karten-Antwort: {e}")
        if raw:
            with st.expander("Rohantwort der KI anzeigen"):
                st.code(raw)
        return []


def llm_evaluate_free_text_answer(user_answer: str, card: Card) -> Dict[str, Any]:
    subject = card.subject or "Allgemein"
    topic = ", ".join(card.tags) if card.tags else card.subject

    if subject == "Rechtswissenschaften":
        system_prompt = SYSTEM_JURA_EVAL
        user_prompt = USER_JURA_EVAL.format(
            topic=topic,
            card_question=card.question,
            card_answer=card.answer,
            card_explanation=card.explanation,
            user_answer=user_answer,
        )
    elif subject == "Medizin":
        system_prompt = SYSTEM_MED_EVAL
        user_prompt = USER_MED_EVAL.format(
            topic=topic,
            card_question=card.question,
            card_answer=card.answer,
            card_explanation=card.explanation,
            user_answer=user_answer,
        )
    else:
        system_prompt = SYSTEM_GENERIC_EVAL
        user_prompt = USER_GENERIC_EVAL.format(
            subject=subject,
            topic=topic,
            card_question=card.question,
            card_answer=card.answer,
            card_explanation=card.explanation,
            user_answer=user_answer,
        )

    try:
        raw = call_llm(system_prompt, user_prompt)
    except LLMError as e:
        st.error(f"KI-Fehler: {e}")
        return {
            "grade": "partial",
            "explanation": "KI-Fehler bei der Auswertung. Antwort wird als 'teilweise richtig' behandelt."
        }

    try:
        result = extract_json_from_response(raw)
        if not isinstance(result, dict):
            raise ValueError("Antwort ist kein JSON-Objekt.")
        return result
    except ValueError as e:
        st.error(f"Fehler beim Parsen der Bewertungs-Antwort: {e}")
        return {
            "grade": "partial",
            "explanation": "Fehler bei der KI-Auswertung. Antwort wird als 'teilweise richtig' behandelt."
        }


def llm_generate_exam(subject: str, topic: str, duration_minutes: int, level: str, mode: str) -> Dict[str, Any]:
    if subject == "Rechtswissenschaften":
        system_prompt = SYSTEM_JURA_EXAM
        user_prompt = USER_JURA_EXAM.format(
            topic=topic,
            level=level,
            duration_minutes=duration_minutes,
            mode=mode,
        )
    elif subject == "Medizin":
        system_prompt = SYSTEM_MED_EXAM
        user_prompt = USER_MED_EXAM.format(
            topic=topic,
            level=level,
            duration_minutes=duration_minutes,
            mode=mode,
        )
    else:
        system_prompt = SYSTEM_GENERIC_EXAM
        user_prompt = USER_GENERIC_EXAM.format(
            subject=subject,
            topic=topic,
            level=level,
            duration_minutes=duration_minutes,
            mode=mode,
        )

    try:
        raw = call_llm(system_prompt, user_prompt)
    except LLMError as e:
        st.error(f"KI-Fehler: {e}")
        return {"questions": []}

    try:
        data = extract_json_from_response(raw)
        if not isinstance(data, dict) or "questions" not in data:
            raise ValueError("Antwort enthaelt kein 'questions'-Feld.")
        return data
    except ValueError as e:
        st.error(f"Fehler beim Parsen der Pruefungs-Antwort: {e}")
        if raw:
            with st.expander("Rohantwort der KI anzeigen"):
                st.code(raw)
        return {"questions": []}


# ============================================================
# 7. STT / TTS / Dateiextraktion
# ============================================================

def stt_transcribe_audio(file_bytes: bytes, filename: str = "audio.mp3") -> str:
    """
    Spracherkennung: Audio (Bytes) -> Text mit OpenAI Whisper.
    """
    try:
        api_key = st.session_state.openai_api_key.strip()
        if not api_key:
            return "Fehler: Kein OpenAI-API-Key hinterlegt. Bitte unter KI-Einstellungen konfigurieren."

        client = OpenAI(api_key=api_key)

        # Erstelle ein file-like Objekt für die API
        audio_file = BytesIO(file_bytes)
        audio_file.name = filename

        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="de"
        )
        return transcript.text
    except OpenAIRateLimitError:
        return "Fehler: OpenAI Rate-Limit erreicht. Bitte später erneut versuchen."
    except OpenAIAPIError as e:
        return f"Fehler bei der Transkription: {e}"
    except Exception as e:
        return f"Unerwarteter Fehler bei der Transkription: {e}"


def tts_generate_audio_from_text(text: str, voice: str = "alloy") -> bytes:
    """
    Text-to-Speech: Text -> Audio-Bytes (mp3) mit OpenAI TTS.
    Verfügbare Stimmen: alloy, echo, fable, onyx, nova, shimmer
    """
    try:
        api_key = st.session_state.openai_api_key.strip()
        if not api_key:
            st.error("Kein OpenAI-API-Key hinterlegt. Bitte unter KI-Einstellungen konfigurieren.")
            return b""

        client = OpenAI(api_key=api_key)

        # OpenAI TTS hat ein Limit von 4096 Zeichen pro Anfrage
        # Bei längeren Texten in Chunks aufteilen
        max_chars = 4096
        audio_chunks = []

        # Text in Sätze aufteilen für natürliche Pausen
        sentences = re.split(r'(?<=[.!?])\s+', text)
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) < max_chars:
                current_chunk += sentence + " "
            else:
                if current_chunk.strip():
                    audio_chunks.append(current_chunk.strip())
                current_chunk = sentence + " "

        if current_chunk.strip():
            audio_chunks.append(current_chunk.strip())

        # Generiere Audio für jeden Chunk
        all_audio = b""
        for i, chunk in enumerate(audio_chunks):
            if not chunk:
                continue

            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=chunk,
                response_format="mp3"
            )
            all_audio += response.content

            # Fortschrittsanzeige
            if len(audio_chunks) > 1:
                st.progress((i + 1) / len(audio_chunks), text=f"Generiere Audio: Teil {i+1}/{len(audio_chunks)}")

        return all_audio

    except OpenAIRateLimitError:
        st.error("OpenAI Rate-Limit erreicht. Bitte später erneut versuchen.")
        return b""
    except OpenAIAPIError as e:
        st.error(f"Fehler bei der Audio-Generierung: {e}")
        return b""
    except Exception as e:
        st.error(f"Unerwarteter Fehler bei der Audio-Generierung: {e}")
        return b""


def extract_text_from_pdf(uploaded_file) -> str:
    """
    Liest ein PDF mit pdfplumber und gibt den extrahierten Text zurück.
    """
    text_chunks = []
    with pdfplumber.open(BytesIO(uploaded_file.read())) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)
    return "\n\n".join(text_chunks)


def extract_text_from_docx(uploaded_file) -> str:
    """
    Liest ein DOCX-Dokument mit python-docx ein und gibt den Text zurück.
    """
    doc = Document(BytesIO(uploaded_file.read()))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def extract_text_from_image(uploaded_file) -> str:
    """
    Führt OCR auf einem hochgeladenen Bild durch (pytesseract).
    Tesseract muss auf dem System installiert und im PATH sein.
    """
    img = Image.open(BytesIO(uploaded_file.read()))
    text = pytesseract.image_to_string(img, lang="deu+eng")
    return text


def extract_text_from_uploaded_file(uploaded_file) -> str:
    """
    Delegiert je nach Dateityp an PDF/DOCX/TXT/Image-OCR.
    Wird in der Upload-Seite verwendet.
    """
    filename = uploaded_file.name.lower()

    if filename.endswith(".txt"):
        try:
            return uploaded_file.read().decode("utf-8", errors="ignore")
        except Exception as e:
            return f"Fehler beim Lesen der TXT-Datei: {e}"

    if filename.endswith(".pdf"):
        try:
            return extract_text_from_pdf(uploaded_file)
        except Exception as e:
            return f"Fehler beim PDF-Auslesen: {e}"

    if filename.endswith(".docx"):
        try:
            return extract_text_from_docx(uploaded_file)
        except Exception as e:
            return f"Fehler beim DOCX-Auslesen: {e}"

    if any(filename.endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
        try:
            return extract_text_from_image(uploaded_file)
        except Exception as e:
            return f"Fehler bei Bild/OCR: {e}"

    return "Dateiformat wird noch nicht unterstützt."


# ============================================================
# 8. Spaced-Repetition & Timeline
# ============================================================

BOX_INTERVALS = {1: 1, 2: 2, 3: 4, 4: 7, 5: 15}


def update_card_after_result(card: Card, result: str):
    today = dt.date.today()
    card.last_reviewed = today

    if result == "correct":
        card.in_special_bucket = False
        card.success_streak += 1
        card.box = min(card.box + 1, max(BOX_INTERVALS.keys()))
    else:
        card.in_special_bucket = True
        card.success_streak = 0
        card.box = 1

    interval_days = BOX_INTERVALS.get(card.box, 1)
    card.due_date = today + dt.timedelta(days=interval_days)
    db_update_card_spaced(card)


def compute_timeline_status(plan: StudyPlan) -> Dict[str, Any]:
    today = dt.date.today()
    total_days = (plan.end_date - plan.start_date).days
    if total_days <= 0:
        total_days = 1

    all_days_until_today = [
        plan.start_date + dt.timedelta(days=i)
        for i in range((today - plan.start_date).days + 1)
        if plan.start_date + dt.timedelta(days=i) <= today
    ]
    free_days_until_today = [d for d in all_days_until_today if d in plan.free_days]
    learning_days_until_today = len(all_days_until_today) - len(free_days_until_today)
    learning_days_until_today = max(learning_days_until_today, 0)

    expected_progress = learning_days_until_today / max(total_days - len(plan.free_days), 1)

    cards = db_get_all_cards(plan.user_id)
    total_cards = len(cards) or 1
    reviewed_cards = [c for c in cards if c.last_reviewed is not None]
    actual_progress = len(reviewed_cards) / total_cards

    progress_diff = expected_progress - actual_progress
    days_behind = progress_diff * total_days if progress_diff > 0 else 0

    if days_behind == 0:
        color = "green"
    elif days_behind <= 2:
        color = "orange"
    else:
        color = "red"

    return {
        "expected_progress": expected_progress,
        "actual_progress": actual_progress,
        "days_behind": days_behind,
        "color": color,
    }


def render_timeline(plan: StudyPlan):
    status = compute_timeline_status(plan)
    today = dt.date.today()
    total_days = (plan.end_date - plan.start_date).days or 1
    pos_today = (today - plan.start_date).days / total_days
    pos_today = min(max(pos_today, 0), 1)

    expected_pct = int(status["expected_progress"] * 100)
    actual_pct = int(status["actual_progress"] * 100)
    today_pct = int(pos_today * 100)
    color = status["color"]

    bar_html = f"""
    <div style="position: relative; width: 100%; height: 20px; background-color: #eee; border-radius: 10px; margin-top: 10px;">
      <div style="position:absolute; left:0; top:0; height:100%; width:{actual_pct}%; background-color: #4CAF50; border-radius: 10px;"></div>
      <div style="position:absolute; left:{expected_pct}%; top:0; height:100%; width:2px; background-color: blue;"></div>
      <div style="position:absolute; left:{today_pct}%; top:-6px; border-left: 6px solid transparent;
                  border-right: 6px solid transparent; border-bottom: 6px solid {color};"></div>
    </div>
    <div style="font-size: 0.85em; margin-top: 4px;">
      <b>Start:</b> {plan.start_date} &nbsp;&nbsp;
      <b>Prüfung:</b> {plan.end_date} &nbsp;&nbsp;
      <b>Status:</b> {color.upper()} (Rückstand≈ {status["days_behind"]:.1f} Tage)
    </div>
    """
    st.markdown(bar_html, unsafe_allow_html=True)


# ============================================================
# 9. Seiten
# ============================================================

def render_gamification_header():
    """Rendert die Gamification-Leiste in der Sidebar."""
    stats = st.session_state.user_stats
    if not stats:
        return

    # XP und Level
    current_xp, next_xp = get_xp_for_next_level(stats.total_xp)
    xp_progress = (stats.total_xp - current_xp) / max(next_xp - current_xp, 1) * 100

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"### 🎮 Level {stats.level}")

    # XP-Fortschrittsbalken
    st.sidebar.markdown(f"""
    <div style="background:#e0e0e0;border-radius:10px;height:20px;margin:5px 0;">
        <div class="xp-bar" style="width:{xp_progress:.0f}%;"></div>
    </div>
    <small>{stats.total_xp} / {next_xp} XP</small>
    """, unsafe_allow_html=True)

    # Streak
    if stats.current_streak > 0:
        st.sidebar.markdown(f'<div class="streak-badge">🔥 {stats.current_streak} Tage Streak</div>',
                           unsafe_allow_html=True)


def page_home():
    st.title("📚 Smart Study Cards")

    # Gamification Header
    stats = st.session_state.user_stats
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🎮 Level", stats.level)
        with col2:
            st.metric("⭐ XP", f"{stats.total_xp:,}")
        with col3:
            st.metric("🔥 Streak", f"{stats.current_streak} Tage")
        with col4:
            st.metric("📚 Gelernt", stats.total_cards_learned)

    st.write("""
    Willkommen! Diese App erstellt mit Hilfe von KI interaktive Lernkarten, Lernpläne,
    Hörbücher, Videos und Prüfungssimulationen für verschiedene Studiengänge
    (z.B. Rechtswissenschaften, Medizin, Informatik, Physik).
    """)

    # Neue Achievements anzeigen
    if st.session_state.new_achievements:
        for ach_id in st.session_state.new_achievements:
            ach = ACHIEVEMENTS[ach_id]
            st.success(f"🏆 Neues Achievement: {ach['icon']} **{ach['name']}** - {ach['desc']} (+{ach['xp']} XP)")
        st.session_state.new_achievements = []

    st.subheader("Aktueller Lernplan – Timeline")
    render_timeline(st.session_state.study_plan)

    # Quick Stats
    st.subheader("📊 Schnellübersicht")
    col1, col2 = st.columns(2)

    with col1:
        # Heatmap der letzten 30 Tage
        st.markdown("**Aktivität der letzten 30 Tage**")
        heatmap_data = db_get_activity_heatmap(st.session_state.user_id, 30)
        if heatmap_data:
            # Einfache Visualisierung
            today = dt.date.today()
            html_cells = ""
            for i in range(30, -1, -1):
                day = today - dt.timedelta(days=i)
                day_str = day.isoformat()
                count = heatmap_data.get(day_str, 0)
                if count == 0:
                    color = "#ebedf0"
                elif count < 5:
                    color = "#9be9a8"
                elif count < 15:
                    color = "#40c463"
                elif count < 30:
                    color = "#30a14e"
                else:
                    color = "#216e39"
                html_cells += f'<div class="heatmap-cell" style="background-color:{color};" title="{day_str}: {count} Karten"></div>'
            st.markdown(f'<div style="display:flex;flex-wrap:wrap;">{html_cells}</div>', unsafe_allow_html=True)
        else:
            st.info("Noch keine Aktivitätsdaten vorhanden.")

    with col2:
        # Achievements Übersicht
        st.markdown("**🏆 Achievements**")
        earned = len(stats.achievements) if stats else 0
        total = len(ACHIEVEMENTS)
        st.progress(earned / total, text=f"{earned}/{total} freigeschaltet")


def page_upload_and_generate():
    st.title("📄 Dokumente hochladen & Karteikarten erzeugen")

    col1, col2 = st.columns(2)
    with col1:
        subject = st.selectbox("Fach / Studienrichtung", ["Rechtswissenschaften", "Medizin", "Informatik", "Physik", "Andere"])
        topic = st.text_input("Thema / Kapitel (z.B. Strafrecht AT, Innere Medizin – KHK)", "")
    with col2:
        difficulty = st.selectbox("Schwierigkeit", ["Einsteiger", "Fortgeschritten", "Examensniveau"])

    uploaded_files = st.file_uploader(
        "Skripte, Bücher, PDFs, Bilder etc. hochladen",
        type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    if st.button("👓 Analysieren & Karteikarten erzeugen"):
        if not uploaded_files:
            st.warning("Bitte mindestens eine Datei hochladen.")
            return

        combined_text = ""
        for uf in uploaded_files:
            text = extract_text_from_uploaded_file(uf)
            combined_text += "\n\n" + text

        with st.spinner("KI erstellt gerade Lernkarten…"):
            card_specs = llm_generate_flashcards(combined_text, subject, topic, difficulty)

        if not card_specs:
            st.error("Es konnten keine Karten erzeugt werden.")
            return

        deck = db_create_deck(st.session_state.user_id, f"{subject} – {topic}", subject, topic)

        for spec in card_specs:
            card = Card(
                id=0,
                deck_id=deck.id,
                user_id=st.session_state.user_id,
                subject=subject,
                question=spec.get("question", ""),
                answer=spec.get("answer", ""),
                explanation=spec.get("explanation", ""),
                choices=spec.get("choices"),
                correct_choice_index=spec.get("correct_choice_index"),
                due_date=dt.date.today(),
            )
            card.id = db_insert_card(card)

        st.success(f"Es wurden {len(card_specs)} Karteikarten im Deck '{deck.name}' angelegt.")


def render_card_study_ui(card: Card):
    bg_color = SUBJECT_COLORS.get(card.subject, "#ffffff")

    st.markdown(
        f'<div class="question-card" style="background-color:{bg_color};">'
        f'<strong>Frage:</strong> {card.question}</div>',
        unsafe_allow_html=True
    )

    # Verwende den vor der Sitzung gewaehlten Antwortmodus
    mode = st.session_state.study_answer_mode

    result = None
    feedback = None

    # Multiple Choice nur wenn Modus gewaehlt UND Karte MC-Optionen hat
    if mode == "Multiple Choice" and card.choices and card.correct_choice_index is not None:
        st.info("Modus: Multiple Choice")
        choice = st.radio("Antwort wählen:", card.choices, key=f"choice_{card.id}")
        if st.button("Antwort prüfen", key=f"check_mc_{card.id}"):
            idx = card.choices.index(choice)
            if idx == card.correct_choice_index:
                result = "correct"
                feedback = "✅ Richtig!"
            else:
                result = "wrong"
                feedback = f"❌ Falsch. Richtige Antwort: **{card.choices[card.correct_choice_index]}**"
    else:
        # Freitext-Modus (oder MC gewuenscht aber keine Optionen verfuegbar)
        if mode == "Multiple Choice" and (not card.choices or card.correct_choice_index is None):
            st.warning("Diese Karte hat keine Multiple-Choice-Optionen. Bitte als Freitext beantworten.")
        else:
            st.info("Modus: Freitext (KI-Bewertung)")

        user_text = st.text_area("Deine Antwort (Freitext)", height=150, key=f"ft_{card.id}")
        col1, col2, col3 = st.columns(3)
        with col1:
            clicked_check = st.button("Antwort bewerten", key=f"check_ft_{card.id}")
        with col2:
            clicked_skip = st.button("Skip", key=f"skip_{card.id}")
        with col3:
            show_solution = st.button("Loesung anzeigen", key=f"solution_{card.id}")

        if clicked_skip:
            result = "skip"
            feedback = "⏭ Frage wurde uebersprungen. Karte wandert in den Sondertopf."
        elif clicked_check:
            eval_result = llm_evaluate_free_text_answer(user_text, card)
            if eval_result["grade"] == "correct":
                result = "correct"
                feedback = "✅ Deine Antwort wird als richtig gewertet."
            elif eval_result["grade"] == "partial":
                result = "wrong"
                feedback = "⚠️ Teilweise richtig. " + eval_result.get("explanation", "")
            else:
                result = "wrong"
                feedback = "❌ Falsch. " + eval_result.get("explanation", "")
        elif show_solution:
            feedback = f"📘 Musterloesung:\n\n{card.answer}\n\n{card.explanation}"

    return result, feedback


def page_study_cards():
    st.title("🧠 Lernen mit Karteikarten")

    plan = st.session_state.study_plan
    render_timeline(plan)

    decks = db_get_decks(st.session_state.user_id)
    if not decks:
        st.info("Noch keine Decks vorhanden. Lade zuerst Dokumente hoch und lass Karten erzeugen.")
        return

    deck_names = {f"{d.subject} – {d.topic} (#{d.id})": d.id for d in decks}
    chosen = st.selectbox("Deck auswählen", list(deck_names.keys()))
    chosen_deck_id = deck_names[chosen]

    col1, col2 = st.columns(2)
    with col1:
        max_cards = st.slider("Anzahl Karten für diese Sitzung", 5, 50, 15)
    with col2:
        answer_mode = st.radio(
            "Antwortmodus",
            ["Freitext", "Multiple Choice"],
            index=0 if st.session_state.study_answer_mode == "Freitext" else 1,
            horizontal=True,
            help="Freitext: KI bewertet deine Antwort. Multiple Choice: Auswahl aus vorgegebenen Optionen."
        )

    include_special = st.checkbox("Sondertopf bevorzugt einbeziehen", value=True)

    if st.button("Lernsitzung starten"):
        st.session_state.study_answer_mode = answer_mode
        st.session_state.current_cards = db_select_next_due_cards(
            user_id=st.session_state.user_id,
            deck_id=chosen_deck_id,
            max_cards=max_cards,
            include_special_bucket=include_special,
        )
        st.session_state.current_card_index = 0

    if not st.session_state.current_cards:
        return

    index = st.session_state.current_card_index
    if index >= len(st.session_state.current_cards):
        st.success("Diese Lernsitzung ist abgeschlossen! 🎉")
        return

    card = st.session_state.current_cards[index]
    st.markdown(f"**Karte {index+1} von {len(st.session_state.current_cards)}**")
    result, feedback = render_card_study_ui(card)

    if feedback:
        st.info(feedback)

    if result in ["correct", "wrong", "skip"]:
        update_card_after_result(card, result)
        if st.button("Nächste Karte"):
            st.session_state.current_card_index += 1


def page_plan_and_calendar():
    st.title("📆 Lernplan & Kalender")

    plan: StudyPlan = st.session_state.study_plan

    st.subheader("Zeitraum der Vorbereitung")
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Startdatum", plan.start_date)
    with col2:
        end = st.date_input("Prüfungsdatum / Enddatum", plan.end_date)

    plan.start_date = start
    plan.end_date = end

    st.subheader("Freie Tage (kein Lernen)")
    free_days_str = ", ".join([d.isoformat() for d in plan.free_days]) if plan.free_days else ""
    new_free_days_str = st.text_input("Freie Tage (Komma-getrennt, Format YYYY-MM-DD)", value=free_days_str)
    if st.button("Freie Tage übernehmen"):
        try:
            days = [s.strip() for s in new_free_days_str.split(",") if s.strip()]
            plan.free_days = [dt.date.fromisoformat(s) for s in days]
            db_update_study_plan(plan)
            st.success("Freie Tage wurden aktualisiert.")
        except Exception:
            st.error("Fehler beim Parsen der Datumsangaben.")

    st.subheader("Gewichtung von Themen im Lernplan")
    decks = db_get_decks(plan.user_id)
    topics = sorted({f"{d.subject}: {d.topic}" for d in decks})
    new_weights: Dict[str, float] = {}

    for t in topics:
        new_weights[t] = st.slider(f"Gewichtung für {t}", 0.0, 1.0, plan.topic_weights.get(t, 0.0), 0.05)

    if st.button("Gewichtungen speichern"):
        plan.topic_weights = new_weights
        db_update_study_plan(plan)
        st.success("Themen-Gewichtungen gespeichert.")

    st.subheader("Timeline-Vorschau")
    render_timeline(plan)


def page_stats():
    st.title("📊 Auswertung & Lernanalyse")

    cards = db_get_all_cards(st.session_state.user_id)
    if not cards:
        st.info("Noch keine Karten vorhanden.")
        return

    total = len(cards)
    reviewed = [c for c in cards if c.last_reviewed is not None]
    special = [c for c in cards if c.in_special_bucket]

    st.metric("Gesamtzahl Karten", total)
    st.metric("Bereits einmal gelernt", len(reviewed))
    st.metric("Im Sondertopf", len(special))

    st.write("Hier können später detailliertere Statistiken nach Fach/Thema und Fehlerquote ergänzt werden.")


def page_exam_simulation():
    st.title("🎤 Prüfungssimulation (schriftlich / mündlich)")

    mode = st.radio("Prüfungsart", ["Schriftlich (Text)", "Mündlich (Audio)"], horizontal=True)
    subject = st.selectbox("Fach / Gebiet", ["Rechtswissenschaften", "Medizin", "Informatik", "Physik", "Andere"])
    topic = st.text_input("Thema / Schwerpunkt (z.B. Strafrecht BT – Körperverletzung)")
    duration = st.slider("Dauer (Minuten)", 15, 180, 45)
    level = st.selectbox("Niveau", ["Grundlagen", "Fortgeschritten", "Examensniveau", "Staatsexamen"])

    if st.button("Prüfung starten"):
        with st.spinner("KI erstellt die Prüfungssimulation…"):
            exam_spec = llm_generate_exam(
                subject,
                topic,
                duration,
                level,
                mode="mündlich" if mode.startswith("Mündlich") else "schriftlich"
            )
        st.session_state.current_exam = {
            "subject": subject,
            "topic": topic,
            "duration": duration,
            "mode": "audio" if mode.startswith("Mündlich") else "text",
            "questions": exam_spec.get("questions", []),
            "answers": [],
            "start_time": dt.datetime.now()
        }
        st.success("Prüfung gestartet.")

    exam = st.session_state.current_exam
    if not exam:
        return

    st.subheader(f"Aktuelle Prüfung: {exam['subject']} – {exam['topic']} ({exam['duration']} Min.)")

    elapsed = (dt.datetime.now() - exam["start_time"]).seconds // 60
    remaining = max(exam["duration"] - elapsed, 0)
    st.info(f"Verbleibende Zeit: {remaining} Minuten (ungefähre Anzeige)")

    if not exam["questions"]:
        st.warning("Noch keine Fragen verfügbar (KI-Antwort leer).")
        return

    q = exam["questions"][0]
    st.markdown(f"**Fall / Aufgabe:** {q.get('prompt', '')}")
    for sp in q.get("sub_prompts", []):
        st.markdown(f"- {sp}")

    answer_text = ""

    if exam["mode"] == "text":
        answer_text = st.text_area("Deine Lösung / Fallbearbeitung", height=250, key="exam_answer_text")
    else:
        uploaded_audio = st.file_uploader("Audioantwort hochladen (z.B. mp3/wav)", type=["mp3", "wav"], key="exam_audio")
        if uploaded_audio is not None and st.button("Audio transkribieren"):
            with st.spinner("Audio wird transkribiert mit OpenAI Whisper…"):
                answer_text = stt_transcribe_audio(uploaded_audio.read(), uploaded_audio.name)
            st.text_area("Transkribierte Antwort", answer_text, height=250, key="exam_answer_from_audio")

    if st.button("Antwort auswerten"):
        st.warning("Hier kann später eine KI-Analyse der Prüfungsantwort eingebaut werden (Hinweisfragen, Themen für Sondertopf etc.).")

    if st.button("Prüfung abbrechen"):
        st.session_state.current_exam = None
        st.info("Prüfungssimulation wurde abgebrochen.")


def generate_audio_script(cards: List[Card], subject: str, topic: str) -> str:
    """
    Generiert ein natuerliches Hoerbuch-Skript aus Karteikarten mittels KI.
    """
    cards_text = "\n\n".join([
        f"Frage {i+1}: {c.question}\nAntwort: {c.answer}\nErklaerung: {c.explanation}"
        for i, c in enumerate(cards)
    ])

    system_prompt = """
Du bist ein erfahrener Dozent, der Lerninhalte als Hoerbuch aufbereitet.
Erstelle aus den gegebenen Karteikarten ein zusammenhaengendes, gut strukturiertes
Hoerbuch-Skript. Der Text soll:
- Natuerlich und fluessig klingen (zum Vorlesen geeignet)
- Die wichtigsten Konzepte erklaeren
- Zusammenhaenge zwischen den Themen herstellen
- Mit einer kurzen Einfuehrung beginnen und einem Fazit enden
- Keine Aufzaehlungszeichen oder Formatierungen enthalten (nur Fliesstext)
"""

    user_prompt = f"""
FACH: {subject}
THEMA: {topic}

KARTEIKARTEN:
{cards_text}

Erstelle ein Hoerbuch-Skript (ca. 500-1000 Woerter), das diese Inhalte didaktisch aufbereitet vermittelt.
"""

    try:
        return call_llm(system_prompt, user_prompt)
    except LLMError as e:
        st.error(f"Fehler bei der Skript-Generierung: {e}")
        return ""


def page_audio_video_modes():
    st.title("🎧 Audio- & 🎬 Video-Lernen")

    st.write("""
    Hier kannst du Lerninhalte als **Hoerbuch** (Audio) anhoeren oder als **Lernkarten-Slideshow** durchgehen.
    Die KI erstellt ein natuerliches Hoerbuch-Skript aus deinen Karteikarten.
    """)

    # Pruefe OpenAI-Key fuer Audio
    if not st.session_state.openai_api_key.strip():
        st.warning("⚠️ Fuer Audio-Funktionen wird ein OpenAI-API-Key benoetigt. Bitte unter 'KI-Einstellungen' hinterlegen.")

    decks = db_get_decks(st.session_state.user_id)
    if not decks:
        st.info("Noch keine Decks vorhanden. Lade zuerst Dokumente hoch und lass Karten erzeugen.")
        return

    deck_names = {f"{d.subject} – {d.topic} (#{d.id})": d.id for d in decks}
    chosen = st.selectbox("Deck / Thema auswaehlen", list(deck_names.keys()))
    chosen_deck_id = deck_names[chosen]

    # Finde das gewaehlte Deck
    chosen_deck = next((d for d in decks if d.id == chosen_deck_id), None)

    mode = st.radio("Modus waehlen", ["🎧 Audio (Hoerbuch)", "🎬 Lernkarten-Slideshow"], horizontal=True)

    if mode.startswith("🎧"):
        # Audio-Modus
        st.subheader("Audio-Einstellungen")

        col1, col2 = st.columns(2)
        with col1:
            voice = st.selectbox(
                "Stimme auswaehlen",
                ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                help="Verschiedene OpenAI TTS-Stimmen mit unterschiedlichen Charakteristiken"
            )
        with col2:
            script_mode = st.radio(
                "Skript-Modus",
                ["KI-Hoerbuch (empfohlen)", "Rohdaten (Frage/Antwort)"],
                help="KI-Hoerbuch: Natuerlicher Fliesstext. Rohdaten: Direkte Frage-Antwort-Paare."
            )

        if st.button("🎧 Audio generieren"):
            cards_for_deck = db_get_cards_by_deck(chosen_deck_id, st.session_state.user_id)

            if not cards_for_deck:
                st.warning("Keine Karten in diesem Deck vorhanden.")
                return

            # Generiere Skript
            if script_mode.startswith("KI"):
                with st.spinner("KI erstellt Hoerbuch-Skript..."):
                    script = generate_audio_script(
                        cards_for_deck,
                        chosen_deck.subject if chosen_deck else "Allgemein",
                        chosen_deck.topic if chosen_deck else "Allgemein"
                    )
            else:
                script = "\n\n".join([
                    f"Frage: {c.question}. Antwort: {c.answer}. {c.explanation}"
                    for c in cards_for_deck
                ])

            if not script:
                st.error("Konnte kein Skript generieren.")
                return

            # Zeige Skript
            with st.expander("📝 Generiertes Skript anzeigen"):
                st.text_area("Skript", script, height=300)

            # Generiere Audio
            with st.spinner("Generiere Audio mit OpenAI TTS..."):
                audio_bytes = tts_generate_audio_from_text(script, voice=voice)

            if audio_bytes:
                st.success("✅ Audio erfolgreich generiert!")

                # Audio-Player
                st.audio(audio_bytes, format="audio/mp3")

                # Download-Button
                st.download_button(
                    label="⬇️ Audio herunterladen (MP3)",
                    data=audio_bytes,
                    file_name=f"hoerbuch_{chosen_deck.topic if chosen_deck else 'lerninhalt'}.mp3",
                    mime="audio/mpeg"
                )
            else:
                st.error("Audio-Generierung fehlgeschlagen. Bitte OpenAI-API-Key pruefen.")

    else:
        # Slideshow-Modus
        st.subheader("🎬 Lernkarten-Slideshow")

        cards_for_deck = db_get_cards_by_deck(chosen_deck_id, st.session_state.user_id)

        if not cards_for_deck:
            st.warning("Keine Karten in diesem Deck vorhanden.")
            return

        # Slideshow-Navigation
        if "slideshow_index" not in st.session_state:
            st.session_state.slideshow_index = 0

        total_cards = len(cards_for_deck)
        current_idx = st.session_state.slideshow_index

        # Navigation
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("⬅️ Zurueck", disabled=current_idx == 0):
                st.session_state.slideshow_index -= 1
                st.rerun()
        with col2:
            st.markdown(f"<h3 style='text-align: center;'>Karte {current_idx + 1} / {total_cards}</h3>", unsafe_allow_html=True)
        with col3:
            if st.button("Weiter ➡️", disabled=current_idx >= total_cards - 1):
                st.session_state.slideshow_index += 1
                st.rerun()

        # Aktuelle Karte anzeigen
        if current_idx < total_cards:
            card = cards_for_deck[current_idx]
            bg_color = SUBJECT_COLORS.get(card.subject, "#f5f5f5")

            # Slide-Darstellung
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, {bg_color} 0%, #ffffff 100%);
                padding: 2rem;
                border-radius: 1rem;
                box-shadow: 0 10px 40px rgba(0,0,0,0.15);
                margin: 1rem 0;
                min-height: 300px;
            ">
                <h2 style="color: #1e3a5f; margin-bottom: 1rem;">❓ Frage</h2>
                <p style="font-size: 1.2rem; color: #333; line-height: 1.6;">{card.question}</p>
            </div>
            """, unsafe_allow_html=True)

            # Antwort aufdecken
            if st.button("💡 Antwort anzeigen", key=f"show_answer_{current_idx}"):
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #e8f5e9 0%, #ffffff 100%);
                    padding: 2rem;
                    border-radius: 1rem;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.15);
                    margin: 1rem 0;
                ">
                    <h2 style="color: #2e7d32; margin-bottom: 1rem;">✅ Antwort</h2>
                    <p style="font-size: 1.1rem; color: #333; line-height: 1.6;">{card.answer}</p>
                    {"<hr style='margin: 1rem 0;'><p style='color: #666;'><strong>Erklaerung:</strong> " + card.explanation + "</p>" if card.explanation else ""}
                </div>
                """, unsafe_allow_html=True)

        # Zurueck zum Anfang
        if st.button("🔄 Slideshow von vorne starten"):
            st.session_state.slideshow_index = 0
            st.rerun()


def page_llm_settings():
    st.title("⚙️ KI-Einstellungen")

    st.write("Hier wählst du, ob die App über OpenAI (ChatGPT) oder Anthropic (Claude) läuft und kannst den API-Key hinterlegen.")

    provider = st.radio(
        "KI-Provider auswählen",
        ["OpenAI (ChatGPT)", "Anthropic (Claude)"],
        index=0 if st.session_state.llm_provider == "openai" else 1,
        horizontal=True,
    )

    if provider.startswith("OpenAI"):
        st.session_state.llm_provider = "openai"
    else:
        st.session_state.llm_provider = "anthropic"

    if st.session_state.llm_provider == "openai":
        st.subheader("🔑 OpenAI-API-Key")
        st.info("Den Key bekommst du im OpenAI-Dashboard unter 'API Keys'.")
        st.session_state.openai_api_key = st.text_input(
            "OpenAI API Key",
            value=st.session_state.openai_api_key,
            type="password",
            help="Wird nur in der aktuellen Streamlit-Session gehalten.",
        )
    else:
        st.subheader("🔑 Anthropic-API-Key")
        st.info("Den Key bekommst du im Claude-Dashboard unter 'API Keys'.")
        st.session_state.anthropic_api_key = st.text_input(
            "Anthropic API Key",
            value=st.session_state.anthropic_api_key,
            type="password",
            help="Wird nur in der aktuellen Streamlit-Session gehalten.",
        )

    if st.button("🔌 Verbindung testen"):
        test_llm_connection()

    status = st.session_state.llm_connection_status
    if status == "ok":
        st.success("Verbindung steht. Du kannst jetzt Lernkarten, Prüfungen etc. mit KI generieren. ✅")
    elif isinstance(status, str) and status not in (None, "ok"):
        st.error(f"Aktueller Verbindungsstatus: {status}")
    else:
        st.info("Noch kein Verbindungstest durchgeführt.")


# ============================================================
# 9b. Neue Seiten (Gamification, Tutor, Analytics, etc.)
# ============================================================

def page_gamification():
    """Gamification-Seite mit Achievements, XP-Details und Statistiken."""
    st.title("🎮 Gamification & Achievements")

    stats = st.session_state.user_stats

    # Level und XP
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Level", stats.level, delta=None)
        current_xp, next_xp = get_xp_for_next_level(stats.total_xp)
        st.progress((stats.total_xp - current_xp) / max(next_xp - current_xp, 1),
                   text=f"{stats.total_xp} / {next_xp} XP")

    with col2:
        st.metric("🔥 Aktueller Streak", f"{stats.current_streak} Tage")
        st.metric("📈 Längster Streak", f"{stats.longest_streak} Tage")

    with col3:
        st.metric("📚 Karten gelernt", stats.total_cards_learned)
        st.metric("✅ Richtig beantwortet", stats.total_correct)

    # Achievements Grid
    st.subheader("🏆 Achievements")

    cols = st.columns(4)
    for i, (ach_id, ach) in enumerate(ACHIEVEMENTS.items()):
        with cols[i % 4]:
            is_earned = ach_id in stats.achievements
            card_class = "achievement-card" if is_earned else "achievement-card achievement-locked"
            st.markdown(f"""
            <div class="{card_class}">
                <div style="font-size:2rem;">{ach['icon']}</div>
                <div><strong>{ach['name']}</strong></div>
                <div style="font-size:0.8rem;">{ach['desc']}</div>
                <div style="color:#666;font-size:0.75rem;">+{ach['xp']} XP</div>
            </div>
            """, unsafe_allow_html=True)

    # XP-Verlauf
    st.subheader("📈 XP-Verlauf")
    sessions = db_get_study_sessions(st.session_state.user_id, 30)
    if sessions:
        # Gruppiere nach Tag
        daily_xp = defaultdict(int)
        for s in sessions:
            daily_xp[s["date"]] += s.get("xp_earned", 0)

        dates = sorted(daily_xp.keys())
        xp_values = [daily_xp[d] for d in dates]

        # Einfaches Balkendiagramm
        if dates:
            st.bar_chart(dict(zip(dates[-14:], xp_values[-14:])))
    else:
        st.info("Noch keine XP-Daten vorhanden. Starte eine Lernsession!")


def page_tutor_chat():
    """KI-Tutor Chat-Seite."""
    st.title("🤖 KI-Tutor")
    st.write("Stelle Fragen zu deinem Lernstoff und erhalte personalisierte Erklärungen.")

    # Thema wählen
    decks = db_get_decks(st.session_state.user_id)
    topic_options = ["Allgemein"] + [f"{d.subject}: {d.topic}" for d in decks]
    selected_topic = st.selectbox("Thema/Kontext wählen", topic_options)

    # Chat-Verlauf laden
    chat_history = db_get_tutor_chat(st.session_state.user_id, 20)

    # Chat-Container
    chat_container = st.container()
    with chat_container:
        for msg in chat_history:
            if msg["role"] == "user":
                st.chat_message("user").write(msg["content"])
            else:
                st.chat_message("assistant").write(msg["content"])

    # Eingabe
    user_input = st.chat_input("Stelle eine Frage...")

    if user_input:
        # User-Nachricht speichern und anzeigen
        db_save_tutor_message(st.session_state.user_id, "user", user_input, selected_topic)
        st.chat_message("user").write(user_input)

        # KI-Antwort generieren
        system_prompt = f"""Du bist ein freundlicher und kompetenter Tutor.
Thema/Kontext: {selected_topic}

Deine Aufgaben:
- Erkläre Konzepte klar und verständlich
- Nutze Beispiele und Analogien
- Stelle Rückfragen um das Verständnis zu prüfen
- Gib Tipps zum effektiven Lernen
- Wenn der Nutzer "Erkläre wie für ein Kind" sagt, vereinfache maximal

Antworte auf Deutsch und sei ermutigend."""

        try:
            with st.spinner("KI denkt nach..."):
                response = call_llm(system_prompt, user_input)
            db_save_tutor_message(st.session_state.user_id, "assistant", response, selected_topic)
            st.chat_message("assistant").write(response)
        except LLMError as e:
            st.error(f"Fehler: {e}")

    # Chat löschen Button
    if st.button("🗑️ Chat-Verlauf löschen"):
        db_clear_tutor_chat(st.session_state.user_id)
        st.rerun()

    # Erklärmodus-Buttons
    st.markdown("---")
    st.markdown("**Schnell-Aktionen:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("👶 Erkläre einfach"):
            st.session_state.tutor_quick = "Erkläre das letzte Thema so einfach wie möglich, als wäre ich 5 Jahre alt."
    with col2:
        if st.button("📝 Zusammenfassung"):
            st.session_state.tutor_quick = "Fasse die wichtigsten Punkte zum aktuellen Thema zusammen."
    with col3:
        if st.button("❓ Quiz mich"):
            st.session_state.tutor_quick = "Stelle mir eine Verständnisfrage zum Thema."


def page_analytics():
    """Erweiterte Analytics-Seite."""
    st.title("📈 Erweiterte Lernanalyse")

    tab1, tab2, tab3 = st.tabs(["📊 Übersicht", "🎯 Schwächen", "⏰ Beste Lernzeit"])

    with tab1:
        st.subheader("Aktivitäts-Heatmap (letztes Jahr)")
        heatmap_data = db_get_activity_heatmap(st.session_state.user_id, 365)

        if heatmap_data:
            # Kalender-Grid rendern
            today = dt.date.today()
            weeks_html = ""

            for week in range(52):
                week_html = ""
                for day in range(7):
                    date = today - dt.timedelta(days=(51-week)*7 + (6-day))
                    date_str = date.isoformat()
                    count = heatmap_data.get(date_str, 0)

                    if count == 0:
                        color = "#ebedf0"
                    elif count < 5:
                        color = "#9be9a8"
                    elif count < 15:
                        color = "#40c463"
                    elif count < 30:
                        color = "#30a14e"
                    else:
                        color = "#216e39"

                    week_html += f'<div class="heatmap-cell" style="background-color:{color};" title="{date_str}: {count}"></div>'

                weeks_html += f'<div style="display:flex;flex-direction:column;">{week_html}</div>'

            st.markdown(f'<div style="display:flex;gap:2px;overflow-x:auto;">{weeks_html}</div>',
                       unsafe_allow_html=True)

            # Legende
            st.markdown("""
            <div style="display:flex;gap:10px;align-items:center;margin-top:10px;">
                <span>Weniger</span>
                <div class="heatmap-cell" style="background-color:#ebedf0;"></div>
                <div class="heatmap-cell" style="background-color:#9be9a8;"></div>
                <div class="heatmap-cell" style="background-color:#40c463;"></div>
                <div class="heatmap-cell" style="background-color:#30a14e;"></div>
                <div class="heatmap-cell" style="background-color:#216e39;"></div>
                <span>Mehr</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Noch keine Aktivitätsdaten vorhanden.")

        # Sessions der letzten 30 Tage
        st.subheader("Letzte Lernsessions")
        sessions = db_get_study_sessions(st.session_state.user_id, 30)
        if sessions:
            for s in sessions[:10]:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.write(f"📅 {s['date']}")
                with col2:
                    st.write(f"📚 {s['cards_seen']} Karten")
                with col3:
                    accuracy = s['cards_correct'] / s['cards_seen'] * 100 if s['cards_seen'] > 0 else 0
                    st.write(f"✅ {accuracy:.0f}% richtig")
                with col4:
                    st.write(f"⭐ +{s.get('xp_earned', 0)} XP")

    with tab2:
        st.subheader("🎯 Schwächen-Analyse")
        weaknesses = db_get_weakness_analysis(st.session_state.user_id)

        if weaknesses:
            for w in weaknesses:
                error_rate = w['error_rate'] * 100 if w['error_rate'] else 0
                color = "red" if error_rate > 50 else "orange" if error_rate > 30 else "green"

                st.markdown(f"""
                **{w['subject']}**
                - Fehlerquote: <span style="color:{color};">{error_rate:.1f}%</span>
                - {w['correct']} richtig / {w['wrong']} falsch
                """, unsafe_allow_html=True)

                st.progress(1 - (error_rate / 100))
        else:
            st.info("Noch keine Daten für Schwächen-Analyse. Lerne mehr Karten!")

    with tab3:
        st.subheader("⏰ Beste Lernzeiten")
        best_times = db_get_best_study_times(st.session_state.user_id)

        if best_times:
            # Sortiere nach Erfolgsquote
            sorted_times = sorted(best_times.items(), key=lambda x: x[1], reverse=True)

            st.write("Deine erfolgreichsten Lernzeiten:")
            for hour, success_rate in sorted_times[:5]:
                time_str = f"{hour:02d}:00 - {(hour+1):02d}:00"
                st.write(f"🕐 **{time_str}**: {success_rate*100:.0f}% Erfolgsquote")

            # Empfehlung
            if sorted_times:
                best_hour = sorted_times[0][0]
                st.success(f"💡 Empfehlung: Lerne am besten zwischen {best_hour:02d}:00 und {best_hour+1:02d}:00 Uhr!")
        else:
            st.info("Noch keine Daten vorhanden. Lerne zu verschiedenen Zeiten!")


def page_import_export():
    """Import/Export-Seite."""
    st.title("📥 Import / 📤 Export")

    tab1, tab2, tab3 = st.tabs(["📤 Exportieren", "📥 Importieren", "🔗 Teilen"])

    with tab1:
        st.subheader("Deck exportieren")
        decks = db_get_decks(st.session_state.user_id)

        if not decks:
            st.info("Keine Decks zum Exportieren vorhanden.")
        else:
            deck_names = {f"{d.name} ({d.subject})": d.id for d in decks}
            selected_deck = st.selectbox("Deck wählen", list(deck_names.keys()))
            deck_id = deck_names[selected_deck]

            export_format = st.radio("Format", ["JSON", "CSV"], horizontal=True)

            if st.button("📤 Exportieren"):
                if export_format == "JSON":
                    data = export_deck_to_json(deck_id, st.session_state.user_id)
                    st.download_button(
                        "⬇️ JSON herunterladen",
                        data,
                        file_name=f"deck_{deck_id}.json",
                        mime="application/json"
                    )
                else:
                    data = export_deck_to_csv(deck_id, st.session_state.user_id)
                    st.download_button(
                        "⬇️ CSV herunterladen",
                        data,
                        file_name=f"deck_{deck_id}.csv",
                        mime="text/csv"
                    )

    with tab2:
        st.subheader("Deck importieren")

        import_method = st.radio("Import-Methode", ["JSON-Datei", "Share-Code"], horizontal=True)

        if import_method == "JSON-Datei":
            uploaded_file = st.file_uploader("JSON-Datei hochladen", type=["json"])
            if uploaded_file and st.button("📥 Importieren"):
                json_str = uploaded_file.read().decode("utf-8")
                success, message = import_deck_from_json(json_str, st.session_state.user_id)
                if success:
                    st.success(message)
                else:
                    st.error(message)
        else:
            share_code = st.text_input("Share-Code eingeben", max_chars=8)
            if share_code and st.button("📥 Mit Code importieren"):
                success, message = import_deck_by_share_code(share_code.upper(), st.session_state.user_id)
                if success:
                    st.success(message)
                else:
                    st.error(message)

    with tab3:
        st.subheader("Deck teilen")
        decks = db_get_decks(st.session_state.user_id)

        if not decks:
            st.info("Keine Decks zum Teilen vorhanden.")
        else:
            deck_names = {f"{d.name} ({d.subject})": d.id for d in decks}
            selected_deck = st.selectbox("Deck zum Teilen wählen", list(deck_names.keys()), key="share_deck")
            deck_id = deck_names[selected_deck]

            if st.button("🔗 Share-Code generieren"):
                code = generate_share_code(deck_id)
                st.success(f"Share-Code: **{code}**")
                st.info("Teile diesen Code mit anderen, damit sie dein Deck importieren können.")


def page_pomodoro():
    """Pomodoro-Timer Seite."""
    st.title("🍅 Pomodoro-Timer")

    st.write("""
    Die Pomodoro-Technik: 25 Minuten fokussiertes Lernen, dann 5 Minuten Pause.
    Nach 4 Pomodoros eine längere Pause (15-30 Min).
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Timer-Einstellungen")
        work_duration = st.slider("Arbeitszeit (Minuten)", 15, 60, 25)
        break_duration = st.slider("Pause (Minuten)", 3, 15, 5)

    with col2:
        st.subheader("Statistik")
        st.metric("🍅 Heute abgeschlossen", st.session_state.pomodoro_sessions_completed)

    st.markdown("---")

    # Timer-Anzeige
    if st.session_state.pomodoro_running and st.session_state.pomodoro_start_time:
        elapsed = (dt.datetime.now() - st.session_state.pomodoro_start_time).seconds
        duration = (break_duration if st.session_state.pomodoro_break else work_duration) * 60
        remaining = max(0, duration - elapsed)

        minutes = remaining // 60
        seconds = remaining % 60

        phase = "☕ Pause" if st.session_state.pomodoro_break else "📚 Lernzeit"
        st.markdown(f"### {phase}")
        st.markdown(f'<div class="pomodoro-timer">{minutes:02d}:{seconds:02d}</div>', unsafe_allow_html=True)

        progress = elapsed / duration
        st.progress(min(progress, 1.0))

        if remaining == 0:
            if st.session_state.pomodoro_break:
                st.balloons()
                st.success("Pause vorbei! Bereit für die nächste Runde?")
                st.session_state.pomodoro_break = False
            else:
                st.session_state.pomodoro_sessions_completed += 1
                st.success("🎉 Pomodoro abgeschlossen! Zeit für eine Pause.")
                st.session_state.pomodoro_break = True

            st.session_state.pomodoro_running = False

        if st.button("⏹️ Stoppen"):
            st.session_state.pomodoro_running = False
            st.session_state.pomodoro_start_time = None
            st.rerun()

        # Auto-refresh
        st.empty()

    else:
        st.markdown('<div class="pomodoro-timer">00:00</div>', unsafe_allow_html=True)

        if st.button("▶️ Starten", type="primary"):
            st.session_state.pomodoro_running = True
            st.session_state.pomodoro_start_time = dt.datetime.now()
            st.session_state.pomodoro_duration = work_duration
            st.rerun()

    # Tipp
    st.markdown("---")
    st.info("💡 **Tipp:** Nutze den Pomodoro-Timer während du Karteikarten lernst oder mit dem KI-Tutor arbeitest!")


def page_cloze_cards():
    """Lückentext-Karten Seite."""
    st.title("📝 Lückentext-Karten (Cloze)")

    st.write("""
    Lückentext-Karten sind besonders effektiv für Definitionen und Fakten.
    Syntax: `{{c1::versteckter Text}}` für Lücken.
    """)

    tab1, tab2 = st.tabs(["➕ Erstellen", "📚 Lernen"])

    with tab1:
        st.subheader("Neue Lückentext-Karte erstellen")

        decks = db_get_decks(st.session_state.user_id)
        if not decks:
            st.warning("Erstelle zuerst ein Deck unter 'Upload & Karten'.")
            return

        deck_names = {f"{d.name}": d.id for d in decks}
        selected_deck = st.selectbox("Deck wählen", list(deck_names.keys()))
        deck_id = deck_names[selected_deck]

        # Beispiel zeigen
        st.info("Beispiel: 'Der {{c1::Bundestag}} wählt den {{c2::Bundeskanzler}}.'")

        cloze_text = st.text_area(
            "Lückentext eingeben",
            placeholder="Der {{c1::wichtige Begriff}} ist entscheidend für {{c2::ein Konzept}}.",
            height=150
        )

        explanation = st.text_input("Erklärung (optional)")

        if st.button("✅ Karte speichern"):
            if cloze_text and "{{c" in cloze_text:
                deck = next(d for d in decks if d.id == deck_id)
                db_insert_cloze_card(deck_id, st.session_state.user_id, deck.subject, cloze_text, explanation)
                st.success("Lückentext-Karte gespeichert!")
            else:
                st.error("Bitte gültigen Lückentext eingeben (mit {{c1::...}} Syntax).")

        # KI-Generierung
        st.markdown("---")
        st.subheader("🤖 KI-generierte Lückentext-Karten")

        source_text = st.text_area("Quelltext für KI", placeholder="Füge hier Text ein...", height=100)

        if st.button("🤖 Lückentexte generieren"):
            if source_text:
                with st.spinner("KI erstellt Lückentexte..."):
                    system_prompt = """Erstelle aus dem gegebenen Text 3-5 Lückentext-Karten.
                    Format: Jede Zeile eine Karte mit {{c1::...}} Syntax für die Lücken.
                    Verstecke die wichtigsten Begriffe/Konzepte."""

                    try:
                        result = call_llm(system_prompt, source_text)
                        st.text_area("Generierte Lückentexte (kopieren & bearbeiten):", result, height=200)
                    except LLMError as e:
                        st.error(f"Fehler: {e}")

    with tab2:
        st.subheader("Lückentext-Karten lernen")

        decks = db_get_decks(st.session_state.user_id)
        if not decks:
            return

        deck_names = {f"{d.name}": d.id for d in decks}
        selected_deck = st.selectbox("Deck wählen", list(deck_names.keys()), key="cloze_learn_deck")
        deck_id = deck_names[selected_deck]

        cloze_cards = db_get_cloze_cards(deck_id, st.session_state.user_id)

        if not cloze_cards:
            st.info("Keine Lückentext-Karten in diesem Deck.")
            return

        # Aktuelle Karte
        if "cloze_index" not in st.session_state:
            st.session_state.cloze_index = 0
        if "cloze_revealed" not in st.session_state:
            st.session_state.cloze_revealed = []

        idx = st.session_state.cloze_index % len(cloze_cards)
        card = cloze_cards[idx]

        st.markdown(f"**Karte {idx + 1} / {len(cloze_cards)}**")

        # Lücken parsen
        clozes = parse_cloze_text(card["cloze_text"])

        # Text mit Lücken anzeigen
        rendered = render_cloze_with_blanks(card["cloze_text"], st.session_state.cloze_revealed)
        st.markdown(f"""
        <div class="question-card" style="font-size:1.2rem;">
            {rendered}
        </div>
        """, unsafe_allow_html=True)

        # Buttons für jede Lücke
        cols = st.columns(len(clozes) + 2)
        for i, (cloze_id, content) in enumerate(clozes):
            with cols[i]:
                if cloze_id not in st.session_state.cloze_revealed:
                    if st.button(f"Lücke {cloze_id}", key=f"reveal_{cloze_id}"):
                        st.session_state.cloze_revealed.append(cloze_id)
                        st.rerun()

        with cols[-2]:
            if st.button("➡️ Nächste"):
                st.session_state.cloze_index += 1
                st.session_state.cloze_revealed = []
                st.rerun()

        with cols[-1]:
            if st.button("🔄 Alle zeigen"):
                st.session_state.cloze_revealed = [c[0] for c in clozes]
                st.rerun()


# ============================================================
# 10. Navigation
# ============================================================

PAGES = {
    "🏠 Übersicht": page_home,
    "📄 Upload & Karten": page_upload_and_generate,
    "🧠 Karteikarten lernen": page_study_cards,
    "📝 Lückentext (Cloze)": page_cloze_cards,
    "📆 Lernplan & Timeline": page_plan_and_calendar,
    "📊 Auswertung": page_stats,
    "📈 Erweiterte Analytik": page_analytics,
    "🎤 Prüfungssimulation": page_exam_simulation,
    "🎧 Audio / 🎬 Video": page_audio_video_modes,
    "🤖 KI-Tutor": page_tutor_chat,
    "🎮 Gamification": page_gamification,
    "🍅 Pomodoro": page_pomodoro,
    "📥 Import/Export": page_import_export,
    "⚙️ KI-Einstellungen": page_llm_settings,
}

st.sidebar.title("Navigation")

# Gamification in Sidebar anzeigen
render_gamification_header()

choice = st.sidebar.radio("Menü", list(PAGES.keys()))
PAGES[choice]()

# Versionsanzeige in der Sidebar
st.sidebar.markdown("---")
st.sidebar.caption(f"Version {APP_VERSION}")
st.sidebar.caption(f"Stand: {APP_LAST_UPDATE}")
