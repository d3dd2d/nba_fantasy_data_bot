import os
import pandas as pd
import streamlit as st
from espn_api.basketball import League

from get_week_range import find_week_range
from utils import (
    TEAM_ABBREVIATION_MAPPING,
    apply_batch_toggle,
    build_added_player_schedule_rows,
    calculate_projected_stats,
    calculate_projected_stats_simple,
    enforce_no_game_constraints,
    filter_future_columns,
    get_all_player_names,
    get_player_stats_map,
    get_team_schedule_data,
    prepare_comparison_data,
    prepare_roster_data,
)

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
    files = [f for f in os.listdir(directory) if f.endswith(".pkl")]
    # Sort files to show newest first
    files.sort(reverse=True)
    return files


def show_history_data():
    st.header("History Data Viewer")

    # Define data directory relative to the script
    DATA_DIR = os.path.join(os.path.dirname(__file__), "history_data")

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
            st.dataframe(df, width="stretch")

        except Exception as e:
            st.error(f"Error loading file {selected_file}: {e}")


@st.cache_resource(ttl=3600)
def get_league():
    """Initialize and cache the ESPN League object to avoid repeated API calls."""
    return League(
        league_id=LEAGUE_ID, year=SEASON_YEAR, espn_s2=ESPN_S2_TOKEN, swid=SWID_TOKEN
    )


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
        selected_label = st.selectbox(
            "Select Stats Source:", list(stats_options.keys())
        )
        selected_stats_file = stats_options[selected_label]

        selected_team_name = st.selectbox("Select a Team:", list(team_map.keys()))

        if selected_team_name:
            team = team_map[selected_team_name]
            st.subheader(f"Roster: {team.team_name}")

            # Load stats map
            stats_map = get_player_stats_map(
                os.path.dirname(__file__), selected_stats_file
            )

            # Prepare roster data
            df_roster = prepare_roster_data(team, stats_map)

            if not df_roster.empty:
                st.dataframe(df_roster, width="stretch")
            else:
                st.info("This team has no players on the roster.")

    except Exception as e:
        st.error(f"Failed to fetch data from ESPN API: {e}")


def get_available_weeks():
    """Scan weekly_schedule folder for available weeks."""
    schedule_dir = os.path.join(os.path.dirname(__file__), "weekly_schedule")
    if not os.path.exists(schedule_dir):
        return []

    files = [
        f for f in os.listdir(schedule_dir) if f.startswith("w") and f.endswith(".pkl")
    ]
    # Sort by week number: w1, w2, ...
    files.sort(key=lambda x: int(x[1:-4]))
    return [f[:-4] for f in files]  # Return ['w1', 'w2'...]


def render_team_schedule_ui(
    team_obj, week_num, df_schedule, side_key, added_players=None, stats_map=None
):
    """
    Render schedule table for a team (Home/Away).
    Handles session state initialization, 'Daily Status' row logic, and updating.
    """
    st.write(f"**{team_obj.team_name} Schedule**")

    # helper from utils
    df_sched = get_team_schedule_data(team_obj, df_schedule)

    if df_sched.empty:
        return pd.DataFrame()  # Empty if no data

    # Stable Session State Key (no hash — we merge changes incrementally)
    ss_key = f"df_{side_key}_{week_num}_{team_obj.team_name}"
    added_key = f"added_{ss_key}"  # Track which players were previously added

    if ss_key not in st.session_state:
        # Initialize with Daily Status Row
        status_row = {"Player": " ⚡ DAILY STATUS", "Pos": "", "Team": ""}
        date_cols = [c for c in df_sched.columns if c not in ["Player", "Pos", "Team"]]
        for d in date_cols:
            status_row[d] = True if df_sched[d].notna().any() else None

        df_final = pd.concat([pd.DataFrame([status_row]), df_sched], ignore_index=True)
        st.session_state[ss_key] = df_final
        st.session_state[added_key] = []

    # Sync added players: remove old, append new
    current_added = list(added_players) if added_players else []
    prev_added = st.session_state.get(added_key, [])

    if current_added != prev_added:
        full_df = st.session_state[ss_key]

        # Remove previously added players (Pos == "ADD")
        full_df = full_df[full_df["Pos"] != "ADD"].reset_index(drop=True)

        # Append new added players
        if current_added and stats_map and df_schedule is not None:
            df_added = build_added_player_schedule_rows(
                current_added, stats_map, df_schedule
            )
            if not df_added.empty:
                full_df = pd.concat([full_df, df_added], ignore_index=True)

        st.session_state[ss_key] = full_df
        st.session_state[added_key] = current_added

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
    future_cols = filter_future_columns(
        st.session_state[ss_key].columns, current_date=None, season_year=SEASON_YEAR
    )

    # Define visible dataframe
    visible_cols = ["Player", "Team"] + future_cols
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
            "Team": st.column_config.TextColumn(disabled=True),
        },
        key=editor_key,
        height=height,
    )

    # Change Detection (Batch Toggle Logic)
    curr_row0 = edited_df.iloc[0]
    last_row0 = st.session_state[last_known_key].iloc[0]
    cols_changed = []
    date_cols = [c for c in edited_df.columns if c not in ["Player", "Pos", "Team"]]

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
    # Rerun if any change occurred to update UI and prevent reset
    if not edited_df.equals(df_visible) or cols_changed:
        st.session_state[ss_key] = full_df
        st.session_state[last_known_key] = full_df.copy()
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

    return edited_df


