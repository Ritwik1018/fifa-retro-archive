import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import re

# ==========================================
# DATABASE INITIALIZATION & BASELINES
# ==========================================
DB_FILE = "fifa_retro_archive.db"

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Global Archives Metadata
    c.execute('''CREATE TABLE IF NOT EXISTS archives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    start_year INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')

    # Trophy Logs
    c.execute('''CREATE TABLE IF NOT EXISTS trophy_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    archive_id INTEGER NOT NULL,
                    season TEXT NOT NULL,
                    competition_type TEXT NOT NULL,
                    sub_category TEXT,
                    winner TEXT NOT NULL,
                    runner_up TEXT,
                    score TEXT,
                    third_place TEXT,
                    host_nation TEXT,
                    FOREIGN KEY(archive_id) REFERENCES archives(id) ON DELETE CASCADE
                )''')

    # Schema Migration Check
    c.execute("PRAGMA table_info(trophy_logs)")
    columns = [column[1] for column in c.fetchall()]
    if "host_nation" not in columns:
        c.execute("ALTER TABLE trophy_logs ADD COLUMN host_nation TEXT")
    if "third_place" not in columns:
        c.execute("ALTER TABLE trophy_logs ADD COLUMN third_place TEXT")

    # Ballon d'Or Logs
    c.execute('''CREATE TABLE IF NOT EXISTS ballon_dor_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    archive_id INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    player_name TEXT NOT NULL,
                    positions TEXT,
                    club TEXT,
                    nation TEXT,
                    FOREIGN KEY(archive_id) REFERENCES archives(id) ON DELETE CASCADE
                )''')

    # Timeline Logs
    c.execute('''CREATE TABLE IF NOT EXISTS timeline_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    archive_id INTEGER NOT NULL,
                    season TEXT NOT NULL,
                    category TEXT NOT NULL,
                    event_details TEXT NOT NULL,
                    FOREIGN KEY(archive_id) REFERENCES archives(id) ON DELETE CASCADE
                )''')

    # Seed Default Archive
    c.execute("SELECT COUNT(*) FROM archives")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO archives (name, start_year) VALUES (?, ?)", ("Default 1998 Save", 1998))
    
    conn.commit()
    conn.close()

# HISTORICAL BASELINES
BASELINES = {
    "World Cup": {"Brazil": 4, "Italy": 3, "Germany": 3, "Uruguay": 2, "Argentina": 2, "England": 1, "France": 1},
    "Euro": {"Germany": 3, "France": 2, "Netherlands": 1, "Denmark": 1, "Spain": 1, "Italy": 1, "Soviet Union": 1, "Czechoslovakia": 1, "Portugal": 0, "Greece": 0},
    "Copa America": {"Argentina": 14, "Uruguay": 14, "Brazil": 5, "Paraguay": 2, "Peru": 2, "Bolivia": 1, "Colombia": 0, "Chile": 0},
    "AFCON": {"Ghana": 4, "Egypt": 4, "Cameroon": 2, "Nigeria": 2, "DR Congo": 2, "Ivory Coast": 1, "South Africa": 1, "Morocco": 1, "Algeria": 1, "Ethiopia": 1, "Sudan": 1, "Congo": 1, "Senegal": 0, "Zambia": 0, "Tunisia": 0},
    "Asian Cup": {"Iran": 3, "Saudi Arabia": 3, "South Korea": 2, "Japan": 1, "Kuwait": 1, "Israel": 1, "Qatar": 0, "Australia": 0},
    "Finalissima": {"France": 1, "Argentina": 1},
    "Club World Cup": {"Real Madrid": 4, "Barcelona": 3, "Corinthians": 2, "Bayern Munich": 1, "Liverpool": 1, "Chelsea": 1, "Inter Milan": 1, "AC Milan": 1, "Manchester United": 1, "Sao Paulo": 1, "International": 1},
    "UCL": {
        "Real Madrid": 7, "AC Milan": 5, "Liverpool": 4, "Ajax": 4, "Bayern Munich": 3,
        "Inter Milan": 2, "Benfica": 2, "Nottingham Forest": 2, "Juventus": 2, "Porto": 1,
        "Manchester United": 1, "Aston Villa": 1, "Celtic": 1, "Feyenoord": 1, "Hamburger SV": 1,
        "Steaua Bucuresti": 1, "PSV Eindhoven": 1, "Red Star Belgrade": 1, "Barcelona": 1, "Marseille": 1, 
        "Borussia Dortmund": 1, "Chelsea": 0, "Manchester City": 0, "Paris Saint-Germain": 0, "Arsenal": 0, "Atletico Madrid": 0
    },
    "EPL": {
        "Liverpool": 18, "Manchester United": 11, "Arsenal": 11, "Everton": 9, "Aston Villa": 7,
        "Sunderland": 6, "Newcastle United": 4, "Sheffield Wednesday": 4, "Blackburn Rovers": 3,
        "Huddersfield Town": 3, "Wolverhampton": 3, "Leeds United": 3, "Preston North End": 2,
        "Portsmouth": 2, "Burnley": 2, "Tottenham Hotspur": 2, "Manchester City": 2, "Derby County": 2,
        "Sheffield United": 1, "West Bromwich Albion": 1, "Chelsea": 1, "Ipswich Town": 1, "Nottingham Forest": 1,
        "Leicester City": 0, "West Ham United": 0, "Southampton": 0, "Crystal Palace": 0, "Fulham": 0, "Brighton": 0
    },
    "La Liga": {
        "Real Madrid": 27, "Barcelona": 15, "Atletico Madrid": 9, "Athletic Bilbao": 8,
        "Valencia": 4, "Real Sociedad": 2, "Real Betis": 1, "Sevilla": 1, "Deportivo La Coruña": 0,
        "Villarreal": 0, "RCD Espanyol": 0, "RCD Mallorca": 0, "Real Zaragoza": 0, "Girona": 0, "Celta Vigo": 0
    },
    "Bundesliga": {
        "Bayern Munich": 14, "Nurnberg": 9, "Schalke 04": 7, "Hamburger SV": 6, "Borussia Dortmund": 5,
        "Borussia Monchengladbach": 5, "VfB Stuttgart": 4, "1. FC Kaiserslautern": 4, "Werder Bremen": 3,
        "1. FC Koln": 3, "Greuther Furth": 3, "VfB Leipzig": 3, "Hertha BSC": 2, "Dresdner SC": 2, "Hannover 96": 2,
        "Eintracht Frankfurt": 1, "TSV 1860 Munich": 1, "Eintracht Braunschweig": 1, "VfL Wolfsburg": 0, "Bayer Leverkusen": 0,
        "RB Leipzig": 0, "SC Freiburg": 0, "TSG 1899 Hoffenheim": 0, "Union Berlin": 0
    },
    "Serie A": {
        "Juventus": 25, "AC Milan": 15, "Inter Milan": 13, "Genoa": 9, "Bologna": 7, "Pro Vercelli": 7,
        "Torino": 7, "Roma": 2, "Napoli": 2, "Fiorentina": 2, "Lazio": 1, "Cagliari": 1, "Sampdoria": 1, "Hellas Verona": 1,
        "Atalanta": 0, "Udinese": 0, "Sassuolo": 0, "Parma": 0
    },
    "Ligue 1": {
        "Saint-Etienne": 10, "Marseille": 8, "Nantes": 7, "Monaco": 6, "Reims": 6, "Bordeaux": 4,
        "Nice": 4, "Paris Saint-Germain": 2, "Sochaux": 2, "Sete": 2, "Lille": 2, "Lens": 1, "Auxerre": 1, "Strasbourg": 1,
        "Olympique Lyonnais": 0, "Montpellier": 0, "Rennes": 0, "Toulouse": 0
    },
    "Ballon d'Or": {
        "Johan Cruyff": 3, "Michel Platini": 3, "Marco van Basten": 3, "Alfredo Di Stefano": 2,
        "Franz Beckenbauer": 2, "Kevin Keegan": 2, "Karl-Heinz Rummenigge": 2, "Ronaldo Nazario": 1,
        "Stanley Matthews": 1, "Raymond Kopa": 1, "Luis Suarez": 1, "Omar Sivori": 1, "Josef Masopust": 1,
        "Lev Yashin": 1, "Denis Law": 1, "Eusebio": 1, "Bobby Charlton": 1, "Florian Albert": 1,
        "George Best": 1, "Gianni Rivera": 1, "Gerd Muller": 1, "Oleg Blokhin": 1, "Allan Simonsen": 1,
        "Paolo Rossi": 1, "Igor Belanov": 1, "Ruud Gullit": 1, "Lothar Matthaus": 1, "Jean-Pierre Papin": 1,
        "Roberto Baggio": 1, "Hristo Stoichkov": 1, "George Weah": 1, "Matthias Sammer": 1, "Zinedine Zidane": 1,
        "Pavel Nedved": 0, "Andriy Shevchenko": 0, "Ronaldinho": 0, "Kaka": 0, "Lionel Messi": 0, "Cristiano Ronaldo": 0, "Luka Modric": 0, "Karim Benzema": 0, "Rodri": 0
    }
}

# HELPER: AUTO-HIDE EMPTY COLUMNS EVERYWHERE
def clean_dataframe(df):
    """
    Normalizes all variations of missing data (None, 'None', 'nan', '', whitespace)
    and drops any column where all values are empty or missing.
    """
    if df.empty:
        return df
    
    cleaned_df = df.copy()
    # Normalize empty indicators to np.nan across the dataframe
    cleaned_df = cleaned_df.replace(
        to_replace=[r'^\s*$', None, 'None', 'nan', '<NA>', 'NaN', 'NoneType'], 
        value=np.nan, 
        regex=True
    )
    
    # Drop columns that are completely null/empty
    cleaned_df = cleaned_df.dropna(how='all', axis=1)
    
    # Fill remaining NaNs back with empty strings for clean table rendering
    return cleaned_df.fillna('')

# AUTO-INCREMENT HELPER
def increment_season_string(season_str, years_to_add=1):
    season_str = str(season_str).strip()
    match_slash = re.match(r"^(\d{4})/(\d{2})$", season_str)
    if match_slash:
        start_year = int(match_slash.group(1))
        next_start = start_year + years_to_add
        next_end = (next_start + 1) % 100
        return f"{next_start}/{next_end:02d}"
    
    match_single = re.match(r"^(\d{4})$", season_str)
    if match_single:
        return str(int(match_single.group(1)) + years_to_add)
        
    return season_str

# DYNAMIC NEXT-YEAR COMPUTATION PER COMPETITION
def get_next_competition_year(archive_id, start_year, comp_type, sub_cat=None, is_quadrennial=False, is_slash=False):
    conn = get_connection()
    c = conn.cursor()
    
    if comp_type == "Ballon d'Or":
        c.execute("SELECT MAX(year) FROM ballon_dor_logs WHERE archive_id=?", (archive_id,))
        max_val = c.fetchone()[0]
        conn.close()
        if max_val is not None:
            return str(max_val + 1)
        return str(start_year + 1)
        
    elif comp_type == "Timeline":
        c.execute("SELECT season FROM timeline_logs WHERE archive_id=? ORDER BY id DESC LIMIT 1", (archive_id,))
        res = c.fetchone()
        conn.close()
        if res and res[0]:
            return increment_season_string(res[0], 1)
        return f"{start_year}/{str(start_year+1)[-2:]}" if is_slash else str(start_year)
        
    else:
        if sub_cat:
            c.execute("SELECT season FROM trophy_logs WHERE archive_id=? AND competition_type=? AND sub_category=? ORDER BY id DESC LIMIT 1", 
                      (archive_id, comp_type, sub_cat))
        else:
            c.execute("SELECT season FROM trophy_logs WHERE archive_id=? AND competition_type=? ORDER BY id DESC LIMIT 1", 
                      (archive_id, comp_type))
        res = c.fetchone()
        conn.close()
        
        step = 4 if is_quadrennial else 1
        if res and res[0]:
            return increment_season_string(res[0], step)
            
        # Default starting value when no logs exist
        if is_slash:
            return f"{start_year}/{str(start_year+1)[-2:]}"
        return str(start_year)

# Ordinal Helper Function
def get_ordinal(n):
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"

# AUTO-COMPLETE SUGGESTIONS FETCH
def get_suggestions(comp_key, archive_id, table_col="winner", extra_defaults=None):
    if extra_defaults is None:
        extra_defaults = []
    
    base_teams = list(BASELINES.get(comp_key, {}).keys())
    
    conn = get_connection()
    c = conn.cursor()
    if comp_key == "Ballon d'Or":
        c.execute("SELECT DISTINCT player_name FROM ballon_dor_logs WHERE archive_id=?", (archive_id,))
    elif comp_key in ["EPL", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]:
        c.execute(f"SELECT DISTINCT {table_col} FROM trophy_logs WHERE archive_id=? AND sub_category=?", (archive_id, comp_key))
    else:
        c.execute(f"SELECT DISTINCT {table_col} FROM trophy_logs WHERE archive_id=? AND competition_type=?", (archive_id, comp_key))
        
    db_results = [r[0] for r in c.fetchall() if r[0]]
    conn.close()
    
    all_suggestions = sorted(list(set(base_teams + extra_defaults + db_results)))
    return all_suggestions

# TITLE COUNT ENGINE
def get_total_titles_up_to(archive_id, comp_key, winner_name, record_id, sub_cat=None):
    base_count = BASELINES.get(comp_key, {}).get(winner_name, 0)
    conn = get_connection()
    c = conn.cursor()
    
    if comp_key == "Ballon d'Or":
        c.execute("SELECT COUNT(*) FROM ballon_dor_logs WHERE archive_id=? AND player_name=? AND id <= ?", (archive_id, winner_name, record_id))
    else:
        if sub_cat:
            c.execute("SELECT COUNT(*) FROM trophy_logs WHERE archive_id=? AND competition_type='Domestic League' AND sub_category=? AND winner=? AND id <= ?", 
                      (archive_id, sub_cat, winner_name, record_id))
        else:
            c.execute("SELECT COUNT(*) FROM trophy_logs WHERE archive_id=? AND competition_type=? AND winner=? AND id <= ?", 
                      (archive_id, comp_key, winner_name, record_id))
            
    in_save_count = c.fetchone()[0]
    conn.close()
    return base_count + in_save_count

# ==========================================
# STREAMLIT UI & HEADER CONTROLS
# ==========================================
st.set_page_config(page_title="FIFA Retro Archive Hub", layout="wide")
init_db()

st.title("⚽ FIFA RETRO ARCHIVE HUB")

conn = get_connection()
archives_df = pd.read_sql_query("SELECT * FROM archives", conn)
conn.close()

archive_options = {row['name']: (row['id'], row['start_year']) for _, row in archives_df.iterrows()}

col_sel, col_new, col_sys = st.columns([3, 1.5, 2])

with col_sel:
    selected_archive_name = st.selectbox(
        "Active Save Archive",
        options=list(archive_options.keys()),
        index=0 if len(archive_options) > 0 else None,
        label_visibility="collapsed"
    )
    active_archive_id, active_start_year = archive_options[selected_archive_name]

# SAVE SWITCH RESET LOGIC: Reset season fields when active save changes
if "current_active_archive_id" not in st.session_state or st.session_state["current_active_archive_id"] != active_archive_id:
    st.session_state["current_active_archive_id"] = active_archive_id
    # Purge cached season state values so they recalculate for the active save
    for k in list(st.session_state.keys()):
        if k.startswith("intl_yr_") or k in ["ucl_season", "cwc_season", "b_yr", "t_season"] or k.startswith("s_"):
            del st.session_state[k]

def create_archive_cb():
    name = st.session_state.get("new_archive_name_input", "").strip()
    year = st.session_state.get("new_archive_year_input", 1998)
    if name:
        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO archives (name, start_year) VALUES (?, ?)", (name, year))
            conn.commit()
            conn.close()
            st.session_state["new_archive_name_input"] = ""
        except sqlite3.IntegrityError:
            pass

with col_new:
    with st.popover("➕ New Save"):
        st.subheader("Create New Save Archive")
        st.text_input("Archive Name", key="new_archive_name_input")
        st.number_input("Start Era Year", value=1998, step=1, key="new_archive_year_input")
        st.button("Create Archive", on_click=create_archive_cb, use_container_width=True)

with col_sys:
    with st.popover("⚙️ SYSTEM MANAGER"):
        st.subheader("App-Wide Management")
        sys_tab1, sys_tab2, sys_tab3 = st.tabs(["✏️ Edit Archive", "🗑️ Delete Archive", "💾 Backup & Restore"])
        
        with sys_tab1:
            target_edit_name = st.selectbox("Select Archive to Edit", options=list(archive_options.keys()), key="edit_arch_sel")
            target_id, target_curr_year = archive_options[target_edit_name]
            updated_name = st.text_input("New Name", value=target_edit_name)
            updated_year = st.number_input("New Start Year", value=target_curr_year, step=1)
            if st.button("Save Changes", key="btn_edit_arch"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("UPDATE archives SET name=?, start_year=? WHERE id=?", (updated_name, updated_year, target_id))
                conn.commit()
                conn.close()
                st.success("Archive updated!")
                st.rerun()

        with sys_tab2:
            target_del_name = st.selectbox("Select Archive to Delete", options=list(archive_options.keys()), key="del_arch_sel")
            target_del_id, _ = archive_options[target_del_name]
            confirm_del = st.checkbox(f"Confirm deletion of '{target_del_name}'?", key="chk_del_arch")
            if st.button("🗑️ Permanently Delete Archive", key="btn_del_arch", type="primary"):
                if confirm_del:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM archives WHERE id=?", (target_del_id,))
                    conn.commit()
                    conn.close()
                    st.success(f"Deleted '{target_del_name}'!")
                    st.rerun()

        with sys_tab3:
            st.markdown("**Master App Backup & Restore**")
            with open(DB_FILE, "rb") as fp:
                st.download_button(
                    label="⬇️ Download Entire Database (.db)",
                    data=fp,
                    file_name="fifa_retro_archive.db",
                    mime="application/x-sqlite3",
                    use_container_width=True
                )
            st.divider()
            uploaded_db = st.file_uploader("Upload a .db Backup File", type=["db"])
            if uploaded_db is not None:
                if st.button("Overwrite Database with Upload", type="primary"):
                    with open(DB_FILE, "wb") as f:
                        f.write(uploaded_db.getbuffer())
                    st.success("Database restored!")
                    st.rerun()

st.caption(f"Currently Active: **{selected_archive_name}** | Baseline Era: **{active_start_year}**")
st.divider()

# ==========================================
# MAIN NAVIGATION (7 TABS)
# ==========================================
p1, p2, p3, p4, p5, p6, p7 = st.tabs([
    "1. International", 
    "2. Champions League", 
    "3. Club World Cup",
    "4. Domestic Leagues", 
    "5. Ballon d'Or", 
    "6. Timeline & Events", 
    "7. Active Save Data Editor"
])

# ------------------------------------------
# PAGE 1: INTERNATIONAL TOURNAMENTS
# ------------------------------------------
with p1:
    st.header("🏆 International Tournaments")
    col_entry, col_view = st.columns([1.2, 2])
    
    with col_entry:
        st.subheader("Log Tournament Result")
        selected_comp = st.selectbox("Tournament", ["World Cup", "Euro", "Copa America", "AFCON", "Asian Cup", "Finalissima"], key="intl_comp_select")
        
        is_4yr = selected_comp in ["World Cup", "Euro", "Copa America", "AFCON", "Asian Cup", "Finalissima"]
        intl_key = f"intl_yr_{selected_comp}"
        
        # Auto-year update calculation per tournament
        if intl_key not in st.session_state:
            st.session_state[intl_key] = get_next_competition_year(active_archive_id, active_start_year, selected_comp, is_quadrennial=is_4yr)
            
        curr_season = st.text_input("Year / Season", key=intl_key)
        
        nation_options = get_suggestions(selected_comp, active_archive_id)
        
        if selected_comp == "World Cup":
            sel_host = st.selectbox("Host Nation", nation_options, key="intl_host_sel", accept_new_options=True)
            sel_win = st.selectbox("Champion", nation_options, key="intl_win_sel", accept_new_options=True)
            sel_run = st.selectbox("Runner-Up", nation_options, key="intl_run_sel", accept_new_options=True)
            sel_third = st.selectbox("3rd Place", nation_options, key="intl_third_sel", accept_new_options=True)
            score_val = st.text_input("Final Scoreline", value="2-1", key="intl_score")
            
        elif selected_comp == "Finalissima":
            sel_host = None
            sel_win = st.selectbox("Winner / Champion", nation_options, key="intl_win_sel", accept_new_options=True)
            sel_run = st.selectbox("Runner-Up", nation_options, key="intl_run_sel", accept_new_options=True)
            sel_third = None
            score_val = st.text_input("Final Scoreline", value="2-1", key="intl_score")
        else:
            sel_host = None
            sel_win = st.selectbox("Champion", nation_options, key="intl_win_sel", accept_new_options=True)
            sel_run = None
            sel_third = None
            score_val = None

        def log_intl_callback(c_name, key_name):
            w = st.session_state.get("intl_win_sel")
            yr = st.session_state.get(key_name)
            if w:
                h = st.session_state.get("intl_host_sel") if c_name == "World Cup" else None
                r = st.session_state.get("intl_run_sel") if c_name in ["World Cup", "Finalissima"] else None
                t = st.session_state.get("intl_third_sel") if c_name == "World Cup" else None
                sc = st.session_state.get("intl_score") if c_name in ["World Cup", "Finalissima"] else None
                
                conn = get_connection()
                c = conn.cursor()
                c.execute('''INSERT INTO trophy_logs (archive_id, season, competition_type, winner, runner_up, score, third_place, host_nation)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                          (active_archive_id, yr, c_name, w, r, sc, t, h))
                conn.commit()
                conn.close()
                
                step = 4 if c_name in ["World Cup", "Euro", "Copa America", "AFCON", "Asian Cup", "Finalissima"] else 1
                st.session_state[key_name] = increment_season_string(yr, years_to_add=step)

        st.button("Log International Result", on_click=log_intl_callback, args=(selected_comp, intl_key), use_container_width=True)

    with col_view:
        st.subheader(f"Recorded {selected_comp} History")
        conn = get_connection()
        intl_df = pd.read_sql_query(
            "SELECT id, season AS Season, competition_type AS Tournament, host_nation AS Host, winner AS Champion, runner_up AS 'Runner-Up', third_place AS '3rd Place', score AS Score FROM trophy_logs WHERE archive_id=? AND competition_type = ? ORDER BY id DESC", 
            conn, params=(active_archive_id, selected_comp)
        )
        conn.close()
        
        if not intl_df.empty:
            intl_df['Total Titles'] = intl_df.apply(
                lambda r: f"{get_ordinal(get_total_titles_up_to(active_archive_id, r['Tournament'], r['Champion'], r['id']))} Title", axis=1
            )
            pref_cols = ['Season', 'Champion', 'Total Titles', 'Host', 'Runner-Up', '3rd Place', 'Score']
            existing_cols = [c for c in pref_cols if c in intl_df.columns]
            
            # Clean and auto-hide empty columns
            display_df = clean_dataframe(intl_df[existing_cols])
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info(f"No {selected_comp} results logged yet in this save.")

