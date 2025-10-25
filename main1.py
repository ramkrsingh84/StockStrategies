from concurrent.futures import ThreadPoolExecutor
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner

def run_all_strategies():
    results = {}
    with ThreadPoolExecutor() as executor:
        futures = {
            name: executor.submit(StrategyRunner(name, config).run)
            for name, config in STRATEGY_CONFIG.items()
        }
        for name, future in futures.items():
            results[name] = future.result()
    return results

if __name__ == "__main__":
    all_results = run_all_strategies()
    for strategy, df in all_results.items():
        print(f"\n📊 Signals for {strategy}")
        if df.empty:
            print("✅ No actionable signals today.")
        else:
            print(df.to_string(index=False))