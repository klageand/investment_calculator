import math

import pandas as pd

from .historical_data_analysis import past_stock_investment_outcome


def collect_data(portfolio: dict) -> dict:
    portfolio_outcome: dict = {"data": {}, "summary": {}}
    for params in portfolio:
        outcome: dict = past_stock_investment_outcome(params)
        data: pd.DataFrame = outcome["data"]
        summary: dict = outcome["summary"]

        portfolio_outcome["data"][params["symbol"]] = data
        portfolio_outcome["summary"][params["symbol"]] = summary

    return portfolio_outcome


def combine_data(data: pd.DataFrame) -> pd.DataFrame:
    df_combined = pd.DataFrame(columns=list(data.values())[0].columns)
    for stock_name, stock_df in data.items():
        df_combined = df_combined.merge(
            stock_df,
            left_on="date",
            right_on="date",
            suffixes=("", f"_{stock_name}"),
            how="outer",
        )
    stock_names = list(data.keys())
    df_combined = df_combined[
        [col for col in df_combined.columns if col.split("_")[-1] in stock_names or col == "date"]
    ]
    df_combined.fillna(0, inplace=True)

    col_list = [
        "monthly_money",
        "quarterly_money",
        "bi_annual_money",
        "annual_money",
        "total",
        "input",
        "dividend_gain",
    ]
    for column in col_list:
        df_combined.loc[:, f"{column}_combined"] = 0
        for stock_name in stock_names:
            df_temp = df_combined.copy()
            df_temp.loc[:, f"{column}_combined"] += df_temp.loc[:, f"{column}_{stock_name}"]
            df_combined = df_temp

    df_combined.loc[:, "return_combined"] = df_combined.loc[:, "total_combined"] / (
        df_combined.loc[:, "total_combined"].shift(1)
        + df_combined.loc[:, "monthly_money_combined"]
        + df_combined.loc[:, "quarterly_money_combined"]
        + df_combined.loc[:, "bi_annual_money_combined"]
        + df_combined.loc[:, "annual_money_combined"]
    )

    return df_combined


def get_combined_summary(df_combined: pd.DataFrame) -> dict:
    final_amount: float = df_combined.loc[df_combined["date"] == df_combined["date"].max(), "total_combined"].iloc[0]
    input_amount: float = df_combined.loc[df_combined["date"] == df_combined["date"].max(), "input_combined"].iloc[0]
    # general_monthly_volatility = df_combined["total_return"].std() * 100
    # general_monthly_mean_return = df_combined["total_return"].mean() * 100
    total_dividend: float = sum(df_combined["dividend_gain_combined"].iloc[1:])
    annual_return: float = (
        math.prod(df_combined.loc[1:, "return_combined"].to_list()) ** (12 / (len(df_combined) - 1)) - 1
    ) * 100
    summary: dict = {
        "final_amount": round(final_amount, 2),
        "input_amount": round(input_amount, 2),
        "total_yield_amount": round(final_amount - input_amount, 2),
        "total_yield_percent": round((final_amount - input_amount) / final_amount * 100, 2),
        "total_dividends": round(total_dividend, 2),
        "annual_return": round(annual_return, 2),
    }
    return summary


def portfolio_past_outcome(portfolio: dict) -> dict:
    portfolio_outcome: dict = collect_data(portfolio)
    df_combined: pd.DataFrame = combine_data(portfolio_outcome["data"])
    summary_combined: dict = get_combined_summary(df_combined)
    summary_combined["investment_time"] = max([p["investment_time"] for p in portfolio])

    portfolio_outcome["data"] = df_combined
    portfolio_outcome["summary"]["combined"] = summary_combined

    return portfolio_outcome
