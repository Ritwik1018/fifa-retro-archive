import streamlit as st
import sqlite3
import pandas as pd
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

    # Safe Schema Migration for existing databases
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

    # Key Events / Timeline Logs
    c.execute('''CREATE TABLE IF NOT EXISTS timeline_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    archive_id INTEGER NOT NULL,
                    season TEXT NOT NULL,
                    category TEXT NOT NULL,
                    event_details TEXT NOT NULL,
                    FOREIGN KEY(archive_id) REFERENCES archives(id) ON DELETE CASCADE
                )''')

    # Seed Default Archive if empty
    c.execute("SELECT COUNT(*) FROM archives")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO archives (name, start_year) VALUES (?, ?)", ("Default 1998 Save", 1998))
    
    conn.commit()
    conn.close()

# Historical Baselines (Pre-1998/99)
BASELINES = {
    "World Cup": {"Brazil": 4, "Italy": 3, "Germany": 3, "Uruguay": 2, "Argentina": 2, "England": 1},
    "Euro": {"Germany": 3, "France": 1, "Netherlands": 1, "Denmark": 1, "Spain": 1, "Italy": 1, "Soviet Union": 1, "Czechoslovakia": 1},
    "Copa America": {"Argentina": 14, "Uruguay": 14, "Brazil": 5, "Paraguay": 2, "Peru": 2, "Bolivia": 1},
    "AFCON": {"Ghana": 4, "Egypt": 4, "Cameroon": 2, "Nigeria": 2, "DR Congo": 2, "Ivory Coast": 1, "South Africa": 1, "Morocco": 1, "Algeria": 1, "Ethiopia": 1, "Sudan": 1, "Congo": 1},
    "Asian Cup": {"Iran": 3, "Saudi Arabia": 3, "South Korea": 2, "Japan": 1, "Kuwait": 1, "Israel": 1},
    "Finalissima": {"France": 1, "Argentina": 1},
    "UCL": {
        "Real Madrid": 7, "AC Milan": 5, "Liverpool": 4, "Ajax": 4, "Bayern Munich": 3,
        "Inter Milan": 2, "Benfica": 2, "Nottingham Forest": 2, "Juventus": 2, "Porto": 1,
        "Manchester United": 1, "Aston Villa": 1, "Celtic": 1, "Feyenoord": 1, "Hamburger SV": 1,
        "Steaua Bucuresti": 1, "PSV Eindhoven": 1, "Red Star Belgrade": 1, "Barcelona": 1, "Marseille": 1, "Borussia Dortmund": 1
    },
    "EPL": {
        "Liverpool": 18, "Manchester United": 11, "Arsenal": 11, "Everton": 9, "Aston Villa": 7,
        "Sunderland": 6, "Newcastle United": 4, "Sheffield Wednesday": 4, "Blackburn Rovers": 3,
        "Huddersfield Town": 3, "Wolverhampton": 3, "Leeds United": 3, "Preston North End": 2,
        "Portsmouth": 2, "Burnley": 2, "Tottenham Hotspur": 2, "Manchester City": 2, "Derby County": 2,
        "Sheffield United": 1, "West Bromwich Albion": 1, "Chelsea": 1, "Ipswich Town": 1, "Nottingham Forest": 1
    },
    "La Liga": {
        "Real Madrid": 27, "Barcelona": 15, "Atletico Madrid": 9, "Athletic Bilbao": 8,
        "Valencia": 4, "Real Sociedad": 2, "Real Betis": 1, "Sevilla": 1
    },
    "Bundesliga": {
        "Bayern Munich": 14, "Nurnberg": 9, "Schalke 04": 7, "Hamburger SV": 6, "Borussia Dortmund": 5,
        "Borussia Monchengladbach": 5, "VfB Stuttgart": 4, "1. FC Kaiserslautern": 4, "Werder Bremen": 3,
        "1. FC Koln": 3, "Greuther Furth": 3, "VfB Leipzig": 3, "Hertha BSC": 2, "Dresdner SC": 2, "Hannover 96": 2,
        "Eintracht Frankfurt": 1, "TSV 1860 Munich": 1, "Eintracht Braunschweig": 1
    },
    "Serie A": {
        "Juventus": 25, "AC Milan": 15, "Inter Milan": 13, "Genoa": 9, "Bologna": 7, "Pro Vercelli": 7,
        "Torino": 7, "Roma": 2, "Napoli": 2, "Fiorentina": 2, "Lazio": 1, "Cagliari": 1, "Sampdoria": 1, "Hellas Verona": 1
    },
    "Ligue 1": {
        "Saint-Etienne": 10, "Marseille": 8, "Nantes": 7, "Monaco": 6, "Reims": 6, "Bordeaux": 4,
        "Nice": 4, "Paris Saint-Germain": 2, "Sochaux": 2, "Sete": 2, "Lille": 2, "Lens": 1, "Auxerre": 1, "Strasbourg": 1
    },
    "Ballon d'Or": {
        "Johan Cruyff": 3, "Michel Platini": 3, "Marco van Basten": 3, "Alfredo Di Stefano": 2,
        "Franz Beckenbauer": 2, "Kevin Keegan": 2, "Karl-Heinz Rummenigge": 2, "Ronaldo Nazario": 1,
        "Stanley Matthews": 1, "Raymond Kopa": 1, "Luis Suarez": 1, "Omar Sivori": 1, "Josef Masopust": 1,
        "Lev Yashin": 1, "Denis Law": 1, "Eusebio": 1, "Bobby Charlton": 1, "Florian Albert": 1,
        "George Best": 1, "Gianni Rivera": 1, "Gerd Muller": 1, "Oleg Blokhin": 1, "Allan Simonsen": 1,
        "Paolo Rossi": 1, "Igor Belanov": 1, "Ruud Gullit": 1, "Lothar Matthaus": 1, "Jean-Pierre Papin": 1,
        "Roberto Baggio": 1, "Hristo Stoichkov": 1, "George Weah": 1, "Matthias Sammer": 1, "Zinedine Zidane": 1
    }
}

