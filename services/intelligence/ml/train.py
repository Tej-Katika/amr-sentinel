"""Training pipeline. Run as: python -m ml.train [--facility-id ID]."""
from __future__ import annotations

import argparse
import logging

from .features import build_training_frame
from .resistance_predictor import ResistancePredictor


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--facility-id", default=None)
    args = parser.parse_args()

    df = build_training_frame(args.facility_id)
    if df.empty:
        print("No training data available; ingest some isolates first.")
        return

    predictor = ResistancePredictor()
    result = predictor.train(df)
    path = predictor.save()

    print(f"Model trained: version={result.model_version}, AUC={result.auc:.3f}, "
          f"acc={result.accuracy:.3f}, n_train={result.n_train}, n_test={result.n_test}")
    print(f"Saved to {path}")


if __name__ == "__main__":
    main()
