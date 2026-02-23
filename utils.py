import os

import pandas as pd
import streamlit as st
from unidecode import unidecode

# Manual name mappings
NAME_MAPPING = {"Alex Sarr": "Alexandre Sarr", "Nic Claxton": "Nicolas Claxton"}

# Team Mapping (Inverted)
TEAM_ABBREVIATION_MAPPING = {
    "GS": "GSW",
    "NO": "NOP",
    "NY": "NYK",
    "PHL": "PHI",
    "PHO": "PHX",
    "SA": "SAS",
    "WAS": "WSH",
}


def get_player_stats_map(base_dir, filename):
    """
    Load the specified stats file and return a dictionary mapping player names to their stats.
    """
    try:
        # Construct path to the specific stats file
        # base_dir should be the directory where history_data resides
        file_path = os.path.join(base_dir, "history_data", filename)
        if not os.path.exists(file_path):
            st.error(f"Stats file not found: {file_path}")
            return {}

        df = pd.read_pickle(file_path)

        # Create a dictionary for quick lookup: Name -> Series (Stats)
        # Normalize keys: unidecode + lower + strip
        stats_map = {
            unidecode(name).lower().strip(): row
            for name, row in zip(df["PLAYER"], df.to_dict("records"))
        }
        return stats_map
    except Exception as e:
        st.error(f"Error loading stats file: {e}")
        return {}


def get_player_avg(player_name, s_map):
    lookup_name = player_name.strip()
    if lookup_name in NAME_MAPPING:
        lookup_name = NAME_MAPPING[lookup_name]
    lookup_key = unidecode(lookup_name).lower().strip()
    return s_map.get(lookup_key, {})


def get_team_schedule_data(team_obj, schedule_df):
    if schedule_df is None:
        return pd.DataFrame()
    roster_rows = []
    dates = schedule_df.index.tolist()
    for player in team_obj.roster:
        pro_team = player.proTeam
        sched_col = TEAM_ABBREVIATION_MAPPING.get(pro_team, pro_team)
        row = {"Player": player.name, "Pos": player.position, "Team": pro_team}

        # Check injury status
        is_out = player.injuryStatus == "OUT"

        if sched_col in schedule_df.columns:
            for date in dates:
                has_game = schedule_df.loc[date, sched_col]
                if has_game == 1:
                    # Default unchecked if player is OUT
                    row[date] = False if is_out else True
                else:
                    row[date] = None
        else:
            for date in dates:
                row[date] = None
        roster_rows.append(row)
    return pd.DataFrame(roster_rows)


def apply_batch_toggle(df, col_name, new_val):
    # Set all non-None values in the column to new_val
    for idx in df.index:
        curr = df.at[idx, col_name]
        if curr is not None:
            df.at[idx, col_name] = new_val
    return df


def calculate_projected_stats(
    edited_df, current_stats, s_map, desired_order, alias_mapping, schedule_df=None
):
    # projected_total = current + sum(player_avg * active_games)

    base_totals = {k: 0.0 for k in desired_order if k not in ["AFG%", "FT%"]}

    def get_curr(k):
        if k in current_stats:
            return current_stats[k].get("value", 0)
        elif k in alias_mapping.keys() and alias_mapping[k] in current_stats:
            return current_stats[alias_mapping[k]].get("value", 0)
        else:
            return 0.0

    for k in base_totals:
        base_totals[k] = get_curr(k)

    if not edited_df.empty:
        # Skip Row 0 (Status Row)
        df_players = edited_df.iloc[1:]

        date_cols = [
            c for c in df_players.columns if c not in ["Player", "Pos", "Team"]
        ]
        for index, row in df_players.iterrows():
            # Count active games
            games_active = 0

            # Determine team schedule column if validation is needed
            pro_team = row["Team"]
            sched_col = TEAM_ABBREVIATION_MAPPING.get(pro_team, pro_team)

            for d in date_cols:
                if row[d] is True:
                    # Validate against schedule if provided
                    if schedule_df is not None:
                        # Check if game exists on this date for this team
                        if sched_col in schedule_df.columns and d in schedule_df.index:
                            if schedule_df.loc[d, sched_col] == 1:
                                games_active += 1
                    else:
                        # Legacy behavior (trust the check) if no schedule passed
                        games_active += 1

            if games_active > 0:
                p_stats = get_player_avg(row["Player"], s_map)
                if p_stats:
                    for k in base_totals:
                        val = 0.0
                        if k in p_stats:
                            val = float(p_stats[k])
                        base_totals[k] += val * games_active

    # Aggregates
    fgm = base_totals.get("FGM", 0)
    fga = base_totals.get("FGA", 0)
    threepm = base_totals.get("3PM", 0)
    ftm = base_totals.get("FTM", 0)
    fta = base_totals.get("FTA", 0)

    afg_pct = (fgm + 0.5 * threepm) / fga if fga > 0 else 0.0
    ft_pct = ftm / fta if fta > 0 else 0.0

    final_stats = {}
    for k in desired_order:
        if k == "AFG%":
            final_stats[k] = f"{afg_pct * 100:.2f}%"
        elif k == "FT%":
            final_stats[k] = f"{ft_pct * 100:.2f}%"
        else:
            final_stats[k] = f"{base_totals.get(k, 0):.1f}"
    return final_stats