# ------------------------------------------
# PAGE 2: UEFA CHAMPIONS LEAGUE
# ------------------------------------------
with p2:
    st.header("🇪🇺 UEFA Champions League")
    col_e2, col_v2 = st.columns([1.2, 2])
    
    if "ucl_season" not in st.session_state:
        st.session_state["ucl_season"] = get_next_competition_year(active_archive_id, active_start_year, "UCL", is_slash=True)

    def log_ucl_callback():
        curr_season = st.session_state.get("ucl_season")
        w = st.session_state.get("ucl_win_sel")
        r = st.session_state.get("ucl_run_sel")
        score = st.session_state.get("ucl_score", "2-1").strip()
        
        if w:
            conn = get_connection()
            c = conn.cursor()
            c.execute('''INSERT INTO trophy_logs (archive_id, season, competition_type, winner, runner_up, score)
                         VALUES (?, ?, 'UCL', ?, ?, ?)''', 
                      (active_archive_id, curr_season, w, r, score))
            conn.commit()
            conn.close()
            
            st.session_state["ucl_season"] = increment_season_string(curr_season, years_to_add=1)

    with col_e2:
        st.subheader("Log UCL Final")
        st.text_input("Season", key="ucl_season")
        
        ucl_options = get_suggestions("UCL", active_archive_id)
        
        st.selectbox("UCL Champion", ucl_options, key="ucl_win_sel", accept_new_options=True)
        st.selectbox("Runner-Up", ucl_options, key="ucl_run_sel", accept_new_options=True)
        st.text_input("Scoreline", value="2-1", key="ucl_score")
        
        st.button("Log UCL Result", on_click=log_ucl_callback, use_container_width=True)

    with col_v2:
        st.subheader("Champions League Archive")
        conn = get_connection()
        ucl_df = pd.read_sql_query(
            "SELECT id, season AS Season, winner AS Champion, runner_up AS 'Runner-Up', score AS Score FROM trophy_logs WHERE archive_id=? AND competition_type='UCL' ORDER BY id DESC",
            conn, params=(active_archive_id,)
        )
        conn.close()
        
        if not ucl_df.empty:
            ucl_df['Total Titles'] = ucl_df.apply(
                lambda r: f"{get_ordinal(get_total_titles_up_to(active_archive_id, 'UCL', r['Champion'], r['id']))} UCL Title", axis=1
            )
            display_ucl = ucl_df[['Season', 'Champion', 'Total Titles', 'Runner-Up', 'Score']]
            display_ucl = clean_dataframe(display_ucl)
            st.dataframe(display_ucl, use_container_width=True, hide_index=True)
        else:
            st.info("No Champions League results logged yet.")

