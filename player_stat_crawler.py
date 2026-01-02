import argparse
import json
import os
import time

import pandas as pd
from selenium import webdriver  # type: ignore
from selenium.webdriver.chrome.options import Options  # type: ignore
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.support.ui import Select  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from unidecode import unidecode  # type: ignore


def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-t', '--data-type', 
        type=int, 
        default=1, 
        help='data type (default: 1, can be [0, 1, 7, 14, 30])'
    )

    parser.add_argument(
        '-d', '--date', 
        type=str, 
        default=20260000, 
        help='date in format like 20260101'
    )

    return parser.parse_args()

args = parse_arguments()


chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

cookie_str = os.getenv('FANTASY_HASHTAG_COOKIES')

# Reference data type, can be [0, 1, 7, 14, 30]
DATA_TYPE = args.data_type
DATE = args.date

def get_history_data(data_type):
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 10)
    driver.get("https://hashtagbasketball.com/import-v2/fantasy-basketball-rankings")
    try:
        cookies = json.loads(cookie_str)
        for cookie in cookies:
            cookie_dict = {
                'name': cookie['name'],
                'value': cookie['value'],
                'domain': cookie.get('domain'), 
                'path': cookie.get('path', '/'),
            }
            driver.add_cookie(cookie_dict)
        
        print("import cookie success")
    except Exception as e:
        print(f"import cookie error: {e}")

    time.sleep(3)

    driver.get("https://hashtagbasketball.com/import-v2/fantasy-basketball-rankings")
    select_top_element = wait.until(
        EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_DDSHOW"))
    )
    select_top = Select(select_top_element)
    select_top.select_by_visible_text("All")

    select_source_element = wait.until(
        EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_DDPOSFROM"))
    )
    select_source = Select(select_source_element)
    select_source.select_by_visible_text("ESPN")

    select_range_element = wait.until(
        EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_DDDURATION"))
    )
    select_range = Select(select_range_element)
    select_range.select_by_value(str(data_type))

    time.sleep(7)

    table = wait.until(
        EC.visibility_of_element_located((By.ID, "ContentPlaceHolder1_GridView1"))
    )

    headers = [th.text for th in table.find_elements(By.TAG_NAME, "th")]
    rows = table.find_elements(By.TAG_NAME, "tr")
    table_data = []
    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        row_data = [cell.text for cell in cells]
        # print(row_data)
        if row_data:
            table_data.append(row_data)
    stats_table = pd.DataFrame(table_data, columns=headers)
    stats_table = stats_table[stats_table["R#"] != "R#"].reset_index(drop=True)
    driver.quit()
    return stats_table


def format_history_data(stats_table):
    hist_scrape = stats_table[
        [
            "PLAYER",
            "TEAM",
            "FG%",
            "FT%",
            "3PM",
            "PTS",
            "TREB",
            "AST",
            "STL",
            "BLK",
            "TO",
        ]
    ].copy()
    hist_scrape[["FGM", "FGA"]] = (
        hist_scrape["FG%"].str.extract(r"\(([\d\.]+)/([\d\.]+)\)").astype(float)
    )
    hist_scrape[["FTM", "FTA"]] = (
        hist_scrape["FT%"].str.extract(r"\(([\d\.]+)/([\d\.]+)\)").astype(float)
    )
    stats_cols = [
        "FGM",
        "FGA",
        "FTM",
        "FTA",
        "3PM",
        "PTS",
        "TREB",
        "AST",
        "STL",
        "BLK",
        "TO",
    ]
    cols = ["PLAYER", "TEAM"] + stats_cols
    history_data = hist_scrape[cols].copy()
    history_data["PLAYER"] = history_data["PLAYER"].apply(unidecode)
    return history_data


def store_table(history_data, pkl_file_name):
    history_data.to_pickle(f".\\history_data\\{pkl_file_name}.pkl")
    history_data.to_csv(f".\\history_data\\{pkl_file_name}.csv")


if __name__ == "__main__":
    raw_table = get_history_data(DATA_TYPE)
    history_table = format_history_data(raw_table)
    store_table(history_table, f"{DATE}_{DATA_TYPE}")
