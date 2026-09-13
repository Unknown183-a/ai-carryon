from torch.utils.data import DataLoader

from src.evaluation.accuracy import evaluate_accuracy
from src.evaluation.comparison import build_comparison_table
from src.models.cnn import build_model


def test_accuracy_calculation_in_valid_range(tiny_dataset):
    loader = DataLoader(tiny_dataset, batch_size=16)
    model = build_model()
    result = evaluate_accuracy(model, loader)

    assert 0.0 <= result["accuracy"] <= 1.0
    assert result["num_samples"] == len(tiny_dataset)


def test_comparison_table_generation_leaves_missing_as_none():
    results = {"M_old": {"overall_accuracy": 0.98}, "M_unlearn": {}}
    df = build_comparison_table(results)

    assert list(df["model"]) == ["M_old", "M_unlearn"]
    assert df.loc[df["model"] == "M_old", "overall_accuracy"].iloc[0] == 0.98
    assert df.loc[df["model"] == "M_unlearn", "overall_accuracy"].isna().iloc[0]
