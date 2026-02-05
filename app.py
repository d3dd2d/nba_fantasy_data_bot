import streamlit as st
import pandas as pd
import os
from espn_api.basketball import League
from unidecode import unidecode
from utils import (
    get_player_stats_map, 
    get_player_avg, 
    get_team_schedule_data, 
    apply_batch_toggle, 
    calculate_projected_stats,
    enforce_no_game_constraints,
    NAME_MAPPING,
    TEAM_ABBREVIATION_MAPPING
)
from get_week_range import find_week_range
from datetime import datetime

# Constants for ESPN API (Loaded from secrets)
LEAGUE_ID = st.secrets["LEAGUE_ID"]
SEASON_YEAR = st.secrets["SEASON_YEAR"]
ESPN_S2_TOKEN = st.secrets["ESPN_S2_TOKEN"]
SWID_TOKEN = st.secrets["SWID_TOKEN"]

def get_pickle_files(directory):
    """
    List all .pkl files in the given directory.
    """
    if not os.path.exists(directory):
        return []
    files = [f for f in os.listdir(directory) if f.endswith('.pkl')]
    # Sort files to show newest first
    files.sort(reverse=True) 
    return files

def show_history_data():
    st.header("History Data Viewer")
    
    # Define data directory relative to the script
    DATA_DIR = os.path.join(os.path.dirname(__file__), 'history_data')
    
    if not os.path.exists(DATA_DIR):
        st.error(f"Directory not found: {DATA_DIR}")
        return

    pkl_files = get_pickle_files(DATA_DIR)
    
    if not pkl_files:
        st.warning("No .pkl files found in history_data directory.")
        return

    selected_file = st.selectbox("Select a file to view:", pkl_files)

    if selected_file:
        file_path = os.path.join(DATA_DIR, selected_file)
        try:
            # Read pickle file
            df = pd.read_pickle(file_path)
            
            st.subheader(f"Data: {selected_file}")
            st.write(f"Shape: {df.shape}")
            
            # Display dataframe
            st.dataframe(df, width='stretch')
            
        except Exception as e:
            st.error(f"Error loading file {selected_file}: {e}")

@st.cache_resource(ttl=3600)
def get_league():
    """Initialize and cache the ESPN League object to avoid repeated API calls."""
    return League(league_id=LEAGUE_ID, year=SEASON_YEAR, espn_s2=ESPN_S2_TOKEN, swid=SWID_TOKEN)

def show_team_rosters():
    st.header("Team Rosters (ESPN Fantasy)")

    try:
        # Initialize League (cached)
        league = get_league()
        
        teams = league.teams
        if not teams:
            st.warning("No teams found in the league.")
            return
            
        # Create a dictionary for team selection
        team_map = {team.team_name: team for team in teams}

        # Stats Source Selector
        stats_options = {"2026 stat.": "current_1.pkl", "2026 proj.": "current_0.pkl"}
        selected_label = st.selectbox("Select Stats Source:", list(stats_options.keys()))
        selected_stats_file = stats_options[selected_label]
        
        selected_team_name = st.selectbox("Select a Team:", list(team_map.keys()))
        
        if selected_team_name:
            team = team_map[selected_team_name]
            st.subheader(f"Roster: {team.team_name}")
            
            # Load stats map
            stats_map = get_player_stats_map(os.path.dirname(__file__), selected_stats_file)
            
            # Prepare roster data
            roster_data = []
            for player in team.roster:
                # 1. Base Roster Info
                player_info = {
                    "Name": player.name,
                }
                
                # 2. Resolve Name for Stats Lookup
                # First, check manual mapping (using original name, stripped)
                lookup_name = player.name.strip()
                if lookup_name in NAME_MAPPING:
                    lookup_name = NAME_MAPPING[lookup_name]
                
                # Next, normalize for matching (unidecode, lower case)
                lookup_key = unidecode(lookup_name).lower().strip()
                
                # 3. Merge Stats
                if lookup_key in stats_map:
                    stats = stats_map[lookup_key]
                    # Exclude the 'PLAYER' and 'TEAM' columns from stats as we have them or don't need them duplicated
                    for key, value in stats.items():
                        if key not in ['PLAYER', 'TEAM']:
                            player_info[key] = value
                else:
                    # Fill 0 for missing players (columns from the dataframe if available, else standard set)
                    if stats_map:
                        example_stats = next(iter(stats_map.values()))
                        for key in example_stats:
                            if key not in ['PLAYER', 'TEAM']:
                                player_info[key] = 0
                    else:
                        player_info["Stats"] = "N/A"

                roster_data.append(player_info)
            
            if roster_data:
                df_roster = pd.DataFrame(roster_data)
                st.dataframe(df_roster, width='stretch')
            else:
                st.info("This team has no players on the roster.")

    except Exception as e:
        st.error(f"Failed to fetch data from ESPN API: {e}")

