import os
import re
import json
import sqlite3
import datetime as dt
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from io import BytesIO

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
APP_VERSION = "1.2.0"
APP_LAST_UPDATE = "2025-12-14 10:30"

load_dotenv()  # .env-Datei laden, falls vorhanden

st.set_page_config(
    page_title="Smart Study Cards",
    page_icon="📚",
    layout="wide",
)

# Schatten-Styles für Karten
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
</style>
""", unsafe_allow_html=True)

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
            topic TEXT NOT NULL
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


init_db_schema()
init_state()
init_llm_state()

# Study-Plan aus DB holen (oder anlegen)
st.session_state.study_plan = get_or_create_study_plan(st.session_state.user_id)


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

def page_home():
    st.title("📚 Smart Study Cards")
    st.write("""
    Willkommen! Diese App erstellt mit Hilfe von KI interaktive Lernkarten, Lernpläne,
    Hörbücher, Videos und Prüfungssimulationen für verschiedene Studiengänge
    (z.B. Rechtswissenschaften, Medizin, Informatik, Physik).
    """)

    st.subheader("Aktueller Lernplan – Timeline")
    render_timeline(st.session_state.study_plan)


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
# 10. Navigation
# ============================================================

PAGES = {
    "🏠 Übersicht": page_home,
    "📄 Upload & Karten": page_upload_and_generate,
    "🧠 Karteikarten lernen": page_study_cards,
    "📆 Lernplan & Timeline": page_plan_and_calendar,
    "📊 Auswertung": page_stats,
    "🎤 Prüfungssimulation": page_exam_simulation,
    "🎧 Audio / 🎬 Video": page_audio_video_modes,
    "⚙️ KI-Einstellungen": page_llm_settings,
}

st.sidebar.title("Navigation")
choice = st.sidebar.radio("Menü", list(PAGES.keys()))
PAGES[choice]()

# Versionsanzeige in der Sidebar
st.sidebar.markdown("---")
st.sidebar.caption(f"Version {APP_VERSION}")
st.sidebar.caption(f"Stand: {APP_LAST_UPDATE}")
