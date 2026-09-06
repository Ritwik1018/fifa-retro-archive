import streamlit as st
import sqlite3
import pandas as pd

# ==========================================
# 1. DATABASE INITIALIZATION & MIGRATION
# ==========================================
DB_FILE = "fifa_retro_archive.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Archives Table
    c.execute('''CREATE TABLE IF NOT EXISTS archives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    start_year INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')

    # Trophy Logs Table
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

    # Ballon d'Or Table
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

    # Timeline Logs Table
    c.execute('''CREATE TABLE IF NOT EXISTS timeline_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    archive_id INTEGER NOT NULL,
                    season TEXT NOT NULL,
                    category TEXT NOT NULL,
                    event_details TEXT NOT NULL,
                    FOREIGN KEY(archive_id) REFERENCES archives(id) ON DELETE CASCADE
                )''')

    # Schema Migrations
    c.execute("PRAGMA table_info(trophy_logs)")
    columns = [col[1] for col in c.fetchall()]
    if "third_place" not in columns:
        c.execute("ALTER TABLE trophy_logs ADD COLUMN third_place TEXT")
    if "host_nation" not in columns:
        c.execute("ALTER TABLE trophy_logs ADD COLUMN host_nation TEXT")

    # Seed Default Archive if empty
    c.execute("SELECT COUNT(*) FROM archives")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO archives (name, start_year) VALUES (?, ?)", ("Default Retro Career", 1998))
    
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. HELPER FUNCTIONS & DB OPERATIONS
# ==========================================
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_archives():
    conn = get_db()
    archives = conn.execute("SELECT * FROM archives ORDER BY created_at DESC").fetchall()
    conn.close()
    return archives

def add_archive(name, start_year):
    conn = get_db()
    try:
        conn.execute("INSERT INTO archives (name, start_year) VALUES (?, ?)", (name, start_year))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def generate_seasons(start_year, count=30):
    return [f"{start_year + i}/{str(start_year + i + 1)[-2:]}" for i in range(count)]

def generate_years(start_year, count=30):
    return [start_year + i for i in range(count)]

# ==========================================
# 3. STREAMLIT APP LAYOUT & CONFIG
# ==========================================
st.set_page_config(page_title="FIFA Retro Career Archive", page_icon="⚽", layout="wide")

st.title("⚽ FIFA Retro Career Mode Archive")

# Sidebar - Archive Selector & Management
st.sidebar.header("📁 Save File Manager")
archives = get_archives()
archive_names = [a["name"] for a in archives]

selected_archive_name = st.sidebar.selectbox("Select Active Save File", archive_names)
active_archive = next(a for a in archives if a["name"] == selected_archive_name)

st.sidebar.markdown("---")
with st.sidebar.expander("➕ Create New Save File"):
    new_name = st.text_input("Save File Name")
    new_start_year = st.number_input("Start Year", min_value=1990, max_value=2030, value=1998, step=1)
    if st.button("Create Save"):
        if new_name.strip():
            if add_archive(new_name.strip(), new_start_year):
                st.success("Save file created successfully!")
                st.rerun()
            else:
                st.error("A save file with this name already exists.")
        else:
            st.error("Please enter a valid save name.")

st.sidebar.info(f"**Active Save:** {active_archive['name']}\n\n**Start Year:** {active_archive['start_year']}")

# Data Options
COMPETITION_TYPES = [
    "Domestic Leagues", 
    "Domestic Cups", 
    "European Competitions", 
    "International Tournaments"
]

LEAGUE_OPTIONS = [
    "Premier League", "La Liga", "Serie A", "Bundesliga", 
    "Ligue 1", "Eredivisie", "Primeira Liga", "Custom/Other League"
]

CUP_OPTIONS = [
    "FA Cup", "EFL Cup", "Copa del Rey", "Coppa Italia", 
    "DFB-Pokal", "Coupe de France", "Custom/Other Domestic Cup"
]

EURO_OPTIONS = [
    "UEFA Champions League", "UEFA Europa League / UEFA Cup", 
    "UEFA Conference League", "UEFA Super Cup"
]

INTL_OPTIONS = [
    "FIFA World Cup", "UEFA European Championship (Euros)", 
    "Copa América", "AFC Asian Cup", "AFCON"
]

SEASONS = generate_seasons(active_archive["start_year"])
YEARS = generate_years(active_archive["start_year"])

# ==========================================
# 4. TAB NAVIGATION
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏆 Log Trophies", 
    "🥇 Ballon d'Or", 
    "📜 Timeline / Lore", 
    "📊 Career Database & Stats",
    "⚙️ Manage Logged Records"
])

# ------------------------------------------
# TAB 1: LOG TROPHIES
# ------------------------------------------
with tab1:
    st.header("🏆 Log Season Competition Result")
    
    col1, col2 = st.columns(2)
    with col1:
        comp_type = st.selectbox("Competition Category", COMPETITION_TYPES, key="t1_type")
        season = st.selectbox("Season", SEASONS, key="t1_season")
    
    with col2:
        if comp_type == "Domestic Leagues":
            sub_cat = st.selectbox("League Name", LEAGUE_OPTIONS)
        elif comp_type == "Domestic Cups":
            sub_cat = st.selectbox("Cup Name", CUP_OPTIONS)
        elif comp_type == "European Competitions":
            sub_cat = st.selectbox("Competition", EURO_OPTIONS)
        else:
            sub_cat = st.selectbox("Tournament", INTL_OPTIONS)

    st.markdown("---")
    
    with st.form("log_trophy_form", clear_on_submit=True):
        if comp_type == "Domestic Leagues":
            st.subheader(f"📊 {sub_cat} Record ({season})")
            winner = st.text_input("Champion (League Winner)*")
            runner_up = None
            score = None
            third_place = None
            host_nation = None

        elif comp_type == "Domestic Cups":
            st.subheader(f"🍷 {sub_cat} Record ({season})")
            c1, c2, c3 = st.columns(3)
            with c1:
                winner = st.text_input("Winner*")
            with c2:
                runner_up = st.text_input("Runner-Up")
            with c3:
                score = st.text_input("Final Score (e.g., 2-1 ET)")
            third_place = None
            host_nation = None

        elif comp_type == "European Competitions":
            st.subheader(f"🌍 {sub_cat} Record ({season})")
            c1, c2, c3 = st.columns(3)
            with c1:
                winner = st.text_input("Winner*")
            with c2:
                runner_up = st.text_input("Runner-Up")
            with c3:
                score = st.text_input("Final Score")
            third_place = None
            host_nation = None

        else: # International Tournaments
            st.subheader(f"🌐 {sub_cat} Record ({season})")
            c1, c2 = st.columns(2)
            with c1:
                winner = st.text_input("Champion (Winner)*")
                runner_up = st.text_input("Runner-Up")
            with c2:
                third_place = st.text_input("Third Place / Semi-Finalist")
                host_nation = st.text_input("Host Nation(s)")
            score = st.text_input("Final Score")

        submit_trophy = st.form_submit_button("Save Trophy Record")
        
        if submit_trophy:
            if not winner.strip():
                st.error("Please provide the Winner/Champion name.")
            else:
                conn = get_db()
                conn.execute('''INSERT INTO trophy_logs 
                                (archive_id, season, competition_type, sub_category, winner, runner_up, score, third_place, host_nation) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                             (active_archive["id"], season, comp_type, sub_cat, winner.strip(), 
                              runner_up.strip() if runner_up else None, 
                              score.strip() if score else None, 
                              third_place.strip() if third_place else None, 
                              host_nation.strip() if host_nation else None))
                conn.commit()
                conn.close()
                st.success(f"Successfully logged {sub_cat} ({season})!")