def get_available_weeks():
    """Scan weekly_schedule folder for available weeks."""
    schedule_dir = os.path.join(os.path.dirname(__file__), 'weekly_schedule')
    if not os.path.exists(schedule_dir):
        return []
    
    files = [f for f in os.listdir(schedule_dir) if f.startswith('w') and f.endswith('.pkl')]
    # Sort by week number: w1, w2, ...
    files.sort(key=lambda x: int(x[1:-4]))
    return [f[:-4] for f in files] # Return ['w1', 'w2'...]

def render_team_schedule_ui(team_obj, week_num, df_schedule, side_key):
    """
    Render schedule table for a team (Home/Away).
    Handles session state initialization, 'Daily Status' row logic, and updating.
    """
    st.write(f"**{team_obj.team_name} Schedule**")
    
    # helper from utils
    df_sched = get_team_schedule_data(team_obj, df_schedule)
    
    if df_sched.empty:
        return pd.DataFrame() # Empty if no data

    # Sesson State Key
    ss_key = f"df_{side_key}_{week_num}_{team_obj.team_name}"
    
    if ss_key not in st.session_state:
        # Initialize with Daily Status Row
        status_row = {"Player": " ⚡ DAILY STATUS", "Pos": "", "Team": ""}
        date_cols = [c for c in df_sched.columns if c not in ['Player', 'Pos', 'Team']]
        for d in date_cols:
            status_row[d] = True if df_sched[d].notna().any() else None
        
        df_final = pd.concat([pd.DataFrame([status_row]), df_sched], ignore_index=True)
        st.session_state[ss_key] = df_final

    # Last Known State (Shadow Copy) for diffing
    last_known_key = f"last_{ss_key}"
    if last_known_key not in st.session_state:
        st.session_state[last_known_key] = st.session_state[ss_key].copy()
    
    # Version Key for Cache Busting (Key Rotation)
    version_key = f"version_{ss_key}"
    if version_key not in st.session_state:
        st.session_state[version_key] = 0

    # Dynamic Height
    n_rows = len(st.session_state[ss_key])
    height = (n_rows + 1) * 35 + 3

    # Filter Columns: Hide Past Dates
    # Current PT Date
    now_pt = pd.Timestamp.now(tz='US/Pacific')
    current_date = now_pt.date()
    
    # Identify columns to show
    all_cols = st.session_state[ss_key].columns
    date_cols = [c for c in all_cols if c not in ['Player', 'Pos', 'Team']]
    
    future_cols = []
    for d_str in date_cols:
        try:
            # Parse header "Jan 26". Assume SEASON_YEAR logic.
            # Split month/day
            parts = d_str.split()
            if len(parts) == 2:
                month_str, day_str = parts
                # Simple mapping or datetime parse
                # 2026 Season: Oct-Dec=2025, Jan-Apr=2026
                dt_temp = datetime.strptime(d_str, "%b %d")
                
                # Determine Year
                if dt_temp.month >= 10:
                    year = SEASON_YEAR - 1
                else:
                    year = SEASON_YEAR
                
                col_date = dt_temp.replace(year=year).date()
                
                if col_date >= current_date:
                    future_cols.append(d_str)
        except:
             # If parse fails, keep it to be safe
             future_cols.append(d_str)

    # Define visible dataframe
    visible_cols = ['Player', 'Pos', 'Team'] + future_cols
    df_visible = st.session_state[ss_key][visible_cols]

    # Define editor key explicitly to control state
    # Use version to force re-render when needed
    editor_key = f"editor_{side_key}_{week_num}_v{st.session_state[version_key]}"
    
    # Render Editor
    edited_df = st.data_editor(
        df_visible, 
        hide_index=True, 
        column_config={
            "Player": st.column_config.TextColumn(disabled=True),
            "Pos": st.column_config.TextColumn(disabled=True),
            "Team": st.column_config.TextColumn(disabled=True)
        },
        key=editor_key,
        height=height
    )

    # Change Detection (Batch Toggle Logic)
    curr_row0 = edited_df.iloc[0]
    last_row0 = st.session_state[last_known_key].iloc[0]
    cols_changed = []
    date_cols = [c for c in edited_df.columns if c not in ['Player', 'Pos', 'Team']]
    
    for d in date_cols:
        if curr_row0[d] != last_row0[d]:
             # Apply Batch Toggle
             edited_df = apply_batch_toggle(edited_df, d, curr_row0[d])
             cols_changed.append(d)
    
    # Update Session State (Merge changes back to full DF)
    # We must allow the full df to persist, but update the modified columns
    full_df = st.session_state[ss_key].copy()
    for col in edited_df.columns:
        full_df[col] = edited_df[col]
    
    st.session_state[ss_key] = full_df
    
    # Update Last Known (for diffing next time)
    # We need to respect that visible cols might change day-to-day
    # But last_known should match the structure of next render??
    # Actually, simplest is to just sync it.
    st.session_state[last_known_key] = full_df.copy()

    # Rerun if programmatic change occurred to update UI
    if cols_changed:
        st.rerun()
    
    # Enforce No-Game Constraint (Active Reversion)
    # Pass ONLY visible portion or full? Enforce on full helps consistency.
    full_df, reverted = enforce_no_game_constraints(full_df, df_schedule)
    
    if reverted:
        st.session_state[ss_key] = full_df
        st.session_state[last_known_key] = full_df.copy()
        
        # Increment version to rotate key and force fresh render
        st.session_state[version_key] += 1
        
        st.toast("Cannot verify game: No game scheduled for this day.", icon="🚫")
        st.rerun()
        st.rerun()
        
    return edited_df

