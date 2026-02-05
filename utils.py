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
