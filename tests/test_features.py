"""
test_features.py — Tests for src/features.py

Covers clean_data(), split_data(), and build_preprocessor().
All tests use the in-memory `raw_df` and `config` fixtures from conftest.py.
"""

import numpy as np
import pytest
from sklearn.compose import ColumnTransformer

from src.features import build_preprocessor, clean_data, split_data


class TestCleanData:
    def test_drops_leakage_column(self, raw_df, config):
        """post_campaign_action must be dropped — it's a post-hoc leakage variable."""
        result = clean_data(raw_df, config)
        assert "post_campaign_action" not in result.columns

    def test_age_capped(self, raw_df, config):
        """Rows where age > 100 should be clipped to 100."""
        result = clean_data(raw_df, config)
        assert result["age"].max() <= 100

    def test_contacted_before_created(self, raw_df, config):
        """contacted_before must be present after cleaning."""
        result = clean_data(raw_df, config)
        assert "contacted_before" in result.columns

    def test_contacted_before_values(self, raw_df, config):
        """pdays == -1 → contacted_before = 0; pdays > 0 → contacted_before = 1."""
        result = clean_data(raw_df, config)
        # raw_df has pdays = [-1, 180, -1]
        expected = [0, 1, 0]
        assert result["contacted_before"].tolist() == expected

    def test_log_transform_applied(self, raw_df, config):
        """duration and campaign should be log-transformed (values differ from raw)."""
        result = clean_data(raw_df, config)
        # log1p(100) ≈ 4.615 — not equal to raw value 100
        assert not (result["duration"] == raw_df["duration"]).all()
        assert not (result["campaign"] == raw_df["campaign"]).all()

    def test_signed_log_transform_applied(self, raw_df, config):
        """balance should be sign-log transformed; negative values stay negative."""
        result = clean_data(raw_df, config)
        # raw_df has balance = [1000, -500, 0]
        assert (
            result["balance"].iloc[1] < 0
        ), "Negative balance must stay negative after signed-log"
        assert result["balance"].iloc[2] == 0.0, "Zero balance must remain zero"

    def test_target_encoded(self, raw_df, config):
        """target 'yes'/'no' strings must be encoded to 1/0 integers."""
        result = clean_data(raw_df, config)
        assert set(result["target"].unique()).issubset({0, 1})

    def test_target_skipped_when_absent(self, raw_df, config):
        """clean_data should not raise when target column is absent (predict mode)."""
        df_no_target = raw_df.drop(columns=["target"])
        result = clean_data(df_no_target, config)
        assert "target" not in result.columns

    def test_age_cap_skipped_when_column_absent(self, raw_df, config):
        """Age cap step must skip gracefully and log a warning when age_col is missing."""
        df_no_age = raw_df.drop(columns=["age"])
        # Redirect age_col to 'age' (which no longer exists) — should not raise
        cfg = {**config, "features": {**config["features"], "age_col": "age"}}
        result = clean_data(df_no_age, cfg)
        assert "age" not in result.columns

    def test_contacted_before_skipped_when_pdays_absent(self, raw_df, config):
        """contacted_before must be absent (and no error) when pdays_col is missing."""
        df_no_pdays = raw_df.drop(columns=["pdays"])
        cfg = {**config, "features": {**
                                      config["features"], "pdays_col": "pdays"}}
        result = clean_data(df_no_pdays, cfg)
        assert "contacted_before" not in result.columns


class TestSplitData:
    def _make_clean_df(self, raw_df, config):
        """Helper: returns a cleaned DataFrame large enough to split."""
        # Duplicate rows so stratified split has enough samples per class
        import pandas as pd

        df = pd.concat([raw_df] * 10, ignore_index=True)
        return clean_data(df, config)

    def test_returns_four_parts(self, raw_df, config):
        df_clean = self._make_clean_df(raw_df, config)
        result = split_data(df_clean, config)
        assert len(result) == 4

    def test_split_sizes(self, raw_df, config):
        """Test set should be ~20% of total rows (within rounding)."""
        df_clean = self._make_clean_df(raw_df, config)
        X_train, X_test, _, _ = split_data(df_clean, config)
        total = len(X_train) + len(X_test)
        assert abs(len(X_test) / total - 0.2) < 0.05

    def test_target_removed_from_features(self, raw_df, config):
        """X splits must not contain the target column."""
        df_clean = self._make_clean_df(raw_df, config)
        X_train, X_test, _, _ = split_data(df_clean, config)
        assert "target" not in X_train.columns
        assert "target" not in X_test.columns

    def test_labels_are_binary(self, raw_df, config):
        """y splits should contain only 0 and 1."""
        df_clean = self._make_clean_df(raw_df, config)
        _, _, y_train, y_test = split_data(df_clean, config)
        assert set(y_train.unique()).issubset({0, 1})
        assert set(y_test.unique()).issubset({0, 1})


