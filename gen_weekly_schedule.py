from datetime import datetime, timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup

cur_year = 2025
week_start = "1/26"
week_end = "2/1"
pkl_file_name = "w15"

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


def gen_date_list(start_date_str, end_date_str):
    start_year = cur_year if int(start_date_str.split("/")[0]) > 9 else cur_year + 1
    end_year = cur_year if int(end_date_str.split("/")[0]) > 9 else cur_year + 1
    start_date = datetime.strptime(f"{start_year}/{start_date_str}", "%Y/%m/%d")
    end_date = datetime.strptime(f"{end_year}/{end_date_str}", "%Y/%m/%d")

    date_list = []
    current_date = start_date
    while current_date <= end_date:
        formatted_date = current_date.strftime("%b %d").replace(" 0", " ")
        date_list.append(formatted_date)
        current_date += timedelta(days=1)

    return date_list


date_list = gen_date_list(week_start, week_end)

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}
schedule_table = pd.DataFrame(columns=team_id_dict.keys(), index=date_list)

for team_name, team_id in team_id_dict.items():
    url = f"https://www.nba.com/team/{team_id}/schedule"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")

        tbody = soup.find("tbody", class_="Crom_body__UYOcU")

        rows = tbody.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            cell_data = [cell.get_text(strip=True) for cell in cells]
            if cell_data[0] in date_list:
                schedule_table.loc[cell_data[0], team_name] = 1
    else:
        print(
            f"Failed to retrieve page, team: {team_name} ({team_id}), status code: {response.status_code}"
        )

schedule_table.fillna(0, inplace=True)
schedule_table.to_pickle(f".\\weekly_schedule\\{pkl_file_name}.pkl")
schedule_table.to_csv(f".\\weekly_schedule\\{pkl_file_name}.csv")
print(schedule_table)