# ------------------------------------------
# PAGE 3: CLUB WORLD CUP
# ------------------------------------------
with p3:
    st.header("🌍 FIFA Club World Cup")
    col_c1, col_c2 = st.columns([1.2, 2])
    
    if "cwc_season" not in st.session_state:
        st.session_state["cwc_season"] = get_next_competition_year(active_archive_id, active_start_year, "Club World Cup", is_quadrennial=True)

    def log_cwc_callback():
        curr_season = st.session_state.get("cwc_season")
        w = st.session_state.get("cwc_win_sel")
        r = st.session_state.get("cwc_run_sel")
        h = st.session_state.get("cwc_host_sel")
        score = st.session_state.get("cwc_score", "2-1").strip()
        
        if w:
            conn = get_connection()
            c = conn.cursor()
            c.execute('''INSERT INTO trophy_logs (archive_id, season, competition_type, winner, runner_up, score, host_nation)
                         VALUES (?, ?, 'Club World Cup', ?, ?, ?, ?)''', 
                      (active_archive_id, curr_season, w, r, score, h))
            conn.commit()
            conn.close()
            
            st.session_state["cwc_season"] = increment_season_string(curr_season, years_to_add=4)

    with col_c1:
        st.subheader("Log Club World Cup Final")
        st.text_input("Year", key="cwc_season")
        
        club_options = get_suggestions("UCL", active_archive_id)
        nation_options = get_suggestions("World Cup", active_archive_id)
        
        st.selectbox("Host Nation", nation_options, key="cwc_host_sel", accept_new_options=True)
        st.selectbox("Winner", club_options, key="cwc_win_sel", accept_new_options=True)
        st.selectbox("Runner-Up", club_options, key="cwc_run_sel", accept_new_options=True)
        st.text_input("Final Scoreline", value="2-1", key="cwc_score")
        
        st.button("Log Club World Cup", on_click=log_cwc_callback, use_container_width=True)

    with col_c2:
        st.subheader("Club World Cup Archive")
        conn = get_connection()
        cwc_df = pd.read_sql_query(
            "SELECT id, season AS Year, host_nation AS Host, winner AS Winner, runner_up AS 'Runner-Up', score AS Score FROM trophy_logs WHERE archive_id=? AND competition_type='Club World Cup' ORDER BY id DESC",
            conn, params=(active_archive_id,)
        )
        conn.close()
        
        if not cwc_df.empty:
            cwc_df['Total Titles'] = cwc_df.apply(
                lambda r: f"{get_ordinal(get_total_titles_up_to(active_archive_id, 'Club World Cup', r['Winner'], r['id']))} Title", axis=1
            )
            display_cwc = cwc_df[['Year', 'Host', 'Winner', 'Total Titles', 'Runner-Up', 'Score']]
            display_cwc = clean_dataframe(display_cwc)
            st.dataframe(display_cwc, use_container_width=True, hide_index=True)
        else:
            st.info("No Club World Cup results logged yet.")