# ------------------------------------------
# TAB 2: BALLON D'OR
# ------------------------------------------
with tab2:
    st.header("🥇 Log Ballon d'Or Winner")
    
    with st.form("ballon_dor_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            bd_year = st.selectbox("Year", YEARS, key="bd_year")
            player_name = st.text_input("Player Name*")
            positions = st.text_input("Position(s) (e.g., ST, RW, CAM)")
        with c2:
            club = st.text_input("Club")
            nation = st.text_input("Nationality")
            
        submit_bd = st.form_submit_button("Save Ballon d'Or Winner")
        if submit_bd:
            if not player_name.strip():
                st.error("Please enter the Player Name.")
            else:
                conn = get_db()
                conn.execute('''INSERT INTO ballon_dor_logs 
                                (archive_id, year, player_name, positions, club, nation) 
                                VALUES (?, ?, ?, ?, ?, ?)''',
                             (active_archive["id"], bd_year, player_name.strip(), 
                              positions.strip() if positions else None, 
                              club.strip() if club else None, 
                              nation.strip() if nation else None))
                conn.commit()
                conn.close()
                st.success(f"Logged {player_name} as {bd_year} Ballon d'Or winner!")

# ------------------------------------------
# TAB 3: TIMELINE & LORE
# ------------------------------------------
with tab3:
    st.header("📜 Log Career Timeline & Key Events")
    
    with st.form("timeline_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            tl_season = st.selectbox("Season", SEASONS, key="tl_season")
        with c2:
            category = st.selectbox("Event Category", [
                "Managerial Move", 
                "Major Transfer", 
                "Icon Retirement", 
                "Record Broken", 
                "Club Milestone / Drama", 
                "Other Storyline"
            ])
        
        event_details = st.text_area("Event Description / Storyline*", placeholder="e.g. Zinedine Zidane retired. Signed Thierry Henry from Arsenal for £32M.")
        
        submit_tl = st.form_submit_button("Log Timeline Event")
        if submit_tl:
            if not event_details.strip():
                st.error("Please enter event details.")
            else:
                conn = get_db()
                conn.execute('''INSERT INTO timeline_logs 
                                (archive_id, season, category, event_details) 
                                VALUES (?, ?, ?, ?)''',
                             (active_archive["id"], tl_season, category, event_details.strip()))
                conn.commit()
                conn.close()
                st.success(f"Logged timeline event for {tl_season}!")

# ------------------------------------------
# TAB 4: CAREER DATABASE & STATS
# ------------------------------------------
with tab4:
    st.header(f"📊 Archive Explorer - {active_archive['name']}")
    
    view_option = st.radio("Select View", ["Trophy History", "Ballon d'Or History", "Career Timeline"], horizontal=True)
    
    conn = get_db()
    
    if view_option == "Trophy History":
        df_trophies = pd.read_sql_query(
            "SELECT season, competition_type, sub_category, winner, runner_up, score, third_place, host_nation FROM trophy_logs WHERE archive_id = ? ORDER BY id DESC", 
            conn, params=(active_archive["id"],)
        )
        if df_trophies.empty:
            st.info("No trophy records logged yet.")
        else:
            filter_cat = st.multiselect("Filter Category", COMPETITION_TYPES, default=COMPETITION_TYPES)
            df_filtered = df_trophies[df_trophies['competition_type'].isin(filter_cat)]
            
            df_display = df_filtered.rename(columns={
                'season': 'Season',
                'competition_type': 'Category',
                'sub_category': 'Competition',
                'winner': 'Champion / Winner',
                'runner_up': 'Runner-Up',
                'score': 'Score',
                'third_place': '3rd Place',
                'host_nation': 'Host Nation'
            })
            
            st.dataframe(df_display, use_container_width=True)

    elif view_option == "Ballon d'Or History":
        df_bd = pd.read_sql_query(
            "SELECT year, player_name, positions, club, nation FROM ballon_dor_logs WHERE archive_id = ? ORDER BY year DESC", 
            conn, params=(active_archive["id"],)
        )
        if df_bd.empty:
            st.info("No Ballon d'Or winners logged yet.")
        else:
            df_bd.columns = ['Year', 'Winner', 'Positions', 'Club', 'Nation']
            st.dataframe(df_bd, use_container_width=True)

    else:
        df_tl = pd.read_sql_query(
            "SELECT season, category, event_details FROM timeline_logs WHERE archive_id = ? ORDER BY id DESC", 
            conn, params=(active_archive["id"],)
        )
        if df_tl.empty:
            st.info("No timeline events logged yet.")
        else:
            df_tl.columns = ['Season', 'Category', 'Event Details']
            st.dataframe(df_tl, use_container_width=True)
            
    conn.close()

# ------------------------------------------
# TAB 5: MANAGE & EDIT LOGGED RECORDS
# ------------------------------------------
with tab5:
    st.header("⚙️ Edit or Delete Existing Records")
    
    manage_category = st.selectbox("Select Record Type to Edit/Delete", ["Trophy Logs", "Ballon d'Or Logs", "Timeline Logs"])
    conn = get_db()
    
    if manage_category == "Trophy Logs":
        records = conn.execute("SELECT * FROM trophy_logs WHERE archive_id = ? ORDER BY id DESC", (active_archive["id"],)).fetchall()
        if not records:
            st.info("No trophy logs to edit.")
        else:
            options = {f"ID #{r['id']} | {r['season']} - {r['sub_category']} (Winner: {r['winner']})": r for r in records}
            selected_option = st.selectbox("Select Record to Manage", list(options.keys()))
            selected_record = options[selected_option]
            
            col_edit, col_del = st.columns([3, 1])
            with col_edit:
                with st.expander("✏️ Edit Selected Trophy Record"):
                    with st.form("edit_trophy_form"):
                        e_season = st.text_input("Season", value=selected_record["season"])
                        e_sub_cat = st.text_input("Competition Name", value=selected_record["sub_category"])
                        e_winner = st.text_input("Winner / Champion", value=selected_record["winner"])
                        
                        if selected_record["competition_type"] != "Domestic Leagues":
                            e_runner_up = st.text_input("Runner-Up", value=selected_record["runner_up"] or "")
                            e_score = st.text_input("Score", value=selected_record["score"] or "")
                        else:
                            e_runner_up = None
                            e_score = None

                        e_third = st.text_input("3rd Place", value=selected_record["third_place"] or "")
                        e_host = st.text_input("Host Nation", value=selected_record["host_nation"] or "")
                        
                        save_edit = st.form_submit_button("Update Record")
                        if save_edit:
                            conn.execute('''UPDATE trophy_logs SET season=?, sub_category=?, winner=?, runner_up=?, score=?, third_place=?, host_nation=? WHERE id=?''',
                                         (e_season, e_sub_cat, e_winner, e_runner_up, e_score, e_third, e_host, selected_record["id"]))
                            conn.commit()
                            st.success("Record updated successfully!")
                            st.rerun()

            with col_del:
                st.write(" ")
                st.write(" ")
                if st.button("❌ Delete Record", key="del_trophy"):
                    conn.execute("DELETE FROM trophy_logs WHERE id = ?", (selected_record["id"],))
                    conn.commit()
                    st.success("Record deleted.")
                    st.rerun()

    elif manage_category == "Ballon d'Or Logs":
        records = conn.execute("SELECT * FROM ballon_dor_logs WHERE archive_id = ? ORDER BY year DESC", (active_archive["id"],)).fetchall()
        if not records:
            st.info("No Ballon d'Or records to edit.")
        else:
            options = {f"ID #{r['id']} | {r['year']} - {r['player_name']} ({r['club']})": r for r in records}
            selected_option = st.selectbox("Select Record to Manage", list(options.keys()))
            selected_record = options[selected_option]
            
            col_edit, col_del = st.columns([3, 1])
            with col_edit:
                with st.expander("✏️ Edit Selected Ballon d'Or Record"):
                    with st.form("edit_bd_form"):
                        e_year = st.number_input("Year", value=selected_record["year"], step=1)
                        e_player = st.text_input("Player Name", value=selected_record["player_name"])
                        e_pos = st.text_input("Positions", value=selected_record["positions"] or "")
                        e_club = st.text_input("Club", value=selected_record["club"] or "")
                        e_nation = st.text_input("Nation", value=selected_record["nation"] or "")
                        
                        save_edit = st.form_submit_button("Update Record")
                        if save_edit:
                            conn.execute('''UPDATE ballon_dor_logs SET year=?, player_name=?, positions=?, club=?, nation=? WHERE id=?''',
                                         (e_year, e_player, e_pos, e_club, e_nation, selected_record["id"]))
                            conn.commit()
                            st.success("Record updated!")
                            st.rerun()

            with col_del:
                st.write(" ")
                st.write(" ")
                if st.button("❌ Delete Record", key="del_bd"):
                    conn.execute("DELETE FROM ballon_dor_logs WHERE id = ?", (selected_record["id"],))
                    conn.commit()
                    st.success("Record deleted.")
                    st.rerun()

    else: # Timeline Logs
        records = conn.execute("SELECT * FROM timeline_logs WHERE archive_id = ? ORDER BY id DESC", (active_archive["id"],)).fetchall()
        if not records:
            st.info("No timeline logs to edit.")
        else:
            options = {f"ID #{r['id']} | {r['season']} - {r['category']}": r for r in records}
            selected_option = st.selectbox("Select Record to Manage", list(options.keys()))
            selected_record = options[selected_option]
            
            col_edit, col_del = st.columns([3, 1])
            with col_edit:
                with st.expander("✏️ Edit Selected Timeline Record"):
                    with st.form("edit_tl_form"):
                        e_season = st.text_input("Season", value=selected_record["season"])
                        e_cat = st.text_input("Category", value=selected_record["category"])
                        e_details = st.text_area("Event Details", value=selected_record["event_details"])
                        
                        save_edit = st.form_submit_button("Update Record")
                        if save_edit:
                            conn.execute('''UPDATE timeline_logs SET season=?, category=?, event_details=? WHERE id=?''',
                                         (e_season, e_cat, e_details, selected_record["id"]))
                            conn.commit()
                            st.success("Record updated!")
                            st.rerun()

            with col_del:
                st.write(" ")
                st.write(" ")
                if st.button("❌ Delete Record", key="del_tl"):
                    conn.execute("DELETE FROM timeline_logs WHERE id = ?", (selected_record["id"],))
                    conn.commit()
                    st.success("Record deleted.")
                    st.rerun()

    conn.close()