import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import math

import pandas as pd

# Load environment variables from the .env file
load_dotenv()
API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")


def get_raw_data(symbol):
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY_ADJUSTED&symbol={symbol}&apikey={API_KEY}"
    response = requests.get(url)
    data = response.json()
    data_for_df = data["Monthly Adjusted Time Series"]
    df = pd.DataFrame.from_dict(data_for_df, orient="index")
    return df



def clean_data(df):
    # update column names ('1. open' -> 'open')
    cols_with_numbers = df.columns
    cols_without_numbers = [" ".join(elem.split(" ")[1:]) for elem in cols_with_numbers]
    df.columns = cols_without_numbers

    # convert entries into numbers
    for col in cols_without_numbers:
        df[col] = pd.to_numeric(df[col])

    # set index (date) as column
    df.reset_index(inplace=True)
    df.rename(columns={"index": "date"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"])

    # calculate dividend percentage
    df["dividend"] = df["dividend amount"] / df["close"]

    # sort by date and set index as month number
    df.sort_values(by="date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    df.loc[:, "change"] = df["close"] / df["close"].shift(1)
    
    return df


def filter_data(df, filter_params):

    df_filtered = df.copy()

    if filter_params.get("start_date", None) is not None:
        # filter by date later start date, sort by date and set index as month number
        start_date = datetime.strptime(filter_params["start_date"], "%Y-%m")
        df_filtered = df_filtered.loc[df_filtered["date"] > start_date, :]
        df_filtered.reset_index(drop=True, inplace=True)
        df_filtered.reset_index(inplace=True)
        df_filtered.rename(columns={"index": "month_number"}, inplace=True)

    if filter_params.get("time_frame", None) is not None:
        start_date = datetime.now() - timedelta(days=365*filter_params["time_frame"])
        df_filtered = df_filtered.loc[df_filtered["date"] > start_date, :]
        df_filtered.reset_index(drop=True, inplace=True)
        df_filtered.reset_index(inplace=True)
        df_filtered.rename(columns={"index": "month_number"}, inplace=True)

    return df_filtered


def calculate_returns(df_filtered, start_money, regular_investments, dividend_reinvestment):

    df_calc = df_filtered.copy()

    # unpack regular investments
    monthly_money = regular_investments["monthly_money"]
    quarterly_money = regular_investments["quarterly_money"]
    bi_annual_money = regular_investments["bi_annual_money"]
    annual_money = regular_investments["annual_money"]

    # get initial investment buy value
    earliest_open = df_calc["date"].min()
    start_val = df_calc.loc[df_calc["date"] == earliest_open, "open"].iloc[0]

    # calculate sell values at the end of month
    df_calc.loc[:, "money"] = df_calc["close"] / start_val * start_money 
    df_calc.loc[:, "monthly_money"] = df_calc["close"] / df_calc["open"] * monthly_money
    df_calc.loc[0, "monthly_money"] = 0
    df_calc.loc[:, "quarterly_money"] = df_calc["close"] / df_calc["open"] * quarterly_money
    df_calc.loc[0, "quarterly_money"] = 0
    df_calc.loc[:, "bi_annual_money"] = df_calc["close"] / df_calc["open"] * bi_annual_money
    df_calc.loc[0, "bi_annual_money"] = 0
    df_calc.loc[:, "annual_money"] = df_calc["close"] / df_calc["open"] * annual_money
    df_calc.loc[0, "annual_money"] = 0
    # df_calc.loc[:, "change"] = df_calc["close"] / df_calc["close"].shift(1)

    df_calc.loc[0, "total"] = df_calc.loc[0, "money"]
    for i in range(1, len(df_calc)):

        # update regular investment amounts
        current_quarterly_money = quarterly_money
        current_bi_annual_money = bi_annual_money
        current_annual_money = annual_money

        if (i - 1) % 3 != 0:
            current_quarterly_money = 0
        if (i - 1) % 6 != 0:
            current_bi_annual_money = 0
        if (i - 1) % 12 != 0:
            current_annual_money = 0

        df_calc.loc[i, "annual_money"] = current_annual_money
        df_calc.loc[i, "bi_annual_money"] = current_bi_annual_money
        df_calc.loc[i, "quarterly_money"] = current_quarterly_money

        # calculate updated total amount based on value change and monthly investment
        df_calc.loc[i, "total"] = (
            df_calc.loc[i-1, "total"] * df_calc.loc[i, "change"] 
            + df_calc.loc[i, "monthly_money"]
            + df_calc.loc[i, "quarterly_money"]
            + df_calc.loc[i, "bi_annual_money"]
            + df_calc.loc[i, "annual_money"]
        )
        # calculate divident gain
        dividend_gain = df_calc.loc[i, "total"] * df_calc.loc[i, "dividend"]
        df_calc.loc[i, "dividend_gain"] = dividend_gain
        if dividend_reinvestment:
            df_calc.loc[i, "total"] += dividend_gain

        # calculate return
        df_calc.loc[i, "return"] = (
            df_calc.loc[i, "total"] / (
                df_calc.loc[i-1, "total"] 
                + df_calc.loc[i, "monthly_money"]
                + df_calc.loc[i, "quarterly_money"]
                + df_calc.loc[i, "bi_annual_money"]
                + df_calc.loc[i, "annual_money"]
            )
        )

    # calculate input
    df_calc.loc[:, "input"] = start_money
    df_calc = calculate_input_for_interval(df_calc, 12, annual_money, start_money)
    df_calc = calculate_input_for_interval(df_calc, 6, bi_annual_money, start_money)
    df_calc = calculate_input_for_interval(df_calc, 3, quarterly_money, start_money)
    df_calc = calculate_input_for_interval(df_calc, 1, monthly_money, start_money)

    return df_calc


def calculate_input_for_interval(df_calc, monthly_interval, amount, start_money):

    # add regular amount
    df_calc.loc[(df_calc["month_number"] - 1) % monthly_interval == 0, "input"] += (
        ((df_calc["month_number"] - 1) / monthly_interval + 1) * amount
    )
    # fill non investment months with input above
    for month in range(1, monthly_interval):
        df_calc.loc[(df_calc["month_number"] - 1) % monthly_interval == month, "input"] = df_calc["input"].shift(month)
    df_calc.loc[0, "input"] = start_money

    return df_calc


def get_summary(df_calc):
    final_amount = df_calc.loc[df_calc["date"] == df_calc["date"].max(), "total"].iloc[0]
    input_amount = df_calc.loc[df_calc["date"] == df_calc["date"].max(), "input"].iloc[0]
    total_dividend = sum(df_calc["dividend_gain"].iloc[1:])
    annual_return = (math.prod(df_calc.loc[1:, "return"].to_list()) ** (12/(len(df_calc) - 1)) - 1) * 100

    dict_out = {
        "final_amount": round(final_amount, 2),
        "input_amount": round(input_amount, 2),
        "total_yield_amount": round(final_amount - input_amount, 2),
        "total_yield_percent": round((final_amount - input_amount) / final_amount * 100, 2),
        "total_dividends": round(total_dividend, 2),
        "annual_return": round(annual_return, 2)
    }
    return dict_out


def get_general_summary(df):
    df_general_calc = df.copy()
    df_general_calc["return"] = df_general_calc["close"].pct_change() 

    general_monthly_volatility = df_general_calc["return"].std() * 100
    general_monthly_mean_return = df_general_calc["return"].mean() * 100
    general_annual_volatility = general_monthly_volatility * math.sqrt(12)
    general_annual_return = (
        (math.prod((df_general_calc.loc[1:, "return"] + 1).to_list()) ** (12/(len(df_general_calc) - 1)) - 1) * 100
    )
    general_mean_annual_dividends = df_general_calc["dividend"].mean() * 100 * 12

    general_summary = {
        "volatility_monthly": general_monthly_volatility,
        "volatility_annual": general_annual_volatility,
        "mean_return_monthly": general_monthly_mean_return,
        "annual_return": general_annual_return,
        "mean_dividend_yield_annual": general_mean_annual_dividends,
        "existent_years": round(len(df_general_calc) / 12, 2)
    }
    return general_summary


def past_stock_investment_outcome(params):

    try:
        # start_date_str = params["start_date"]
        time_frame = params["investment_time"]
        symbol = params["symbol"]
        start_money = params["initial_investment"]
    except KeyError as error:
        print("Missing arguments: ", error)
        print("received payload: ", params)
        raise error

    regular_investments = {
        "monthly_money": params.get("monthly_investment", 0),
        "quarterly_money": params.get("quarter_investment", 0),
        "bi_annual_money": params.get("bi_annual_investment", 0),
        "annual_money": params.get("annual_investment", 0)
    }
    dividend_reinvestment = params.get("dividend_reinvestment", True)

    df = get_raw_data(symbol)
    df = clean_data(df)
    df_filtered = filter_data(df, {"time_frame": time_frame})
    df_calc = calculate_returns(df_filtered, start_money, regular_investments, dividend_reinvestment)
    summary = get_summary(df_calc)
    general_summary = get_general_summary(df) 
    summary["general"] = general_summary
    summary["investment_time"] = time_frame

    outcome = {
        "data": df_calc,
        "summary": summary
    }

    return outcome


def save_summary(summary: dict, name: str, save_path: str, print_summary: bool = True, width = 40):

    col_widths = [int(width / 2) - 2, int(width / 2), 2] 

    summary_lines_header = [
        write_line("=", width),
        "".join([" " * int(width / 2 - len(name) / 2), name]),
        write_line("=", width),
    ]

    if summary.get("general", None) is not None:
        summary_lines_general_info = [
            "".join([" " * int(width / 2 - len("General Info") / 2), "General Info"]),
            write_line("-", width),
            write_table_line(["Annual Return", "{:.2f}".format(summary["general"]["annual_return"]), "%"], width, col_widths=col_widths),
            write_line("- ", width),
            write_table_line(["Volatility", "", ""], width, col_widths=col_widths),
            write_table_line(["   monthly", "{:.2f}".format(summary["general"]["volatility_monthly"]), "%"], width, col_widths=col_widths),
            write_table_line(["   annual", "{:.2f}".format(summary["general"]["volatility_annual"]), "%"], width, col_widths=col_widths),
            write_table_line(["Dividend Yield", "", ""], width, col_widths=col_widths),
            write_table_line(["   annual", "{:.2f}".format(summary["general"]["mean_dividend_yield_annual"]), "%"], width, col_widths=col_widths),
            write_line("- ", width),
            write_table_line(["Years assessed", "{:.2f}".format(summary["general"]["existent_years"]), ""], width, col_widths=col_widths),
            write_line("-", width)
        ]
    else:
        summary_lines_general_info = []

    summary_lines_outcome = [
        "".join([" " * int(width / 2 - len("Outcome") / 2), "Outcome"]),
        write_line("-", width),
        write_table_line(["Input", "{:.2f}".format(summary["input_amount"]), "$"], width, col_widths=col_widths),
        write_table_line(["Output", "{:.2f}".format(summary["final_amount"]), "$"], width, col_widths=col_widths),
        write_line("- ", width),
        write_table_line(["Yield", "", ""], width, col_widths=col_widths),
        write_table_line(["   total", "{:.2f}".format(summary['total_yield_amount']), "$"], width, col_widths=col_widths),
        write_table_line(["   total", "{:.2f}".format(summary['total_yield_percent']), "%"], width, col_widths=col_widths),
        write_table_line(["   dividend", "{:.2f}".format(summary['total_dividends']), "$"], width, col_widths=col_widths),
        write_line("- ", width),
        write_table_line(["Annual Return", "{:.2f}".format(summary['annual_return']), "%"], width, col_widths=col_widths),
        write_line("-", width),
        write_table_line(["Investment Years", "{:.2f}".format(summary['investment_time']), ""], width, col_widths=col_widths),
        write_line("-", width)
    ]

    summary_lines = summary_lines_header + summary_lines_general_info + summary_lines_outcome

    if print_summary:
        for line in summary_lines:
            print(line)
    
    with open(save_path, 'w') as outfile:
        outfile.write('\n'.join(str(i) for i in summary_lines))  


def write_line(symbol: str, table_width: int) -> str:
    """
    Return repetition of given `symbol`.

    Parameters
    ----------
    symbol : str
        String to be repeated.
    table_width : int
        Length of output string.

    Returns
    -------
    str
        A string composed of repititions of `symbol` with length `table_width`.

    """
    if type(symbol) != str:
        symbol = str(symbol)
    return symbol * int(table_width / len(symbol))


def write_table_line(cols: list, table_width: int, align: str = "right", col_widths: list = []) -> str:
    """
    Return a line of a table.

    Entries will be aligned and evenly spaced.

    Parameters
    ----------
    cols : list
        List of row entries.
    table_width : int
        Width of the table in characters.
    align : str, optional
        Alignment of the entries. 'right' - all entries, except the first one are
        right aligned. 'left' - all entries are left aligned. 'last_right' - only the
        last entry is right aligned, all others are left aligned. The default is 'right'.

    Returns
    -------
    str
        Line of a table with alignment according to `align` and width according
        to `table_width`.

    """
    columns = len(cols)
    if col_widths == []:
        col_width = [int(table_width / columns) for i in range(columns)]
    else:
        col_width = [int(table_width * col_widths[i] / sum(col_widths)) for i in range(columns)]

    line = ""

    if align == "right":
        for i in range(columns):
            if i == 0:
                line = (
                    line
                    + str(cols[i])
                    + " " * (col_width[i] + col_width[i + 1] - len(str(cols[i])) - len(str(cols[i + 1])))
                )
            elif i == columns - 1:
                line = line + str(cols[i])
            else:
                line = line + str(cols[i]) + " " * (col_width[i + 1] - len(str(cols[i + 1])))

    elif align == "left":
        for i in range(columns):
            if i == columns - 1:
                line = line + str(cols[i])
            else:
                line = line + str(cols[i]) + " " * (col_width[i] - len(str(cols[i])))

    elif align == "last_right":
        for i in range(columns):
            if i == columns - 2:
                line = (
                    line
                    + str(cols[i])
                    + " " * (col_width[i] + col_width[i + 1] - len(str(cols[i])) - len(str(cols[i + 1])))
                )
            elif i == columns - 1:
                line = line + str(cols[i])
            else:
                line = line + str(cols[i]) + " " * (col_width[i] - len(str(cols[i])))

    return line
