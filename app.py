"""
Unfall-Schadenmanagement App
----------------------------
Eine Streamlit-App zur Abwicklung von Verkehrsunfällen mit Dashboards
für Werkstatt, Anwalt, Versicherer und Unfallopfer.
"""

import streamlit as st
from auth import check_authentication, show_login_page

# Seiten-Konfiguration
st.set_page_config(
    page_title="Schadenmanager",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS für modernes Dashboard-Design
st.markdown("""
<style>
    /* Globaler Hintergrund */
    .stApp {
        background-color: #f5f5f7;
    }

    /* Card-Styling */
    .card {
        background-color: #ffffff;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07);
        padding: 20px;
        margin-bottom: 16px;
    }

    .card-header {
        font-size: 1.2em;
        font-weight: 600;
        color: #1a1a2e;
        margin-bottom: 12px;
        border-bottom: 2px solid #0066cc;
        padding-bottom: 8px;
    }

    /* Status-Badges */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.85em;
        font-weight: 500;
    }

    .status-green {
        background-color: #d4edda;
        color: #155724;
    }

    .status-orange {
        background-color: #fff3cd;
        color: #856404;
    }

    .status-red {
        background-color: #f8d7da;
        color: #721c24;
    }

    /* Sidebar-Styling */
    .css-1d391kg {
        background-color: #ffffff;
    }

    /* Button-Styling */
    .stButton>button {
        background-color: #0066cc;
        color: white;
        border-radius: 6px;
        border: none;
        padding: 8px 16px;
    }

    .stButton>button:hover {
        background-color: #0052a3;
    }
</style>
""", unsafe_allow_html=True)


def render_card(title: str, content: str):
    """Rendert eine Card mit Titel und Inhalt."""
    st.markdown(f"""
    <div class="card">
        <div class="card-header">{title}</div>
        <div>{content}</div>
    </div>
    """, unsafe_allow_html=True)


def main():
    """Hauptfunktion der App."""

    # Authentifizierung prüfen
    if not check_authentication():
        show_login_page()
        return

    # Sidebar Navigation
    with st.sidebar:
        st.markdown("### Navigation")

        # Benutzer-Info
        user = st.session_state.get("user", {})
        role = user.get("role", "Unbekannt")
        username = user.get("username", "Gast")

        st.markdown(f"""
        <div class="card">
            <strong>Angemeldet als:</strong><br>
            {username}<br>
            <small>Rolle: {role}</small>
        </div>
        """, unsafe_allow_html=True)

        # Menü je nach Rolle
        menu_items = get_menu_for_role(role)
        selected_page = st.radio("Bereich wählen:", menu_items, label_visibility="collapsed")

        st.markdown("---")
        if st.button("Abmelden", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # Hauptinhalt basierend auf Auswahl
    render_page(selected_page, role)


def get_menu_for_role(role: str) -> list:
    """Gibt die Menüpunkte basierend auf der Benutzerrolle zurück."""
    base_menu = ["Dashboard", "Projekte"]

    role_menus = {
        "Werkstatt": ["Ersatzwagen", "Rechnungen & Zahlungen"],
        "Anwalt": ["Mandate", "Gebühren & Streitwert", "Korrespondenz"],
        "Versicherung": ["Regulierung", "Gutachten", "Statistiken"],
        "Unfallopfer": ["Mein Fall", "Dokumente", "Status"]
    }

    return base_menu + role_menus.get(role, [])


def render_page(page: str, role: str):
    """Rendert die ausgewählte Seite."""

    st.title(f"📊 {page}")

    if page == "Dashboard":
        render_dashboard(role)
    elif page == "Projekte":
        render_projects()
    else:
        st.info(f"Seite '{page}' wird noch entwickelt...")


def render_dashboard(role: str):
    """Rendert das Dashboard für die jeweilige Rolle."""

    col1, col2 = st.columns(2)

    with col1:
        render_card("Aktive Projekte", """
            <p style="font-size: 2em; font-weight: bold; color: #0066cc;">12</p>
            <p>3 neue diese Woche</p>
        """)

        render_card("Offene Meilensteine", """
            <p><span class="status-badge status-red">3 Überfällig</span></p>
            <p><span class="status-badge status-orange">5 Diese Woche</span></p>
            <p><span class="status-badge status-green">8 Im Plan</span></p>
        """)

    with col2:
        render_card("Timeline", """
            <p>🔴 Gutachten ausstehend</p>
            <p>🟠 Reparatur in Arbeit</p>
            <p>🟢 Ersatzwagen bereit</p>
        """)

        render_card("Letzte Aktivitäten", """
            <p>• Neues Projekt angelegt (heute)</p>
            <p>• Gutachten hochgeladen (gestern)</p>
            <p>• Zahlung eingegangen (vor 3 Tagen)</p>
        """)


def render_projects():
    """Rendert die Projektübersicht."""

    # Demo-Daten
    projects = [
        {"id": "PRJ-001", "name": "Müller vs. Schmidt", "status": "In Bearbeitung", "datum": "2024-01-15"},
        {"id": "PRJ-002", "name": "Weber Unfall A7", "status": "Abgeschlossen", "datum": "2024-01-10"},
        {"id": "PRJ-003", "name": "Fischer Parkschaden", "status": "Neu", "datum": "2024-01-20"},
    ]

    for proj in projects:
        status_class = {
            "Neu": "status-orange",
            "In Bearbeitung": "status-green",
            "Abgeschlossen": "status-green"
        }.get(proj["status"], "status-orange")

        st.markdown(f"""
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>{proj['id']}</strong> - {proj['name']}
                    <br><small>Erstellt: {proj['datum']}</small>
                </div>
                <span class="status-badge {status_class}">{proj['status']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
