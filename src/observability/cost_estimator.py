from __future__ import annotations

import json
import os


DEFAULT_PRICES: dict[str, dict[str, float]] = {
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


class CostEstimator:
    def __init__(self, prices_file: str | None = None) -> None:
        if prices_file and os.path.exists(prices_file):
            with open(prices_file, encoding="utf-8") as f:
                self._prices: dict[str, dict[str, float]] = json.load(f)
        else:
            self._prices = dict(DEFAULT_PRICES)

    def estimate(self, prompt_tokens: int, completion_tokens: int) -> dict[str, float]:
        results: dict[str, float] = {}
        for model, prices in self._prices.items():
            cost = (prompt_tokens / 1_000_000 * prices["input"]) + (
                completion_tokens / 1_000_000 * prices["output"]
            )
            results[model] = round(cost, 6)
        return results

    def add_model(self, name: str, input_price: float, output_price: float) -> None:
        self._prices[name] = {"input": input_price, "output": output_price}
