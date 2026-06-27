from __future__ import annotations

import argparse
from pathlib import Path

from unsw_nb15_pipeline import train_from_csv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = (
    PROJECT_ROOT
    / "Data"
    / "UNSW-NB15 dataset"
    / "CSV Files"
    / "Training and Testing Sets"
)
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "models"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the UNSW-NB15 intrusion detection ML pipeline.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Folder containing prepared UNSW train/test CSVs.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Folder for the saved model and metrics.")
    parser.add_argument(
        "--model",
        choices=["random_forest", "xgboost"],
        default="random_forest",
        help="Main classifier. Random Forest is the recommended first implementation.",
    )
    parser.add_argument("--feature-k", type=int, default=40, help="Maximum selected features after preprocessing.")
    parser.add_argument("--n-estimators", type=int, default=200, help="Tree count for Random Forest and Isolation Forest.")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Optional stratified training sample for quick smoke tests before full training.",
    )
    parser.add_argument("--random-state", type=int, default=42, help="Random seed for reproducible training.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = train_from_csv(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        model_type=args.model,
        feature_k=args.feature_k,
        sample_size=args.sample_size,
        random_state=args.random_state,
        n_estimators=args.n_estimators,
    )

    binary = output.metrics["binary"]
    multiclass = output.metrics["multiclass"]
    anomaly = output.metrics["anomaly"]

    print(f"Saved model: {output.model_path}")
    print(f"Saved metrics: {output.metrics_path}")
    print(f"Saved sample predictions: {output.sample_predictions_path}")
    print(
        "Binary classification "
        f"accuracy={binary['accuracy']:.4f}, precision={binary['precision']:.4f}, "
        f"recall={binary['recall']:.4f}, f1={binary['f1_score']:.4f}, roc_auc={binary['roc_auc']}"
    )
    print(
        "Multi-class classification "
        f"accuracy={multiclass['accuracy']:.4f}, precision={multiclass['precision']:.4f}, "
        f"recall={multiclass['recall']:.4f}, f1={multiclass['f1_score']:.4f}, "
        f"roc_auc={multiclass['roc_auc']}"
    )
    print(f"Isolation Forest anomaly ROC-AUC={anomaly['roc_auc']}")


if __name__ == "__main__":
    main()
