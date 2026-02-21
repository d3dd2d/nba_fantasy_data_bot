import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Import the schedule dictionary from get_week_range
# Assuming get_week_range.py is in the same directory
try:
    from get_week_range import schedule
except ImportError:
    print("Error: get_week_range.py not found.")
    sys.exit(1)

# Team IDs (Same as before)
team_id_dict = {
    "ATL": 1610612737,
    "BOS": 1610612738,
    "BKN": 1610612751,
    "CHA": 1610612766,
    "CHI": 1610612741,
    "CLE": 1610612739,
    "DAL": 1610612742,
    "DEN": 1610612743,
    "DET": 1610612765,
    "GSW": 1610612744,
    "HOU": 1610612745,
    "IND": 1610612754,
    "LAC": 1610612746,
    "LAL": 1610612747,
    "MEM": 1610612763,
    "MIA": 1610612748,
    "MIL": 1610612749,
    "MIN": 1610612750,
    "NOP": 1610612740,
    "NYK": 1610612752,
    "OKC": 1610612760,
    "ORL": 1610612753,
    "PHI": 1610612755,
    "PHX": 1610612756,
    "POR": 1610612757,
    "SAC": 1610612758,
    "SAS": 1610612759,
    "TOR": 1610612761,
    "UTA": 1610612762,
    "WSH": 1610612764,
}

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}


def gen_date_list_from_range(start_date, end_date):
    """Generate list of date strings formatted like 'Jan 26'."""
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        # Format: "Jan 26" (Month Day)
        # Note: NBA site uses "Jan 1" not "Jan 01", so we strip leading zero if present
        # strftime %d is 01-31. To remove 0 on windows usually #, on linux -.
        # Making it platform independent string manip:
        month = current_date.strftime("%b")
        day = current_date.day  # integer, no leading zero
        formatted_date = f"{month} {day}"
        date_list.append(formatted_date)
        current_date += timedelta(days=1)
    return date_list


def scrape_week(week_name, start_date, end_date):
    print(f"Scraping {week_name} ({start_date.date()} to {end_date.date()})...")

    date_list = gen_date_list_from_range(start_date, end_date)
    schedule_table = pd.DataFrame(columns=team_id_dict.keys(), index=date_list)
    schedule_table = schedule_table.fillna(0)  # Init with 0

    for team_name, team_id in team_id_dict.items():
        url = f"https://www.nba.com/team/{team_id}/schedule"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                # Look for the specific table body class used in previous script
                tbody = soup.find("tbody", class_="Crom_body__UYOcU")

                if tbody:
                    rows = tbody.find_all("tr")
                    for row in rows:
                        cells = row.find_all("td")
                        if cells:
                            cell_data = [cell.get_text(strip=True) for cell in cells]
                            game_date_str = cell_data[0]

                            # Check if valid date format roughly (e.g. "Mon, Oct 20") - usually NBA site has "Oct 20" or "Mon Oct 20"
                            # The previous script looked for exact match in date_list.
                            # The NBA site format is typically "Day, Mon DD" or something.
                            # Previous script logic: cell_data[0] in date_list.
                            # We need to ensure we match the scraped string to our date_list format.
                            # Debug: The previous script generated date_list like "Oct 20" and checked exact match.

                            # Let's clean the cell data to match our format "MMM D"
                            # Attempt to find if our generated date exists in the cell string
                            for d in date_list:
                                if d == game_date_str:
                                    schedule_table.loc[d, team_name] = 1
                                    break
                else:
                    print(f"  Warning: Table body not found for {team_name}")
            else:
                print(f"  Failed: {team_name} ({response.status_code})")
        except Exception as e:
            print(f"  Error {team_name}: {e}")

    # Ensure output dir exists
    out_dir = os.path.join(os.path.dirname(__file__), "weekly_schedule")
    os.makedirs(out_dir, exist_ok=True)

    pkl_path = os.path.join(out_dir, f"{week_name}.pkl")
    schedule_table.to_pickle(pkl_path)
    print(f"  Saved {pkl_path}")
    return schedule_table


import argparse


def run_all_weeks():
    print("Generating schedules for ALL weeks...")
    # Sort keys to process in order w1, w2, ...
    sorted_weeks = sorted(schedule.keys(), key=lambda x: int(x[1:]))
    for week_name in sorted_weeks:
        start_date, end_date = schedule[week_name]
        scrape_week(week_name, start_date, end_date)


def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly schedule for a specific week or all weeks."
    )
    parser.add_argument(
        "-w",
        "--week",
        type=str,
        required=True,
        help="Week number (e.g., '17', 'w17', or 'all')",
    )
    args = parser.parse_args()

    if args.week.lower() == "all":
        run_all_weeks()
    else:
        # Normalize input "17" -> "w17"
        week_input = args.week if args.week.startswith("w") else f"w{args.week}"

        if week_input not in schedule:
            print(f"Error: Week '{week_input}' not found in schedule config.")
            print(f"Available weeks: {', '.join(list(schedule.keys())[:5])}...")
            sys.exit(1)

        print(f"Generating schedule for {week_input}...")
        start_date, end_date = schedule[week_input]
        scrape_week(week_input, start_date, end_date)


if __name__ == "__main__":
    main()
