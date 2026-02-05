import pandas as pd

schedule = {
    "w1": (pd.to_datetime("2025-10-20"), pd.to_datetime("2025-10-26")),
    "w2": (pd.to_datetime("2025-10-27"), pd.to_datetime("2025-11-02")),
    "w3": (pd.to_datetime("2025-11-03"), pd.to_datetime("2025-11-09")),
    "w4": (pd.to_datetime("2025-11-10"), pd.to_datetime("2025-11-16")),
    "w5": (pd.to_datetime("2025-11-17"), pd.to_datetime("2025-11-23")),
    "w6": (pd.to_datetime("2025-11-24"), pd.to_datetime("2025-11-30")),
    "w7": (pd.to_datetime("2025-12-01"), pd.to_datetime("2025-12-07")),
    "w8": (pd.to_datetime("2025-12-08"), pd.to_datetime("2025-12-14")),
    "w9": (pd.to_datetime("2025-12-15"), pd.to_datetime("2025-12-21")),
    "w10": (pd.to_datetime("2025-12-22"), pd.to_datetime("2025-12-28")),
    "w11": (pd.to_datetime("2025-12-29"), pd.to_datetime("2026-01-04")),
    "w12": (pd.to_datetime("2026-01-05"), pd.to_datetime("2026-01-11")),
    "w13": (pd.to_datetime("2026-01-12"), pd.to_datetime("2026-01-18")),
    "w14": (pd.to_datetime("2026-01-19"), pd.to_datetime("2026-01-25")),
    "w15": (pd.to_datetime("2026-01-26"), pd.to_datetime("2026-02-01")),
    "w16": (pd.to_datetime("2026-02-02"), pd.to_datetime("2026-02-08")),
    "w17": (pd.to_datetime("2026-02-09"), pd.to_datetime("2026-02-22")),
    "w18": (pd.to_datetime("2026-02-23"), pd.to_datetime("2026-03-01")),
    "w19": (pd.to_datetime("2026-03-02"), pd.to_datetime("2026-03-08")),
    "w20": (pd.to_datetime("2026-03-09"), pd.to_datetime("2026-03-15")),
    "w21": (pd.to_datetime("2026-03-16"), pd.to_datetime("2026-03-29")),
    "w22": (pd.to_datetime("2026-03-30"), pd.to_datetime("2026-04-12")),
}


def find_week_range(date):
    if type(date) == str:
        date = pd.to_datetime(date)
    for week, (start, end) in schedule.items():
        if start <= date <= end:
            return week
    return None


def get_start_end_date(date):
    week = find_week_range(date)
    return schedule[week]
