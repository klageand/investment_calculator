import numpy as np
import pandas as pd

import historical_data_analysis as hda



def simulate_outcome(stock_config, monthly_mean, monthly_std, iterations=100):

    number_of_months = stock_config["investment_time"] * 12

    df_dict_simulated = simulate_data(stock_config, monthly_mean, monthly_std, number_of_months, iterations)
    df_dict_calc = calculate_outcome(df_dict_simulated, number_of_months, iterations)
    summary = summarize_simulation_outcome(df_dict_simulated, df_dict_calc, number_of_months, iterations)

    return summary


def summarize_simulation_outcome(df_dict_simulated, df_dict_calc, number_of_months, iterations):

    # summarize each iteration
    df_result = pd.DataFrame(
        columns=[
            "input_amount", 
            "final_amount", 
            "total_yield_amount", 
            "total_yield_percent", 
            "total_dividends", 
            "annual_return"
        ],
        index=list(range(iterations))
    )
    df_result.loc[:, "input_amount"] = df_dict_simulated["input"][-1]
    df_result.loc[:, "final_amount"] = df_dict_calc["df_total"].loc[:, number_of_months - 1]
    df_result.loc[:, "total_dividends"] = df_dict_simulated["df_dividend_gain"].transpose().sum()
    df_result.loc[:, "annual_return"] = 100 *(
        df_dict_calc["df_return"].transpose().product() ** (12/number_of_months) - 1
    )
    df_result.loc[:, "total_yield_amount"] = df_result.loc[:, "final_amount"] - df_result.loc[:, "input_amount"]
    df_result.loc[:, "total_yield_percent"] = 100 * (
        df_result.loc[:, "total_yield_amount"] / df_result.loc[:, "final_amount"]
    )

    # summarize summary of all interations
    simulation_summary = {}
    for col in df_result.columns:
        simulation_summary[col] = {}
        simulation_summary[col]["mean"] = df_result.loc[:, col].mean()
        simulation_summary[col]["std"] = df_result.loc[:, col].std()
        simulation_summary[col]["quantile_25"] = df_result.loc[:, col].quantile(0.25)
        simulation_summary[col]["quantile_50"] = df_result.loc[:, col].quantile(0.5)
        simulation_summary[col]["quantile_75"] = df_result.loc[:, col].quantile(0.75)
        simulation_summary[col]["min"] = df_result.loc[:, col].min()
        simulation_summary[col]["max"] = df_result.loc[:, col].max()

    return simulation_summary


def simulate_data(stock_config, monthly_mean, monthly_std, number_of_months, iterations):
    static_cols = ["monthly_money", "quarterly_money", "bi_annual_money", "annual_money", "input"]
    simulated_cols = ["simulated_change", "dividend_gain"]

    df_dict_simulated = {f"df_{col}": pd.DataFrame(
        columns=list(range(number_of_months)), 
        index=list(range(iterations))
        )
        for col in simulated_cols
    }
    for i in range(iterations):
        df_simulation = get_simulated_df(stock_config, monthly_mean, monthly_std)

        if i == 0:
            for col in static_cols:
                df_dict_simulated[col] = df_simulation.loc[:, col].to_list()

        df_simulation = df_simulation.set_index(df_simulation.loc[:,"month_number"]).drop(columns=["month_number"])
        df_simulation.columns = [f"{col}_{i}" for col in df_simulation.columns]
        df_simulation = df_simulation.transpose()

        for col in simulated_cols:
            df_dict_simulated[f"df_{col}"].loc[i, :] = df_simulation.loc[f"{col}_{i}"]

    return df_dict_simulated


def get_simulated_df(stock_config, monthly_mean, monthly_std):
    number_of_months = stock_config["investment_time"] * 12

    df_simulation = pd.DataFrame()
    random_return_values = np.random.normal(monthly_mean, monthly_std, number_of_months)
    df_simulation.loc[:, "simulated_change"] = random_return_values + 1

    df_simulation.loc[1:, "monthly_money"] = stock_config["monthly_investment"]
    df_simulation.loc[1::3, "quarterly_money"] = stock_config["quarter_investment"]
    df_simulation.loc[1::6, "bi_annual_money"] = stock_config["bi_annual_investment"]
    df_simulation.loc[1::12, "annual_money"] = stock_config["annual_investment"]
    df_simulation.fillna(0, inplace=True)

    df_simulation.reset_index(inplace=True)
    df_simulation.rename(columns={"index": "month_number"}, inplace=True)

    df_simulation.loc[:, "input"] = stock_config["initial_investment"]
    df_simulation = hda.calculate_input_for_interval(df_simulation, 12, stock_config["annual_investment"], stock_config["initial_investment"])
    df_simulation = hda.calculate_input_for_interval(df_simulation, 6, stock_config["bi_annual_investment"], stock_config["initial_investment"])
    df_simulation = hda.calculate_input_for_interval(df_simulation, 3, stock_config["quarter_investment"], stock_config["initial_investment"])
    df_simulation = hda.calculate_input_for_interval(df_simulation, 1, stock_config["monthly_investment"], stock_config["initial_investment"])

    df_simulation.loc[:, "dividend_gain"] = 0

    return df_simulation


def calculate_outcome(df_dict_simulated, number_of_months, iterations):

    calc_cols = ["total", "return"]
    
    df_dict_calc = {f"df_{col}": pd.DataFrame(
        columns=list(range(number_of_months)), 
        index=list(range(iterations))
        )
        for col in calc_cols
    }
    df_dict_calc["df_total"].loc[:, 0] = df_dict_simulated["input"][0] * df_dict_simulated["df_simulated_change"].loc[:, 0]
    for month in range(1, number_of_months):
        df_dict_calc["df_total"].loc[:, month] = (
            df_dict_calc["df_total"].loc[:, month - 1] * df_dict_simulated["df_simulated_change"].loc[:, month]
            + df_dict_simulated["monthly_money"][month] * df_dict_simulated["df_simulated_change"].loc[:, month]
            + df_dict_simulated["quarterly_money"][month] * df_dict_simulated["df_simulated_change"].loc[:, month]
            + df_dict_simulated["bi_annual_money"][month] * df_dict_simulated["df_simulated_change"].loc[:, month]
            + df_dict_simulated["annual_money"][month] * df_dict_simulated["df_simulated_change"].loc[:, month]
        )
        df_dict_calc["df_return"].loc[:, month] = (
            df_dict_calc["df_total"].loc[:, month] / (
                df_dict_calc["df_total"].loc[:, month - 1]
                + df_dict_simulated["monthly_money"][month]
                + df_dict_simulated["quarterly_money"][month]
                + df_dict_simulated["bi_annual_money"][month]
                + df_dict_simulated["annual_money"][month]
            )
        )
    
    return df_dict_calc