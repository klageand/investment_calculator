import json
import os

import matplotlib.pyplot as plt

import project_helpers as hp
from historical_data_analysis import portfolio_past_outcome, save_summary
from simulation import simulate_outcome


def analyze_portfolio(portfolio_name):
    # get paths
    current_dir_path = os.path.dirname(os.path.abspath(__file__))
    project_abs_path = hp.get_project_abs_path("investment_calculator", current_dir_path)
    portfolio_dir = os.path.join(project_abs_path, "data", "portfolios")
    result_dir = os.path.join(project_abs_path, "data", "results", portfolio_name)

    # get portfolio config
    with open(f"{portfolio_dir}/{portfolio_name}.json", "r") as f:
        portfolio = json.load(f)

    # create result path
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    # get portfolio historical analysis
    portfolio_outcome = portfolio_past_outcome(portfolio["portfolio"])
    data = portfolio_outcome["data"]

    # simulation based on combined stock parameters
    portfolio_outcome["simulation"] = {}
    for stock_name in portfolio_outcome["summary"].keys():
        if stock_name == "combined":
            continue
        # stock_name = "URTH"
        stock_config = [p for p in portfolio["portfolio"] if p["symbol"] == stock_name][0]
        monthly_std = portfolio_outcome["summary"][stock_name]["general"]["volatility_monthly"] / 100
        monthly_mean = portfolio_outcome["summary"][stock_name]["general"]["mean_return_monthly"] / 100

        # simulation
        simulation_save_path = f"{result_dir}/{stock_name}_simulation_result.json"

        if os.path.exists(simulation_save_path):
            with open(simulation_save_path, "r") as f:
                simulation_result = json.loads(f.read())
        else:
            simulation_result = simulate_outcome(stock_config, monthly_mean, monthly_std)
            with open(simulation_save_path, "w") as f:
                f.write(json.dumps(simulation_result))

        portfolio_outcome["simulation"][stock_name] = simulation_result

    # save plots in results
    for stock_name in portfolio_outcome["summary"].keys():
        data = portfolio_outcome["data"].loc[portfolio_outcome["data"][f"input_{stock_name}"] > 0, :]
        data.plot(x="date", y=[f"total_{stock_name}", f"input_{stock_name}"])
        plt.savefig(f"{result_dir}/{stock_name}.png")

    # save summaries as .txt files
    for stock_name, stock_summary in portfolio_outcome["summary"].items():
        save_summary(stock_summary, stock_name, f"{result_dir}/{stock_name}_summary.txt")

    return portfolio_outcome