def show_matchup_results():
    st.header("Matchup Results")

    # Select Week
    weeks = get_available_weeks()
    if not weeks:
        st.warning("No weekly schedule files found.")
        return

    # Calculate Current PT Date & Defaults
    now_pt = pd.Timestamp.now(tz="US/Pacific")
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
            team_map = {team.team_name: team for team in teams}
            team_names = list(team_map.keys())

            # Layout: Two rows of radio buttons
            st.write("### Team 1")
            selected_team1 = st.radio(
                "Select Team 1:",
                team_names,
                index=0,
                horizontal=True,
                label_visibility="collapsed",
            )

            st.write("### Team 2")
            # Default to second team if possible
            default_idx = 1 if len(team_names) > 1 else 0
            selected_team2 = st.radio(
                "Select Team 2:",
                team_names,
                index=default_idx,
                horizontal=True,
                label_visibility="collapsed",
            )

            if selected_team1 and selected_team2:
                # 3. Fetch Matchups (Box Scores)
                # Use calculated scoring_period as requested
                box_scores = league.box_scores(
                    matchup_period=week_num, scoring_period=scoring_period
                )

                # Helper to find team data in box scores
                def get_team_data_from_box_scores(t_name, b_scores):
                    for matchup in b_scores:
                        if matchup.home_team.team_name == t_name:
                            return matchup.home_team, matchup.home_stats
                        if matchup.away_team.team_name == t_name:
                            return matchup.away_team, matchup.away_stats
                    return None, None

                t1_obj, t1_stats = get_team_data_from_box_scores(
                    selected_team1, box_scores
                )
                if not t1_obj:
                    # Fallback to general team object if not in box scores
                    t1_obj = team_map.get(selected_team1)
                    t1_stats = {}

                t2_obj, t2_stats = get_team_data_from_box_scores(
                    selected_team2, box_scores
                )
                if not t2_obj:
                    t2_obj = team_map.get(selected_team2)
                    t2_stats = {}

                # Proceed even if stats are empty (t1_obj/t2_obj strictly shouldn't be None due to selectbox)
                if t1_obj and t2_obj:
                    st.subheader(
                        f"Comparison: {t1_obj.team_name} vs {t2_obj.team_name}"
                    )

                    # Available keys (checking t1, assuming t2 has similar structure or handling gracefully)
                    available_keys = list(t1_stats.keys()) if t1_stats else []

                    # User desired order
                    desired_order = [
                        "AFG%",
                        "FT%",
                        "3PM",
                        "TREB",
                        "AST",
                        "STL",
                        "BLK",
                        "TO",
                        "PTS",
                        "FGM",
                        "FGA",
                        "FTM",
                        "FTA",
                    ]

                    # Map user 'Display Names' to potential 'API Keys'
                    aliases = {"TREB": "REB"}

                    # Build Comparison Table
                    df_matchup = prepare_comparison_data(
                        t1_obj, t1_stats, t2_obj, t2_stats, desired_order, aliases
                    )
                    st.table(df_matchup)

                    # Stats Source Selector
                    stats_options = {
                        "2026 stat.": "current_1.pkl",
                        "2026 proj.": "current_0.pkl",
                    }
                    selected_label = st.selectbox(
                        "Select Stats Source for Projections:",
                        list(stats_options.keys()),
                    )
                    stats_file = stats_options[selected_label]

                    # Placeholder for Prediction Stats
                    prediction_placeholder = st.empty()

                    # --- Roster & Schedule Section ---
                    st.markdown("---")
                    st.subheader("Prediction Calculator")
                    st.caption(
                        "選取未來預計會進行的比賽，預計不會上場的請取消勾選。\n\n數據更新時間為美西時間午夜12點。(16:00 UTC+8)"
                    )

                    # Load Stats for Projections
                    stats_map = get_player_stats_map(
                        os.path.dirname(__file__), stats_file
                    )

                    # Load Weekly Schedule
                    schedule_path = os.path.join(
                        os.path.dirname(__file__), "weekly_schedule", f"w{week_num}.pkl"
                    )
                    df_schedule = None
                    if os.path.exists(schedule_path):
                        df_schedule = pd.read_pickle(schedule_path)
                    else:
                        st.warning(f"Schedule file not found for Week {week_num}")

                    # --- Add Players + Schedule Tables ---
                    all_player_names = get_all_player_names(stats_map)

                    # Team 1: table first, multiselect below
                    t1_container = st.container()
                    added_t1 = st.multiselect(
                        f"Add players to {t1_obj.team_name}:",
                        all_player_names,
                        key="add_players_t1",
                    )
                    with t1_container:
                        edited_t1_df = render_team_schedule_ui(
                            t1_obj,
                            week_num,
                            df_schedule,
                            "team1",
                            added_players=added_t1,
                            stats_map=stats_map,
                        )

                    # Team 2: table first, multiselect below
                    t2_container = st.container()
                    added_t2 = st.multiselect(
                        f"Add players to {t2_obj.team_name}:",
                        all_player_names,
                        key="add_players_t2",
                    )
                    with t2_container:
                        edited_t2_df = render_team_schedule_ui(
                            t2_obj,
                            week_num,
                            df_schedule,
                            "team2",
                            added_players=added_t2,
                            stats_map=stats_map,
                        )

                    # --- Calculate Predictions ---
                    t1_proj = calculate_projected_stats(
                        edited_t1_df,
                        t1_stats if t1_stats else {},
                        stats_map,
                        desired_order,
                        aliases,
                        schedule_df=df_schedule,
                    )
                    t2_proj = calculate_projected_stats(
                        edited_t2_df,
                        t2_stats if t2_stats else {},
                        stats_map,
                        desired_order,
                        aliases,
                        schedule_df=df_schedule,
                    )

                    # --- Render Prediction Table (Transposed) ---
                    t1_proj_row = {}
                    t2_proj_row = {}
                    for k in desired_order:
                        t1_proj_row[k] = t1_proj.get(k, "-")
                        t2_proj_row[k] = t2_proj.get(k, "-")

                    df_pred = pd.DataFrame(
                        [t1_proj_row, t2_proj_row],
                        index=[t1_obj.team_name, t2_obj.team_name],
                    )

                    with prediction_placeholder.container():
                        st.markdown("---")
                        st.subheader("Prediction Stats (Final Projected)")
                        st.table(df_pred)

    except Exception as e:
        st.error(f"Error fetching matchup data: {e}")