class TestBuildPreprocessor:
    def test_returns_column_transformer(self, raw_df, config):
        """build_preprocessor should return a ColumnTransformer."""
        df_clean = clean_data(raw_df, config)
        X = df_clean.drop(columns=["target"])
        result = build_preprocessor(X)
        assert isinstance(result, ColumnTransformer)

    def test_preprocessor_fits_and_transforms(self, raw_df, config):
        """Fitting the preprocessor on training data must not raise."""
        import pandas as pd

        df = pd.concat([raw_df] * 10, ignore_index=True)
        df_clean = clean_data(df, config)
        X = df_clean.drop(columns=["target"])
        preprocessor = build_preprocessor(X)
        transformed = preprocessor.fit_transform(X)
        assert transformed.shape[0] == len(X)
        assert transformed.shape[1] > 0


class TestPipelineRobustness:
    """Full pipeline (clean → split → preprocess → train) with missing columns."""

    def _run_full_pipeline(self, df, config):
        """Helper: runs the complete training pipeline end-to-end."""
        import pandas as pd
        from src.train import train

        # Need enough rows for stratified split
        df = pd.concat([df] * 10, ignore_index=True)
        df_clean = clean_data(df, config)
        X_train, X_test, y_train, y_test = split_data(df_clean, config)
        preprocessor = build_preprocessor(X_train)
        pipeline = train(X_train, y_train, preprocessor, config)
        return pipeline, X_test, y_test

    def test_full_pipeline_without_age_column(self, raw_df, config):
        """Removing age from the dataset must not break the training pipeline.

        clean_data() skips the age-cap step and logs a warning.
        build_preprocessor() infers columns dynamically — age simply absent.
        The trained pipeline must still produce predictions on the test set.
        """
        df_no_age = raw_df.drop(columns=["age"])
        pipeline, X_test, y_test = self._run_full_pipeline(df_no_age, config)

        assert hasattr(
            pipeline, "predict"), "Pipeline must have predict method"
        preds = pipeline.predict(X_test)
        assert len(preds) == len(y_test)
        assert set(preds).issubset({0, 1}), "Predictions must be binary"
        assert "age" not in pipeline.feature_names_in_ if hasattr(
            pipeline, "feature_names_in_") else True

    def test_full_pipeline_without_pdays_column(self, raw_df, config):
        """Removing pdays from the dataset must not break the training pipeline.

        clean_data() skips the contacted_before feature (logs a warning).
        build_preprocessor() infers columns dynamically — contacted_before absent.
        The trained pipeline must still produce predictions on the test set.
        """
        df_no_pdays = raw_df.drop(columns=["pdays"])
        pipeline, X_test, y_test = self._run_full_pipeline(df_no_pdays, config)

        assert hasattr(
            pipeline, "predict"), "Pipeline must have predict method"
        preds = pipeline.predict(X_test)
        assert len(preds) == len(y_test)
        assert set(preds).issubset({0, 1}), "Predictions must be binary"

    def test_pipeline_without_pdays_does_not_produce_contacted_before(self, raw_df, config):
        """contacted_before must not appear in X when pdays is absent at training time.

        If it did appear (e.g. all zeros), the model would expect it at inference
        on unseen rows — creating a silent feature mismatch.
        """
        import pandas as pd

        df = pd.concat([raw_df.drop(columns=["pdays"])]
                       * 10, ignore_index=True)
        df_clean = clean_data(df, config)
        X = df_clean.drop(columns=["target"])
        assert "contacted_before" not in X.columns

    def test_inference_without_pdays_on_model_trained_without_pdays(self, raw_df, config):
        """A model trained without pdays must accept inference rows also lacking pdays.

        This reflects the real scenario: if pdays is absent in production data,
        the training run also won't have it, so no column mismatch occurs.
        """
        import pandas as pd

        df_no_pdays = raw_df.drop(columns=["pdays"])
        pipeline, X_test, _ = self._run_full_pipeline(df_no_pdays, config)

        # Inference row matching training schema (no pdays, no contacted_before)
        inference_row = X_test.iloc[[0]]
        assert "pdays" not in inference_row.columns
        assert "contacted_before" not in inference_row.columns

        pred = pipeline.predict(inference_row)
        assert len(pred) == 1
        assert pred[0] in {0, 1}