# AUTO-INCREMENT HELPER FUNCTION
def increment_season_string(season_str):
    """
    Increments '2008/09' to '2009/10', '1998/99' to '1999/00', 
    or single year strings like '2008' to '2009'.
    """
    season_str = str(season_str).strip()
    match_slash = re.match(r"^(\d{4})/(\d{2})$", season_str)
    if match_slash:
        start_year = int(match_slash.group(1))
        next_start = start_year + 1
        next_end = (next_start + 1) % 100
        return f"{next_start}/{next_end:02d}"
    
    match_single = re.match(r"^(\d{4})$", season_str)
    if match_single:
        return str(int(match_single.group(1)) + 1)
        
    return season_str

# Ordinal Helper Function
def get_ordinal(n):
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"

def get_total_titles_up_to(archive_id, comp_key, winner_name, record_id, sub_cat=None):
    base_count = BASELINES.get(comp_key, {}).get(winner_name, 0)
    conn = get_connection()
    c = conn.cursor()
    
    if comp_key == "Ballon d'Or":
        c.execute("SELECT COUNT(*) FROM ballon_dor_logs WHERE archive_id=? AND player_name=? AND id <= ?", (archive_id, winner_name, record_id))
    else:
        if sub_cat:
            c.execute("SELECT COUNT(*) FROM trophy_logs WHERE archive_id=? AND competition_type=? AND sub_category=? AND winner=? AND id <= ?", 
                      (archive_id, comp_key, sub_cat, winner_name, record_id))
        else:
            c.execute("SELECT COUNT(*) FROM trophy_logs WHERE archive_id=? AND competition_type=? AND winner=? AND id <= ?", 
                      (archive_id, comp_key, winner_name, record_id))
            
    in_save_count = c.fetchone()[0]
    conn.close()
    return base_count + in_save_count