# ------------------------------------------
# PAGE 4: DOMESTIC LEAGUES
# ------------------------------------------
with p4:
    st.header("⚽ Big Five Domestic Leagues")
    
    league_tabs = st.tabs(["🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "🇪🇸 La Liga", "🇩🇪 Bundesliga", "🇮🇹 Serie A", "🇫🇷 Ligue 1"])
    league_keys = ["EPL", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]
    
    def log_league_callback(l_key):
        s_k = f"s_{l_key}"
        curr_season = st.session_state.get(s_k)
        w = st.session_state.get(f"w_sel_{l_key}")
        
        if w:
            conn = get_connection()
            c = conn.cursor()
            c.execute('''INSERT INTO trophy_logs (archive_id, season, competition_type, sub_category, winner)
                         VALUES (?, ?, 'Domestic League', ?, ?)''',
                      (active_archive_id, curr_season, l_key, w))
            conn.commit()
            conn.close()
            
            st.session_state[s_k] = increment_season_string(curr_season, years_to_add=1)

    for tab, l_key in zip(league_tabs, league_keys):
        with tab:
            cl1, cl2 = st.columns([1.2, 2])
            
            s_k = f"s_{l_key}"
            if s_k not in st.session_state:
                st.session_state[s_k] = get_next_competition_year(active_archive_id, active_start_year, "Domestic League", sub_cat=l_key, is_slash=True)

            with cl1:
                st.subheader(f"Log {l_key} Winner")
                st.text_input("Season", key=s_k)
                
                dom_options = get_suggestions(l_key, active_archive_id)
                st.selectbox("League Champion", dom_options, key=f"w_sel_{l_key}", accept_new_options=True)
                
                st.button(f"Log {l_key} Result", key=f"btn_{l_key}", on_click=log_league_callback, args=(l_key,), use_container_width=True)

            with cl2:
                st.subheader(f"{l_key} History Log")
                conn = get_connection()
                dom_df = pd.read_sql_query(
                    "SELECT id, season AS Season, winner AS Champion FROM trophy_logs WHERE archive_id=? AND competition_type='Domestic League' AND sub_category=? ORDER BY id DESC",
                    conn, params=(active_archive_id, l_key)
                )
                conn.close()
                
                if not dom_df.empty:
                    dom_df['Total Titles'] = dom_df.apply(
                        lambda r: f"{get_ordinal(get_total_titles_up_to(active_archive_id, l_key, r['Champion'], r['id'], sub_cat=l_key))} Title", axis=1
                    )
                    display_dom = dom_df[['Season', 'Champion', 'Total Titles']]
                    display_dom = clean_dataframe(display_dom)
                    st.dataframe(display_dom, use_container_width=True, hide_index=True)
                else:
                    st.info(f"No {l_key} titles logged yet.")

# ------------------------------------------
# PAGE 5: BALLON D'OR
# ------------------------------------------
with p5:
    st.header("🥇 Ballon d'Or Ledger")
    col_b1, col_b2 = st.columns([1.2, 2])
    
    if "b_yr" not in st.session_state:
        st.session_state["b_yr"] = get_next_competition_year(active_archive_id, active_start_year, "Ballon d'Or")

    def log_ballon_callback():
        curr_yr_str = str(st.session_state.get("b_yr")).strip()
        p = st.session_state.get("b_play_sel")
        c_val = st.session_state.get("b_club_sel")
        n_val = st.session_state.get("b_nat_sel")
        
        if p:
            pos_str = ", ".join(st.session_state.get("b_pos_select", ["ST"]))
            conn = get_connection()
            c = conn.cursor()
            c.execute('''INSERT INTO ballon_dor_logs (archive_id, year, player_name, positions, club, nation)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (active_archive_id, int(curr_yr_str) if curr_yr_str.isdigit() else active_start_year, p, pos_str, c_val, n_val))
            conn.commit()
            conn.close()
            
            st.session_state["b_yr"] = increment_season_string(curr_yr_str, years_to_add=1)

    with col_b1:
        st.subheader("Log Ballon d'Or Winner")
        st.text_input("Year", key="b_yr")
        
        player_options = get_suggestions("Ballon d'Or", active_archive_id)
        st.selectbox("Player Name", player_options, key="b_play_sel", accept_new_options=True)
            
        st.multiselect("Positions Played", ["ST", "CF", "RW", "LW", "AM", "CM", "DM", "CB", "LB", "RB", "GK"], default=["ST"], key="b_pos_select")
        
        club_options = get_suggestions("UCL", active_archive_id)
        st.selectbox("Club", club_options, key="b_club_sel", accept_new_options=True)
            
        nation_options = get_suggestions("World Cup", active_archive_id)
        st.selectbox("Nation", nation_options, key="b_nat_sel", accept_new_options=True)
        
        st.button("Log Ballon d'Or", on_click=log_ballon_callback, use_container_width=True)

    with col_b2:
        st.subheader("Ballon d'Or History")
        conn = get_connection()
        b_df = pd.read_sql_query(
            "SELECT id, year AS Year, player_name AS Winner, positions AS Positions, club AS Club, nation AS Nation FROM ballon_dor_logs WHERE archive_id=? ORDER BY year DESC",
            conn, params=(active_archive_id,)
        )
        conn.close()
        
        if not b_df.empty:
            b_award_name = "Ballon d'Or"
            b_df["Total Ballon d'Ors"] = b_df.apply(
                lambda r: f"{get_ordinal(get_total_titles_up_to(active_archive_id, b_award_name, r['Winner'], r['id']))} Win", axis=1
            )
            display_b = b_df[['Year', 'Winner', 'Positions', 'Club', 'Nation', "Total Ballon d'Ors"]]
            display_b = clean_dataframe(display_b)
            st.dataframe(display_b, use_container_width=True, hide_index=True)
        else:
            st.info("No Ballon d'Or winners logged yet.")

# ------------------------------------------
# PAGE 6: TIMELINE & KEY EVENTS
# ------------------------------------------
with p6:
    st.header("📖 Career Timeline & Narrative Events")
    col_t1, col_t2 = st.columns([1.2, 2])
    
    if "t_season" not in st.session_state:
        st.session_state["t_season"] = get_next_competition_year(active_archive_id, active_start_year, "Timeline", is_slash=True)
    if "t_details" not in st.session_state:
        st.session_state["t_details"] = ""

    def add_timeline_callback():
        details = st.session_state.get("t_details", "").strip()
        curr_season = st.session_state.get("t_season")
        if details:
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO timeline_logs (archive_id, season, category, event_details) VALUES (?, ?, ?, ?)",
                      (active_archive_id, curr_season, "General", details))
            conn.commit()
            conn.close()
            
            st.session_state["t_season"] = increment_season_string(curr_season, years_to_add=1)
            st.session_state["t_details"] = ""

    with col_t1:
        st.subheader("Log Event / Storyline")
        st.text_input("Season / Year", key="t_season")
        st.text_area("Event Description & Notes", key="t_details")
        st.button("Add Event to Timeline", on_click=add_timeline_callback, use_container_width=True)

    with col_t2:
        st.subheader("Timeline Notebook")
        conn = get_connection()
        t_df = pd.read_sql_query(
            "SELECT season AS Season, event_details AS Description FROM timeline_logs WHERE archive_id=? ORDER BY id DESC",
            conn, params=(active_archive_id,)
        )
        conn.close()
        
        if not t_df.empty:
            t_df = clean_dataframe(t_df)
            st.dataframe(t_df, use_container_width=True, hide_index=True)
        else:
            st.info("No timeline events logged yet.")

# ------------------------------------------
# PAGE 7: ACTIVE SAVE DATA EDITOR
# ------------------------------------------
with p7:
    st.header(f"✏️ Active Save Data Editor ({selected_archive_name})")
    ed_tab1, ed_tab2, ed_tab3 = st.tabs(["Trophies Editor", "Ballon d'Or Editor", "Timeline Editor"])
    
    conn = get_connection()
    c = conn.cursor()
    
    with ed_tab1:
        st.subheader("Edit / Delete Trophy Log Rows")
        trophies_df = pd.read_sql_query("SELECT id, season, competition_type, sub_category, winner, runner_up, score FROM trophy_logs WHERE archive_id=?", conn, params=(active_archive_id,))
        if not trophies_df.empty:
            sel_row_id = st.selectbox("Select Record ID", options=trophies_df['id'].tolist(), format_func=lambda x: f"ID {x}: {trophies_df[trophies_df['id']==x]['competition_type'].values[0]} ({trophies_df[trophies_df['id']==x]['season'].values[0]}) - {trophies_df[trophies_df['id']==x]['winner'].values[0]}")
            row_data = trophies_df[trophies_df['id'] == sel_row_id].iloc[0]
            
            e_winner = st.text_input("Edit Winner", value=row_data['winner'])
            e_runner = st.text_input("Edit Runner-Up", value=str(row_data['runner_up'] or ''))
            e_score = st.text_input("Edit Score", value=str(row_data['score'] or ''))
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Update Trophy Record", use_container_width=True):
                    c.execute("UPDATE trophy_logs SET winner=?, runner_up=?, score=? WHERE id=?", (e_winner, e_runner, e_score, sel_row_id))
                    conn.commit()
                    st.success("Record updated!")
                    st.rerun()
            with c2:
                if st.button("🗑️ Delete Trophy Record", type="primary", use_container_width=True):
                    c.execute("DELETE FROM trophy_logs WHERE id=?", (sel_row_id,))
                    conn.commit()
                    st.success("Record deleted!")
                    st.rerun()
        else:
            st.info("No trophy records to edit.")

    with ed_tab2:
        st.subheader("Edit / Delete Ballon d'Or Rows")
        b_edit_df = pd.read_sql_query("SELECT id, year, player_name, positions, club, nation FROM ballon_dor_logs WHERE archive_id=?", conn, params=(active_archive_id,))
        if not b_edit_df.empty:
            sel_b_id = st.selectbox("Select Ballon d'Or ID", options=b_edit_df['id'].tolist(), format_func=lambda x: f"ID {x}: {b_edit_df[b_edit_df['id']==x]['year'].values[0]} - {b_edit_df[b_edit_df['id']==x]['player_name'].values[0]}")
            brow_data = b_edit_df[b_edit_df['id'] == sel_b_id].iloc[0]
            
            eb_player = st.text_input("Edit Player Name", value=brow_data['player_name'])
            eb_club = st.text_input("Edit Club", value=brow_data['club'])
            eb_nation = st.text_input("Edit Nation", value=brow_data['nation'])
            
            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button("Update Ballon d'Or Record", use_container_width=True):
                    c.execute("UPDATE ballon_dor_logs SET player_name=?, club=?, nation=? WHERE id=?", (eb_player, eb_club, eb_nation, sel_b_id))
                    conn.commit()
                    st.success("Ballon d'Or record updated!")
                    st.rerun()
            with bc2:
                if st.button("🗑️ Delete Ballon d'Or Record", type="primary", use_container_width=True):
                    c.execute("DELETE FROM ballon_dor_logs WHERE id=?", (sel_b_id,))
                    conn.commit()
                    st.success("Record deleted!")
                    st.rerun()
        else:
            st.info("No Ballon d'Or records to edit.")

    with ed_tab3:
        st.subheader("Edit / Delete Timeline Rows")
        t_edit_df = pd.read_sql_query("SELECT id, season, event_details FROM timeline_logs WHERE archive_id=?", conn, params=(active_archive_id,))
        if not t_edit_df.empty:
            sel_t_id = st.selectbox("Select Timeline ID", options=t_edit_df['id'].tolist(), format_func=lambda x: f"ID {x}: {t_edit_df[t_edit_df['id']==x]['season'].values[0]}")
            trow_data = t_edit_df[t_edit_df['id'] == sel_t_id].iloc[0]
            
            et_season = st.text_input("Edit Season", value=trow_data['season'])
            et_details = st.text_area("Edit Event Details", value=trow_data['event_details'])
            
            tc1, tc2 = st.columns(2)
            with tc1:
                if st.button("Update Timeline Record", use_container_width=True):
                    c.execute("UPDATE timeline_logs SET season=?, event_details=? WHERE id=?", (et_season, et_details, sel_t_id))
                    conn.commit()
                    st.success("Timeline record updated!")
                    st.rerun()
            with tc2:
                if st.button("🗑️ Delete Timeline Record", type="primary", use_container_width=True):
                    c.execute("DELETE FROM timeline_logs WHERE id=?", (sel_t_id,))
                    conn.commit()
                    st.success("Record deleted!")
                    st.rerun()
        else:
            st.info("No timeline records to edit.")

    conn.close()