def show_matchup_results():
    st.header("Matchup Results")
    
    # Select Week
    weeks = get_available_weeks()
    if not weeks:
        st.warning("No weekly schedule files found.")
        return

    # Calculate Current PT Date & Defaults
    now_pt = pd.Timestamp.now(tz='US/Pacific')
    current_date = now_pt.date()
    season_start = pd.Timestamp("2025-10-20").date()
    
    # Calculate Scoring Period (Days since start)
    # User requested sp_num = date difference between current day and 2025/10/20
    scoring_period = (current_date - season_start).days
    
    # Identify Current Week
    # find_week_range generally expects a datetime or timestamp, let's pass the normalized timestamp or date
    # In get_week_range.py, it compares vs pd.to_datetime values. Safe to pass pd.Timestamp.
    current_week_str = find_week_range(pd.Timestamp(current_date))
    
    # Determine Default Index
    default_week_idx = 0
    if current_week_str in weeks:
        default_week_idx = weeks.index(current_week_str)
    elif weeks:
        # Fallback to last week if current not found (e.g. offseason or future)
        default_week_idx = len(weeks) - 1

    selected_week_str = st.selectbox("Select Week:", weeks, index=default_week_idx)
    week_num = int(selected_week_str[1:])
    
    try:
        # Initialize League (cached)
        league = get_league()
        
        if selected_week_str:
            # 2. Select Teams (Independent)
            # We need team list. League object has it.
            teams = league.teams
            team_names = [team.team_name for team in teams]
            
            col1, col2 = st.columns(2)
            with col1:
                selected_team1 = st.selectbox("Select Team 1:", team_names, index=0)
            with col2:
                # Default to second team if possible
                default_idx = 1 if len(team_names) > 1 else 0
                selected_team2 = st.selectbox("Select Team 2:", team_names, index=default_idx)
            
            if selected_team1 and selected_team2:
                # 3. Fetch Matchups (Box Scores)
                # Use calculated scoring_period as requested
                box_scores = league.box_scores(matchup_period=week_num, scoring_period=scoring_period)
                
                # Helper to find team data in box scores
                def get_team_data_from_box_scores(t_name, b_scores):
                    for matchup in b_scores:
                        if matchup.home_team.team_name == t_name:
                             return matchup.home_team, matchup.home_stats
                        if matchup.away_team.team_name == t_name:
                             return matchup.away_team, matchup.away_stats
                    return None, None

                t1_obj, t1_stats = get_team_data_from_box_scores(selected_team1, box_scores)
                t2_obj, t2_stats = get_team_data_from_box_scores(selected_team2, box_scores)
                
                if t1_obj and t2_obj:
                    st.subheader(f"Comparison: {t1_obj.team_name} vs {t2_obj.team_name}")
                    
                    # Available keys (checking t1, assuming t2 has similar structure or handling gracefully)
                    available_keys = list(t1_stats.keys()) if t1_stats else []
                    
                    # User desired order
                    desired_order = ['AFG%', 'FT%', '3PM', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'PTS', 'FGM', 'FGA', 'FTM', 'FTA']
                    
                    # Map user 'Display Names' to potential 'API Keys'
                    aliases = {'TREB': 'REB'}
                    
                    # Build Comparison Table
                    t1_row = {}
                    t2_row = {}
                    
                    for display_key in desired_order:
                        # Determine API key
                        api_key = display_key
                        if display_key not in available_keys and display_key in aliases:
                            if aliases[display_key] in available_keys:
                                api_key = aliases[display_key]
                        
                        # Fetch values (Handle None stats if future week)
                        t1_val = t1_stats.get(api_key, {}).get('value', 0) if t1_stats else 0
                        t2_val = t2_stats.get(api_key, {}).get('value', 0) if t2_stats else 0

                        # Format values
                        if display_key in ['AFG%', 'FT%']:
                            t1_display = f"{t1_val * 100:.2f}%"
                            t2_display = f"{t2_val * 100:.2f}%"
                        else:
                            t1_display = f"{int(t1_val)}"
                            t2_display = f"{int(t2_val)}"
                        
                        t1_row[display_key] = t1_display
                        t2_row[display_key] = t2_display
                    
                    # Create DataFrame
                    df_matchup = pd.DataFrame([t1_row, t2_row], index=[t1_obj.team_name, t2_obj.team_name])
                    st.table(df_matchup)
                    
                    # Stats Source Selector
                    stats_options = {"2026 stat.": "current_1.pkl", "2026 proj.": "current_0.pkl"}
                    selected_label = st.selectbox("Select Stats Source for Projections:", list(stats_options.keys()))
                    stats_file = stats_options[selected_label]

                    # Placeholder for Prediction Stats
                    prediction_placeholder = st.empty()

                    # --- Roster & Schedule Section ---
                    st.markdown("---")
                    st.subheader("Prediction Calculator")
                    st.caption("選取未來預計會進行的比賽，預計不會上場的請取消勾選。\n\n數據更新時間為美西時間午夜12點。(16:00 UTC+8)\n\n另外有時候按第一次框框會沒反應，請再按一次!")

                    # Load Stats for Projections
                    stats_map = get_player_stats_map(os.path.dirname(__file__), stats_file)
                    
                    # Load Weekly Schedule
                    schedule_path = os.path.join(os.path.dirname(__file__), 'weekly_schedule', f'w{week_num}.pkl')
                    df_schedule = None
                    if os.path.exists(schedule_path):
                        df_schedule = pd.read_pickle(schedule_path)
                    else:
                        st.warning(f"Schedule file not found for Week {week_num}")

                    # --- Process Teams (Unified Helper) ---
                    # Use unique keys for editors since teams can change
                    edited_t1_df = render_team_schedule_ui(t1_obj, week_num, df_schedule, "team1")
                    edited_t2_df = render_team_schedule_ui(t2_obj, week_num, df_schedule, "team2")

                    # --- Calculate Predictions ---
                    t1_proj = calculate_projected_stats(edited_t1_df, t1_stats if t1_stats else {}, stats_map, desired_order, aliases, schedule_df=df_schedule)
                    t2_proj = calculate_projected_stats(edited_t2_df, t2_stats if t2_stats else {}, stats_map, desired_order, aliases, schedule_df=df_schedule)
                    
                    # --- Render Prediction Table (Transposed) ---
                    t1_proj_row = {}
                    t2_proj_row = {}
                    for k in desired_order:
                        t1_proj_row[k] = t1_proj.get(k, "-")
                        t2_proj_row[k] = t2_proj.get(k, "-")
                    
                    df_pred = pd.DataFrame([t1_proj_row, t2_proj_row], index=[t1_obj.team_name, t2_obj.team_name])
                    
                    with prediction_placeholder.container():
                        st.markdown("---")
                        st.subheader("Prediction Stats (Final Projected)")
                        st.table(df_pred)
                
                else:
                     st.warning("Could not find data for one or both selected teams in this week's box scores.")

    except Exception as e:
        st.error(f"Error fetching matchup data: {e}")

def main():
    st.set_page_config(page_title="Fantasy Data Bot", layout="wide")
    st.title("Cubist Fantasy")

    # Sidebar Navigation
    page = st.sidebar.radio("Navigation", ["Matchup Results", "History Data", "Team Rosters"])

    if page == "History Data":
        show_history_data()
    elif page == "Team Rosters":
        show_team_rosters()
    elif page == "Matchup Results":
        show_matchup_results()

if __name__ == "__main__":
    main()