# ==========================================
# PAGE LAYOUT & HEADER CONTROLS
# ==========================================
st.set_page_config(page_title="FIFA Retro Archive Hub", layout="wide")
init_db()

st.title("⚽ FIFA RETRO ARCHIVE HUB")

# Fetch Archives
conn = get_connection()
archives_df = pd.read_sql_query("SELECT * FROM archives", conn)
conn.close()

archive_options = {row['name']: (row['id'], row['start_year']) for _, row in archives_df.iterrows()}

# TOP CONTROL STRIP
col_sel, col_new, col_sys = st.columns([3, 1.5, 2])

with col_sel:
    selected_archive_name = st.selectbox(
        "Active Save Archive",
        options=list(archive_options.keys()),
        index=0 if len(archive_options) > 0 else None,
        label_visibility="collapsed"
    )
    active_archive_id, active_start_year = archive_options[selected_archive_name]

# Callback for New Archive creation
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
    with st.popover("⚙️ SYSTEM MANAGER (App-Wide)"):
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
            confirm_del = st.checkbox(f"Confirm deletion of '{target_del_name}' and ALL its records?", key="chk_del_arch")
            if st.button("🗑️ Permanently Delete Archive", key="btn_del_arch", type="primary"):
                if confirm_del:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM archives WHERE id=?", (target_del_id,))
                    conn.commit()
                    conn.close()
                    st.success(f"Deleted '{target_del_name}'!")
                    st.rerun()
                else:
                    st.warning("Check the confirmation box first.")

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
            st.markdown("**Restore / Import Database**")
            uploaded_db = st.file_uploader("Upload a .db Backup File", type=["db"])
            if uploaded_db is not None:
                if st.button("Overwrite Current Database with Upload", type="primary"):
                    with open(DB_FILE, "wb") as f:
                        f.write(uploaded_db.getbuffer())
                    st.success("Database restored successfully!")
                    st.rerun()

st.caption(f"Currently Active: **{selected_archive_name}** | Baseline Era: **{active_start_year}**")
st.divider()

# ==========================================
# MAIN 6-PAGE CONTENT NAVIGATION
# ==========================================
p1, p2, p3, p4, p5, p6 = st.tabs([
    "1. International", 
    "2. Champions League", 
    "3. Domestic Leagues", 
    "4. Ballon d'Or", 
    "5. Timeline & Events", 
    "6. Active Save Data Editor"
])

