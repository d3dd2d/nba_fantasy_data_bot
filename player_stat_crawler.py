import argparse
import json
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

cookie_str = r'[ { "domain": ".hashtagbasketball.com", "expirationDate": 1776365782, "hostOnly": false, "httpOnly": false, "name": "__eoi", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": "0", "value": "ID=63b11be335db3fe6:T=1760813782:RT=1767198145:S=AA-AfjbGrpA_qs6gq3KJPBN03vA0", "id": 1 }, { "domain": ".hashtagbasketball.com", "expirationDate": 1794509782, "hostOnly": false, "httpOnly": false, "name": "__gads", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": "0", "value": "ID=a0c0b194fb1c3895:T=1760813782:RT=1767198145:S=ALNI_MapL3Bxn94tUIzldmWSx3P4_KNKNA", "id": 2 }, { "domain": ".hashtagbasketball.com", "expirationDate": 1794509782, "hostOnly": false, "httpOnly": false, "name": "__gpi", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": "0", "value": "UID=000012b418db412d:T=1760813782:RT=1767198145:S=ALNI_MYu9dd2UNHizSY1xbBnz2czkSlwtA", "id": 3 }, { "domain": ".hashtagbasketball.com", "expirationDate": 1790085930, "hostOnly": false, "httpOnly": false, "name": "_cc_id", "path": "/", "sameSite": "lax", "secure": false, "session": false, "storeId": "0", "value": "dd7377b2150beebf1c8aed872778e1f9", "id": 4 }, { "domain": ".hashtagbasketball.com", "expirationDate": 1801841962.014657, "hostOnly": false, "httpOnly": false, "name": "_ga", "path": "/", "sameSite": "unspecified", "secure": false, "session": false, "storeId": "0", "value": "GA1.1.791157268.1760813780", "id": 5 }, { "domain": ".hashtagbasketball.com", "expirationDate": 1801841962.0142, "hostOnly": false, "httpOnly": false, "name": "_ga_08GEFM06S7", "path": "/", "sameSite": "unspecified", "secure": false, "session": false, "storeId": "0", "value": "GS2.1.s1767281953$o68$g1$t1767281962$j51$l0$h0", "id": 6 }, { "domain": ".hashtagbasketball.com", "expirationDate": 1797936456, "hostOnly": false, "httpOnly": false, "name": "_pubCommonId", "path": "/", "sameSite": "lax", "secure": false, "session": false, "storeId": "0", "value": "cb5fdd48-7504-47d1-b7a6-3291f9a654fa", "id": 7 }, { "domain": ".hashtagbasketball.com", "expirationDate": 1797936456, "hostOnly": false, "httpOnly": false, "name": "_pubCommonId_cst", "path": "/", "sameSite": "lax", "secure": false, "session": false, "storeId": "0", "value": "eYeD6g%3D%3D", "id": 8 }, { "domain": ".hashtagbasketball.com", "expirationDate": 1800977959, "hostOnly": false, "httpOnly": false, "name": "_scor_uid", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": "0", "value": "e77b4bd2f5d646e4ac62f7ee16671ace", "id": 9 }, { "domain": ".hashtagbasketball.com", "expirationDate": 1800894148, "hostOnly": false, "httpOnly": false, "name": "cto_bundle", "path": "/", "sameSite": "unspecified", "secure": false, "session": false, "storeId": "0", "value": "793nCF96bFJudVdQeXhWQll2cUt4eUlNMngwU1haekJMeDBqS1VCSllwV0ZURm9RMndGbU10Y1JWZjdWcWh0TDA0TWl1YSUyRkdacVFicGxWQnclMkZrczFlTHZscUI1S1Q4R0txVUFWc0FOTFUlMkJ0NE9Jc09rcjB3ZE85QkZyTDZ2JTJCQTJWNk9Sd2VNQkU4NndEWDc2T2J4aHYxNlZvRm9aejZrM0h0OSUyQnU5eWlWJTJCSXZVMHclM0Q", "id": 10 }, { "domain": ".hashtagbasketball.com", "expirationDate": 1767362729, "hostOnly": false, "httpOnly": false, "name": "panoramaId", "path": "/", "sameSite": "lax", "secure": false, "session": false, "storeId": "0", "value": "c4fcba910c3bd0acff826830640416d539387c3c07163a6b13b9d7736dc81728", "id": 11 }, { "domain": ".hashtagbasketball.com", "expirationDate": 1767362729, "hostOnly": false, "httpOnly": false, "name": "panoramaId_expiry", "path": "/", "sameSite": "lax", "secure": false, "session": false, "storeId": "0", "value": "1767362729054", "id": 12 }, { "domain": "hashtagbasketball.com", "expirationDate": 1769873958, "hostOnly": true, "httpOnly": false, "name": "_lr_env_src_ats", "path": "/", "sameSite": "unspecified", "secure": false, "session": false, "storeId": "0", "value": "false", "id": 13 }, { "domain": "hashtagbasketball.com", "expirationDate": 1767285558, "hostOnly": true, "httpOnly": false, "name": "_lr_retry_request", "path": "/", "sameSite": "unspecified", "secure": false, "session": false, "storeId": "0", "value": "true", "id": 14 }, { "domain": "hashtagbasketball.com", "hostOnly": true, "httpOnly": true, "name": ".ASPXAUTH", "path": "/", "sameSite": "lax", "secure": false, "session": true, "storeId": "0", "value": "35704CC07BFA50EE938DF6F94654624BA14EF6B5FF209ABFE2FD9B374C2DAB3ED586715B10437DA388EFFA6BF16145E0C193DFD10D475F0B61CC274F356CB2867342021ECE2811CB97BE3D4176356B10473C2FC0756521647224B6DAC3D1A804F5E04C2125BCEC2780808D84BD99FE72BD569E11C4507114C06C91ADCE43AF3F7CC645B45DC9DE1EA5F91F5AEFEFE762AB90A1EF990385CCF550CCB7C1FC84DA", "id": 15 }, { "domain": "hashtagbasketball.com", "expirationDate": 1798817953.773343, "hostOnly": true, "httpOnly": false, "name": "am_gpp", "path": "/", "sameSite": "lax", "secure": false, "session": false, "storeId": "0", "value": "DBABzw~1---~BqgAAAAAAACA", "id": 16 }, { "domain": "hashtagbasketball.com", "expirationDate": 1798817953.773582, "hostOnly": true, "httpOnly": false, "name": "am_gpp_cmp_version", "path": "/", "sameSite": "lax", "secure": false, "session": false, "storeId": "0", "value": "v2test", "id": 17 }, { "domain": "hashtagbasketball.com", "expirationDate": 1798817960, "hostOnly": true, "httpOnly": false, "name": "am_tokens", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": "0", "value": "{%22mv_uuid%22:%22230eacc0-ac54-11f0-8c99-d7d27121c6f7%22%2C%22version%22:%22ap-v1%22}", "id": 18 }, { "domain": "hashtagbasketball.com", "expirationDate": 1798817959, "hostOnly": true, "httpOnly": false, "name": "am_tokens_ap-v1", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": "0", "value": "{%22mv_uuid%22:%22230eacc0-ac54-11f0-8c99-d7d27121c6f7%22%2C%22version%22:%22ap-v1%22}", "id": 19 }, { "domain": "hashtagbasketball.com", "hostOnly": true, "httpOnly": true, "name": "ASP.NET_SessionId", "path": "/", "sameSite": "lax", "secure": true, "session": true, "storeId": "0", "value": "y0an5pzxo4e5abvtksifdjfx", "id": 20 }, { "domain": "hashtagbasketball.com", "expirationDate": 1767311058, "hostOnly": true, "httpOnly": false, "name": "ccsid", "path": "/", "sameSite": "lax", "secure": false, "session": false, "storeId": "0", "value": "5a9fe8ec-8b24-4efc-8b52-2a58b4378518", "id": 21 }, { "domain": "hashtagbasketball.com", "expirationDate": 1775000358, "hostOnly": true, "httpOnly": false, "name": "ccuid", "path": "/", "sameSite": "lax", "secure": false, "session": false, "storeId": "0", "value": "465037b5-92c2-4242-9e34-6197e4596c08", "id": 22 }, { "domain": "hashtagbasketball.com", "expirationDate": 1767283754, "hostOnly": true, "httpOnly": false, "name": "growme_headless_version", "path": "/", "sameSite": "unspecified", "secure": false, "session": false, "storeId": "0", "value": "{\"name\":\"1.18.69\",\"version\":\"1.18.69\"}", "id": 23 } ]'

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
