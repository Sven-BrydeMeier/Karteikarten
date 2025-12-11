"""
Authentifizierungsmodul für die Schadenmanager-App
--------------------------------------------------
Verwendet bcrypt direkt für Passwort-Hashing (stabil und kompatibel).
"""

import streamlit as st
import bcrypt
import json
from pathlib import Path
from datetime import datetime

# Pfad zur Benutzer-Datenbank (JSON-Datei)
USERS_DB_PATH = Path("data/users.json")


def hash_password(password: str) -> str:
    """Hasht ein Passwort mit bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Überprüft ein Passwort gegen den Hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def load_users() -> dict:
    """Lädt die Benutzerdatenbank."""
    if USERS_DB_PATH.exists():
        try:
            with open(USERS_DB_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_users(users: dict):
    """Speichert die Benutzerdatenbank."""
    USERS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def get_demo_users() -> dict:
    """Gibt Demo-Benutzer zurück (für Entwicklung/Test)."""
    return {
        "werkstatt": {
            "password_hash": hash_password("werkstatt123"),
            "role": "Werkstatt",
            "name": "Werkstatt Müller GmbH",
            "email": "info@werkstatt-mueller.de"
        },
        "anwalt": {
            "password_hash": hash_password("anwalt123"),
            "role": "Anwalt",
            "name": "RA Dr. Schmidt",
            "email": "schmidt@kanzlei.de"
        },
        "versicherung": {
            "password_hash": hash_password("versicherung123"),
            "role": "Versicherung",
            "name": "Allianz Schadenabteilung",
            "email": "schaden@allianz.de"
        },
        "kunde": {
            "password_hash": hash_password("kunde123"),
            "role": "Unfallopfer",
            "name": "Max Mustermann",
            "email": "max@example.de"
        }
    }


def init_demo_users():
    """Initialisiert Demo-Benutzer falls noch keine existieren."""
    users = load_users()
    if not users:
        users = get_demo_users()
        save_users(users)
    return users


def authenticate_user(username: str, password: str) -> dict | None:
    """Authentifiziert einen Benutzer."""
    users = load_users()

    # Falls keine Benutzer existieren, Demo-Benutzer erstellen
    if not users:
        users = init_demo_users()

    if username not in users:
        return None

    user_data = users[username]
    if verify_password(password, user_data.get("password_hash", "")):
        return {
            "username": username,
            "role": user_data.get("role", "Unbekannt"),
            "name": user_data.get("name", username),
            "email": user_data.get("email", "")
        }
    return None


def register_user(username: str, password: str, role: str, name: str, email: str) -> tuple[bool, str]:
    """Registriert einen neuen Benutzer."""
    users = load_users()

    # Validierung
    if not username or len(username) < 3:
        return False, "Benutzername muss mindestens 3 Zeichen haben."

    if username in users:
        return False, "Benutzername bereits vergeben."

    if not password or len(password) < 6:
        return False, "Passwort muss mindestens 6 Zeichen haben."

    if role not in ["Werkstatt", "Anwalt", "Versicherung", "Unfallopfer"]:
        return False, "Ungültige Rolle ausgewählt."

    # Benutzer speichern
    users[username] = {
        "password_hash": hash_password(password),
        "role": role,
        "name": name or username,
        "email": email,
        "created_at": datetime.now().isoformat()
    }
    save_users(users)

    return True, "Registrierung erfolgreich! Sie können sich jetzt anmelden."


def check_authentication() -> bool:
    """Prüft ob der Benutzer authentifiziert ist."""
    return st.session_state.get("authenticated", False)


def show_login_page():
    """Zeigt die Login/Registrierungs-Seite."""

    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 20px;
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("<div class='login-header'>", unsafe_allow_html=True)
        st.title("🚗 Schadenmanager")
        st.markdown("##### Unfallabwicklung leicht gemacht")
        st.markdown("</div>", unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Anmelden", "Registrieren"])

        with tab1:
            show_login_form()

        with tab2:
            show_registration_form()

        # Demo-Hinweis
        with st.expander("Demo-Zugangsdaten"):
            st.markdown("""
            **Werkstatt:** werkstatt / werkstatt123
            **Anwalt:** anwalt / anwalt123
            **Versicherung:** versicherung / versicherung123
            **Unfallopfer:** kunde / kunde123
            """)


def show_login_form():
    """Zeigt das Login-Formular."""

    with st.form("login_form"):
        username = st.text_input("Benutzername", placeholder="Ihr Benutzername")
        password = st.text_input("Passwort", type="password", placeholder="Ihr Passwort")

        submitted = st.form_submit_button("Anmelden", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("Bitte Benutzername und Passwort eingeben.")
            else:
                user = authenticate_user(username, password)
                if user:
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = user
                    st.success(f"Willkommen, {user['name']}!")
                    st.rerun()
                else:
                    st.error("Ungültige Anmeldedaten.")


def show_registration_form():
    """Zeigt das Registrierungs-Formular."""

    with st.form("register_form"):
        username = st.text_input("Benutzername*", placeholder="Min. 3 Zeichen")
        email = st.text_input("E-Mail*", placeholder="ihre@email.de")
        name = st.text_input("Name/Firma", placeholder="Ihr Name oder Firmenname")
        role = st.selectbox("Rolle*", ["Werkstatt", "Anwalt", "Versicherung", "Unfallopfer"])
        password = st.text_input("Passwort*", type="password", placeholder="Min. 6 Zeichen")
        password_confirm = st.text_input("Passwort bestätigen*", type="password")

        submitted = st.form_submit_button("Registrieren", use_container_width=True)

        if submitted:
            if password != password_confirm:
                st.error("Passwörter stimmen nicht überein.")
            else:
                success, message = register_user(username, password, role, name, email)
                if success:
                    st.success(message)
                else:
                    st.error(message)