# ------------------------------------------
# PAGE 1: INTERNATIONAL TOURNAMENTS
# ------------------------------------------
with p1:
    st.header("🏆 International Tournaments")
    
    col_entry, col_view = st.columns([1.2, 2])
    
    for k, d in [("intl_season", "1998"), ("intl_host", ""), ("intl_win", ""), ("intl_run", ""), ("intl_third", ""), ("intl_score", "2-1")]:
        if k not in st.session_state:
            st.session_state[k] = d

    def log_intl_callback():
        w = st.session_state.get("intl_win", "").strip()
        comp = st.session_state.get("intl_comp_select", "World Cup")
        curr_season = st.session_state.get("intl_season", "1998")
        
        if w:
            is_wc = (comp == "World Cup")
            is_finalissima = (comp == "Finalissima")
            
            host_val = st.session_state.get("intl_host", "").strip() if is_wc else None
            runner_val = st.session_state.get("intl_run", "").strip() if (is_wc or is_finalissima) else None
            third_val = st.session_state.get("intl_third", "").strip() if is_wc else None
            score_val = st.session_state.get("intl_score", "").strip() if (is_wc or is_finalissima) else None
            
            conn = get_connection()
            c = conn.cursor()
            c.execute('''INSERT INTO trophy_logs (archive_id, season, competition_type, winner, runner_up, score, third_place, host_nation)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                      (active_archive_id, curr_season, comp, w, runner_val, score_val, third_val, host_val))
            conn.commit()
            conn.close()
            
            # Increment season automatically
            st.session_state["intl_season"] = increment_season_string(curr_season)
            st.session_state["intl_host"] = ""
            st.session_state["intl_win"] = ""
            st.session_state["intl_run"] = ""
            st.session_state["intl_third"] = ""
            st.session_state["intl_score"] = "2-1"

    with col_entry:
        st.subheader("Log Tournament Result")
        selected_comp = st.selectbox("Tournament", ["World Cup", "Euro", "Copa America", "AFCON", "Asian Cup", "Finalissima"], key="intl_comp_select")
        st.text_input("Year / Season", key="intl_season")
        
        if selected_comp == "World Cup":
            st.text_input("Host Nation", key="intl_host")
            st.text_input("Champion", key="intl_win")
            st.text_input("Runner-Up", key="intl_run")
            st.text_input("3rd Place", key="intl_third")
            st.text_input("Final Scoreline", key="intl_score")
        elif selected_comp == "Finalissima":
            st.text_input("Winner / Champion", key="intl_win")
            st.text_input("Runner-Up", key="intl_run")
            st.text_input("Final Scoreline", key="intl_score")
        else:
            st.text_input("Champion", key="intl_win")
        
        st.button("Log International Result", on_click=log_intl_callback, use_container_width=True)

    with col_view:
        st.subheader(f"Recorded {selected_comp} History")
        conn = get_connection()
        intl_df = pd.read_sql_query(
            """SELECT id,
                      season AS Season, 
                      competition_type AS Tournament, 
                      host_nation AS Host,
                      winner AS Champion, 
                      runner_up AS 'Runner-Up', 
                      third_place AS '3rd Place',
                      score AS Score 
               FROM trophy_logs 
               WHERE archive_id=? 
                 AND competition_type = ? 
               ORDER BY id DESC""", 
            conn, params=(active_archive_id, selected_comp)
        )
        conn.close()
        
        if not intl_df.empty:
            intl_df['Total Titles'] = intl_df.apply(
                lambda r: f"{get_ordinal(get_total_titles_up_to(active_archive_id, r['Tournament'], r['Champion'], r['id']))} Title", axis=1
            )
            
            display_cols = ['Season', 'Champion', 'Total Titles']
            if intl_df['Host'].notna().any(): display_cols.append('Host')
            if intl_df['Runner-Up'].notna().any(): display_cols.append('Runner-Up')
            if intl_df['3rd Place'].notna().any(): display_cols.append('3rd Place')
            if intl_df['Score'].notna().any(): display_cols.append('Score')
            
            st.dataframe(intl_df[display_cols], use_container_width=True, hide_index=True)
        else:
            st.info(f"No {selected_comp} results logged yet in this save.")

# ------------------------------------------
# PAGE 2: UEFA CHAMPIONS LEAGUE
# ------------------------------------------
with p2:
    st.header("🇪🇺 UEFA Champions League")
    col_e2, col_v2 = st.columns([1.2, 2])
    
    for k, d in [("ucl_season", "1998/99"), ("ucl_win", ""), ("ucl_run", ""), ("ucl_score", "2-1")]:
        if k not in st.session_state:
            st.session_state[k] = d

    def log_ucl_callback():
        w = st.session_state.get("ucl_win", "").strip()
        curr_season = st.session_state.get("ucl_season", "1998/99")
        if w:
            conn = get_connection()
            c = conn.cursor()
            c.execute('''INSERT INTO trophy_logs (archive_id, season, competition_type, winner, runner_up, score)
                         VALUES (?, ?, 'UCL', ?, ?, ?)''', 
                      (active_archive_id, curr_season, w, st.session_state.get("ucl_run", "").strip(), st.session_state.get("ucl_score", "").strip()))
            conn.commit()
            conn.close()
            
            # Increment season automatically (e.g. 2008/09 -> 2009/10)
            st.session_state["ucl_season"] = increment_season_string(curr_season)
            st.session_state["ucl_win"] = ""
            st.session_state["ucl_run"] = ""
            st.session_state["ucl_score"] = "2-1"

    with col_e2:
        st.subheader("Log UCL Final")
        st.text_input("Season", key="ucl_season")
        st.text_input("UCL Champion", key="ucl_win")
        st.text_input("Runner-Up", key="ucl_run")
        st.text_input("Scoreline", key="ucl_score")
        
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
            display_ucl = ucl_df[['Season', 'Champion', 'Runner-Up', 'Score', 'Total Titles']]
            st.dataframe(display_ucl, use_container_width=True, hide_index=True)
        else:
            st.info("No Champions League results logged yet.")

# ------------------------------------------
# PAGE 3: DOMESTIC LEAGUES
# ------------------------------------------
with p3:
    st.header("⚽ Big Five Domestic Leagues")
    
    league_tabs = st.tabs(["🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "🇪🇸 La Liga", "🇩🇪 Bundesliga", "🇮🇹 Serie A", "🇫🇷 Ligue 1"])
    league_keys = ["EPL", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]
    
    def log_league_callback(l_key):
        s_k, w_k, r_k = f"s_{l_key}", f"w_{l_key}", f"r_{l_key}"
        w = st.session_state.get(w_k, "").strip()
        curr_season = st.session_state.get(s_k, "1998/99")
        if w:
            conn = get_connection()
            c = conn.cursor()
            c.execute('''INSERT INTO trophy_logs (archive_id, season, competition_type, sub_category, winner, runner_up)
                         VALUES (?, ?, 'Domestic League', ?, ?, ?)''',
                      (active_archive_id, curr_season, l_key, w, st.session_state.get(r_k, "").strip()))
            conn.commit()
            conn.close()
            
            # Increment season automatically
            st.session_state[s_k] = increment_season_string(curr_season)
            st.session_state[w_k] = ""
            st.session_state[r_k] = ""

    for tab, l_key in zip(league_tabs, league_keys):
        with tab:
            cl1, cl2 = st.columns([1.2, 2])
            
            s_k, w_k, r_k = f"s_{l_key}", f"w_{l_key}", f"r_{l_key}"
            if s_k not in st.session_state:
                st.session_state[s_k] = "1998/99"
            if w_k not in st.session_state:
                st.session_state[w_k] = ""
            if r_k not in st.session_state:
                st.session_state[r_k] = ""

            with cl1:
                st.subheader(f"Log {l_key} Winner")
                st.text_input("Season", key=s_k)
                st.text_input("League Champion", key=w_k)
                st.text_input("Runner-Up (Optional)", key=r_k)
                
                st.button(f"Log {l_key} Result", key=f"btn_{l_key}", on_click=log_league_callback, args=(l_key,), use_container_width=True)

            with cl2:
                st.subheader(f"{l_key} History Log")
                conn = get_connection()
                dom_df = pd.read_sql_query(
                    "SELECT id, season AS Season, winner AS Champion, runner_up AS 'Runner-Up' FROM trophy_logs WHERE archive_id=? AND competition_type='Domestic League' AND sub_category=? ORDER BY id DESC",
                    conn, params=(active_archive_id, l_key)
                )
                conn.close()
                
                if not dom_df.empty:
                    dom_df['Total Titles'] = dom_df.apply(
                        lambda r: f"{get_ordinal(get_total_titles_up_to(active_archive_id, l_key, r['Champion'], r['id'], sub_cat=l_key))} Title", axis=1
                    )
                    display_dom = dom_df[['Season', 'Champion', 'Runner-Up', 'Total Titles']]
                    st.dataframe(display_dom, use_container_width=True, hide_index=True)
                else:
                    st.info(f"No {l_key} titles logged yet.")

# ------------------------------------------
# PAGE 4: BALLON D'OR
# ------------------------------------------
with p4:
    st.header("🥇 Ballon d'Or Ledger")
    
    col_b1, col_b2 = st.columns([1.2, 2])
    
    for k, d in [("b_yr", 1999), ("b_play", ""), ("b_club", ""), ("b_nat", "")]:
        if k not in st.session_state:
            st.session_state[k] = d

    def log_ballon_callback():
        p = st.session_state.get("b_play", "").strip()
        curr_yr = st.session_state.get("b_yr", 1999)
        if p:
            pos_str = ", ".join(st.session_state.get("b_pos_select", ["ST"]))
            conn = get_connection()
            c = conn.cursor()
            c.execute('''INSERT INTO ballon_dor_logs (archive_id, year, player_name, positions, club, nation)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (active_archive_id, curr_yr, p, pos_str, st.session_state.get("b_club", "").strip(), st.session_state.get("b_nat", "").strip()))
            conn.commit()
            conn.close()
            
            # Increment year automatically
            st.session_state["b_yr"] = curr_yr + 1
            st.session_state["b_play"] = ""
            st.session_state["b_club"] = ""
            st.session_state["b_nat"] = ""

    with col_b1:
        st.subheader("Log Ballon d'Or Winner")
        st.number_input("Year", step=1, key="b_yr")
        st.text_input("Player Name", key="b_play")
        st.multiselect("Positions Played", ["ST", "CF", "RW", "LW", "AM", "CM", "DM", "CB", "LB", "RB", "GK"], default=["ST"], key="b_pos_select")
        st.text_input("Club", key="b_club")
        st.text_input("Nation", key="b_nat")
        
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
            st.dataframe(display_b, use_container_width=True, hide_index=True)
        else:
            st.info("No Ballon d'Or winners logged yet.")