def enforce_no_game_constraints(edited_df, schedule_df):
    """
    Reverts checks on days with no game.
    Returns (cleaned_df, changed) tuple.
    """
    if schedule_df is None or edited_df.empty:
        return edited_df, False

    changed = False

    # Iterate over player rows (index 1 to end)
    # We skip row 0 (Daily Status) for individual enforcement as it's a control row.
    df_players = edited_df.iloc[1:]
    date_cols = [c for c in df_players.columns if c not in ["Player", "Pos", "Team"]]

    for idx in df_players.index:
        row = edited_df.loc[idx]
        pro_team = row["Team"]
        sched_col = TEAM_ABBREVIATION_MAPPING.get(pro_team, pro_team)

        for d in date_cols:
            val = row[d]
            # If user checked it (True), verify if it's valid
            if val is True:
                is_valid = False
                if sched_col in schedule_df.columns and d in schedule_df.index:
                    if schedule_df.loc[d, sched_col] == 1:
                        is_valid = True

                if not is_valid:
                    # Revert to None (unchecked/empty)
                    edited_df.at[idx, d] = None
                    changed = True

    return edited_df, changed


from datetime import datetime


def filter_future_columns(all_cols, current_date=None, season_year=2025):
    """
    Filter columns to show only future dates based on current_date.
    Returns list of column names.
    """
    if current_date is None:
        now_pt = pd.Timestamp.now(tz="US/Pacific")
        current_date = now_pt.date()

    date_cols = [c for c in all_cols if c not in ["Player", "Pos", "Team"]]
    future_cols = []

    for d_str in date_cols:
        try:
            # Parse header "Jan 26"
            parts = d_str.split()
            if len(parts) == 2:
                month_str, day_str = parts
                dt_temp = datetime.strptime(d_str, "%b %d")

                # Determine Year
                if dt_temp.month >= 10:
                    year = season_year - 1
                else:
                    year = season_year

                col_date = dt_temp.replace(year=year).date()

                if col_date >= current_date:
                    future_cols.append(d_str)
        except:
            future_cols.append(d_str)

    return future_cols


def prepare_comparison_data(t1_obj, t1_stats, t2_obj, t2_stats, desired_order, aliases):
    """
    Build a comparison DataFrame for two teams.
    """
    available_keys = list(t1_stats.keys()) if t1_stats else []

    t1_row = {}
    t2_row = {}

    for display_key in desired_order:
        # Determine API key
        api_key = display_key
        if display_key not in available_keys and display_key in aliases:
            if aliases[display_key] in available_keys:
                api_key = aliases[display_key]

        # Fetch values
        t1_val = t1_stats.get(api_key, {}).get("value", 0) if t1_stats else 0
        t2_val = t2_stats.get(api_key, {}).get("value", 0) if t2_stats else 0

        # Format values
        if display_key in ["AFG%", "FT%"]:
            t1_display = f"{t1_val * 100:.2f}%"
            t2_display = f"{t2_val * 100:.2f}%"
        else:
            t1_display = f"{int(t1_val)}"
            t2_display = f"{int(t2_val)}"

        t1_row[display_key] = t1_display
        t2_row[display_key] = t2_display

    # Create DataFrame
    df_matchup = pd.DataFrame(
        [t1_row, t2_row], index=[t1_obj.team_name, t2_obj.team_name]
    )
    return df_matchup


def prepare_roster_data(team, stats_map):
    """
    Build roster dataframe for a team.
    """
    roster_data = []
    for player in team.roster:
        player_info = {"Name": player.name}

        # Resolve Name
        lookup_name = player.name.strip()
        if lookup_name in NAME_MAPPING:
            lookup_name = NAME_MAPPING[lookup_name]
        lookup_key = unidecode(lookup_name).lower().strip()

        # Merge Stats
        if lookup_key in stats_map:
            stats = stats_map[lookup_key]
            for key, value in stats.items():
                if key not in ["PLAYER", "TEAM"]:
                    player_info[key] = value
        else:
            if stats_map:
                example_stats = next(iter(stats_map.values()))
                for key in example_stats:
                    if key not in ["PLAYER", "TEAM"]:
                        player_info[key] = 0
            else:
                player_info["Stats"] = "N/A"

        roster_data.append(player_info)

    return pd.DataFrame(roster_data) if roster_data else pd.DataFrame()


def calculate_projected_stats_simple(
    team_obj, schedule_df, stats_map, desired_order, alias_mapping
):
    """
    Calculate projected stats for a team without interactive editing.
    All non-OUT players are assumed to play all scheduled games.
    Returns a dict of raw numeric values (not formatted strings).
    """
    base_totals = {k: 0.0 for k in desired_order if k not in ["AFG%", "FT%"]}

    if schedule_df is None:
        return base_totals

    dates = schedule_df.index.tolist()

    for player in team_obj.roster:
        # Skip OUT players
        if player.injuryStatus == "OUT":
            continue

        pro_team = player.proTeam
        sched_col = TEAM_ABBREVIATION_MAPPING.get(pro_team, pro_team)

        # Count games
        games_active = 0
        if sched_col in schedule_df.columns:
            for d in dates:
                if schedule_df.loc[d, sched_col] == 1:
                    games_active += 1

        if games_active > 0:
            p_stats = get_player_avg(player.name, stats_map)
            if p_stats:
                for k in base_totals:
                    val = 0.0
                    # Check alias mapping
                    if k in p_stats:
                        val = float(p_stats[k])
                    elif k in alias_mapping and alias_mapping[k] in p_stats:
                        val = float(p_stats[alias_mapping[k]])
                    base_totals[k] += val * games_active

    # Compute derived stats
    fgm = base_totals.get("FGM", 0)
    fga = base_totals.get("FGA", 0)
    threepm = base_totals.get("3PM", 0)
    ftm = base_totals.get("FTM", 0)
    fta = base_totals.get("FTA", 0)

    result = dict(base_totals)
    result["AFG%"] = (fgm + 0.5 * threepm) / fga if fga > 0 else 0.0
    result["FT%"] = ftm / fta if fta > 0 else 0.0

    return result
