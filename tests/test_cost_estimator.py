from __future__ import annotations

import json
import os
import tempfile

from src.observability.cost_estimator import CostEstimator


def test_estimate_default_prices():
    est = CostEstimator()
    result = est.estimate(prompt_tokens=1000, completion_tokens=500)
    assert abs(result["claude-sonnet-4"] - 0.0105) < 0.0001
    assert "claude-opus-4" in result
    assert "gpt-4o" in result


def test_estimate_zero_tokens():
    est = CostEstimator()
    result = est.estimate(prompt_tokens=0, completion_tokens=0)
    for cost in result.values():
        assert cost == 0.0


def test_add_model():
    est = CostEstimator()
    est.add_model("custom-model", input_price=1.0, output_price=2.0)
    result = est.estimate(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert abs(result["custom-model"] - 3.0) < 0.0001


def test_load_prices_from_file():
    tmpdir = tempfile.mkdtemp()
    prices_file = os.path.join(tmpdir, "prices.json")
    custom_prices = {"my-model": {"input": 5.0, "output": 10.0}}
    with open(prices_file, "w") as f:
        json.dump(custom_prices, f)
    est = CostEstimator(prices_file=prices_file)
    result = est.estimate(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert "my-model" in result
    assert abs(result["my-model"] - 15.0) < 0.0001