# ------------------------------------------
# PAGE 5: TIMELINE & KEY EVENTS
# ------------------------------------------
with p5:
    st.header("📖 Career Timeline & Narrative Events")
    
    col_t1, col_t2 = st.columns([1.2, 2])
    
    if "t_season" not in st.session_state:
        st.session_state["t_season"] = "1998/99"
    if "t_details" not in st.session_state:
        st.session_state["t_details"] = ""

    def add_timeline_callback():
        details = st.session_state.get("t_details", "").strip()
        curr_season = st.session_state.get("t_season", "1998/99")
        if details:
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO timeline_logs (archive_id, season, category, event_details) VALUES (?, ?, ?, ?)",
                      (active_archive_id, curr_season, "General", details))
            conn.commit()
            conn.close()
            
            # Increment season automatically
            st.session_state["t_season"] = increment_season_string(curr_season)
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
            st.dataframe(t_df, use_container_width=True, hide_index=True)
        else:
            st.info("No timeline events logged yet.")

# ------------------------------------------
# PAGE 6: ACTIVE SAVE DATA EDITOR
# ------------------------------------------
with p6:
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
                    st.success("Ballon d'Or record deleted!")
                    st.rerun()
        else:
            st.info("No Ballon d'Or records to edit.")

    with ed_tab3:
        st.subheader("Edit / Delete Timeline Rows")
        t_edit_df = pd.read_sql_query("SELECT id, season, category, event_details FROM timeline_logs WHERE archive_id=?", conn, params=(active_archive_id,))
        if not t_edit_df.empty:
            sel_t_id = st.selectbox("Select Event ID", options=t_edit_df['id'].tolist(), format_func=lambda x: f"ID {x}: {t_edit_df[t_edit_df['id']==x]['season'].values[0]}")
            
            trow_data = t_edit_df[t_edit_df['id'] == sel_t_id].iloc[0]
            
            et_details = st.text_area("Edit Event Details", value=trow_data['event_details'])
            
            tc1, tc2 = st.columns(2)
            with tc1:
                if st.button("Update Event Record", use_container_width=True):
                    c.execute("UPDATE timeline_logs SET event_details=? WHERE id=?", (et_details, sel_t_id))
                    conn.commit()
                    st.success("Timeline record updated!")
                    st.rerun()
            with tc2:
                if st.button("🗑️ Delete Event Record", type="primary", use_container_width=True):
                    c.execute("DELETE FROM timeline_logs WHERE id=?", (sel_t_id,))
                    conn.commit()
                    st.success("Timeline record deleted!")
                    st.rerun()
        else:
            st.info("No timeline records to edit.")

    conn.close()