def show_team_strength():
    st.header("Team Strength Evaluation")
    st.caption("預測你的隊伍在未來每週對上所有隊伍的表現")

    # Stat categories
    desired_order = [
        "AFG%",
        "FT%",
        "3PM",
        "TREB",
        "AST",
        "STL",
        "BLK",
        "TO",
        "PTS",
        "FGM",
        "FGA",
        "FTM",
        "FTA",
    ]
    aliases = {"TREB": "REB"}
    # TO is "lower is better"
    lower_is_better = {"TO"}

    # Stats source
    stats_options = {"2026 stat.": "current_1.pkl", "2026 proj.": "current_0.pkl"}
    selected_label = st.selectbox(
        "Select Stats Source:", list(stats_options.keys()), key="strength_stats"
    )
    stats_file = stats_options[selected_label]

    try:
        league = get_league()
        teams = league.teams
        if not teams:
            st.warning("No teams found.")
            return

        team_map = {team.team_name: team for team in teams}
        team_names = list(team_map.keys())

        # Select target team
        st.write("### Select Your Team")
        target_team_name = st.radio(
            "Target Team:",
            team_names,
            index=0,
            horizontal=True,
            label_visibility="collapsed",
            key="strength_target",
        )
        target_team = team_map[target_team_name]

        # Load stats
        stats_map = get_player_stats_map(os.path.dirname(__file__), stats_file)

        # Get available future weeks (w18+)
        weeks = get_available_weeks()
        future_weeks = [w for w in weeks if int(w[1:]) >= 18]

        if not future_weeks:
            st.warning("No schedule files found for w18 onwards.")
            return

        # Process each week
        for week_str in future_weeks:
            week_num = int(week_str[1:])
            schedule_path = os.path.join(
                os.path.dirname(__file__), "weekly_schedule", f"{week_str}.pkl"
            )
            if not os.path.exists(schedule_path):
                continue

            df_schedule = pd.read_pickle(schedule_path)

            st.markdown("---")
            st.subheader(f"Week {week_num}")

            # Calculate target team stats
            target_stats = calculate_projected_stats_simple(
                target_team, df_schedule, stats_map, desired_order, aliases
            )

            # Build rows: first row = target team (reference), then each opponent
            rows = []

            # Target team reference row
            target_row = {"Team": f"⭐ {target_team_name}"}
            for k in desired_order:
                val = target_stats.get(k, 0)
                if k in ["AFG%", "FT%"]:
                    target_row[k] = round(val * 100, 2)
                else:
                    target_row[k] = round(val, 1)
            target_row["Wins"] = "-"
            rows.append(target_row)

            # Opponent rows
            for opp_name in team_names:
                if opp_name == target_team_name:
                    continue
                opp_team = team_map[opp_name]
                opp_stats = calculate_projected_stats_simple(
                    opp_team, df_schedule, stats_map, desired_order, aliases
                )

                opp_row = {"Team": opp_name}
                wins = 0
                skip_for_wins = {"FGM", "FGA", "FTM", "FTA"}
                for k in desired_order:
                    t_val = target_stats.get(k, 0)
                    o_val = opp_stats.get(k, 0)
                    if k in ["AFG%", "FT%"]:
                        opp_row[k] = round(o_val * 100, 2)
                    else:
                        opp_row[k] = round(o_val, 1)

                    # Don't count hidden columns in wins
                    if k in skip_for_wins:
                        continue

                    # Determine win/loss for target team
                    if k in lower_is_better:
                        if t_val < o_val:
                            wins += 1
                    else:
                        if t_val > o_val:
                            wins += 1
                opp_row["Wins"] = str(wins)
                rows.append(opp_row)

            df_result = pd.DataFrame(rows)
            df_result = df_result.set_index("Team")

            # Hide detailed columns
            hide_cols = ["FGM", "FGA", "FTM", "FTA"]
            df_result = df_result.drop(
                columns=[c for c in hide_cols if c in df_result.columns]
            )

            # Apply styling: color cells based on W/L vs target
            def color_cells(df):
                styles = pd.DataFrame("", index=df.index, columns=df.columns)
                target_vals = df.iloc[0]  # Reference row

                for idx in df.index[1:]:  # Skip target row
                    for col in desired_order:
                        if col not in df.columns:
                            continue
                        t_val = target_vals[col]
                        o_val = df.at[idx, col]
                        try:
                            t_val = float(t_val)
                            o_val = float(o_val)
                        except (ValueError, TypeError):
                            continue

                        if col in lower_is_better:
                            if t_val < o_val:
                                styles.at[idx, col] = (
                                    "background-color: #2d6a2d; color: white"
                                )
                            elif t_val > o_val:
                                styles.at[idx, col] = (
                                    "background-color: #8b2020; color: white"
                                )
                        else:
                            if t_val > o_val:
                                styles.at[idx, col] = (
                                    "background-color: #2d6a2d; color: white"
                                )
                            elif t_val < o_val:
                                styles.at[idx, col] = (
                                    "background-color: #8b2020; color: white"
                                )

                # Style the Wins column
                if "Wins" in df.columns:
                    for idx in df.index[1:]:
                        val = df.at[idx, "Wins"]
                        try:
                            wins_val = int(val)
                            total = len(desired_order)
                            if wins_val > total / 2:
                                styles.at[idx, "Wins"] = (
                                    "background-color: #8b2020; color: white"
                                )
                            elif wins_val < total / 2:
                                styles.at[idx, "Wins"] = (
                                    "background-color: #2d6a2d; color: white"
                                )
                        except (ValueError, TypeError):
                            pass

                # Style target row (bold)
                for col in styles.columns:
                    styles.loc[styles.index[0], col] = (
                        "font-weight: bold; background-color: #1a3a5c; color: white"
                    )

                return styles

            styled_df = df_result.style.apply(color_cells, axis=None)
            st.dataframe(styled_df, width="stretch")

    except Exception as e:
        st.error(f"Error: {e}")


def main():
    st.set_page_config(page_title="Fantasy Data Bot", layout="wide")
    st.title("Cubist Fantasy")

    # Sidebar Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["Matchup Results", "Team Strength", "History Data", "Team Rosters"],
    )

    if page == "History Data":
        show_history_data()
    elif page == "Team Rosters":
        show_team_rosters()
    elif page == "Matchup Results":
        show_matchup_results()
    elif page == "Team Strength":
        show_team_strength()


if __name__ == "__main__":
    main()
