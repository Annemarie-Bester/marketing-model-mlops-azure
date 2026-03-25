"""
features.py — Feature engineering and preprocessing pipeline.

Applies EDA-driven cleaning, creates derived features, and builds
a scikit-learn ColumnTransformer for train/test preprocessing.

Design decisions:
- All transforms are fit on training data only (no data leakage).
- The ColumnTransformer is returned unfitted so it can be embedded
  inside train.py's full Pipeline — ensuring the saved model artifact
  self-contains both preprocessing and the classifier.
- Log transforms are applied manually in clean_data() before the
  sklearn pipeline, keeping the ColumnTransformer simple (impute + scale).
"""

import logging

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

logger = logging.getLogger(__name__)


def clean_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Apply EDA-driven cleaning and feature engineering to raw data.

    Steps (driven by findings in notebooks/01_eda.ipynb):
      1. Drop post-hoc variables that risk data leakage.
      2. Cap implausible age values (4 rows with age > 100 are data entry errors).
      3. Create 'contacted_before' binary from pdays sentinel (-1 = never contacted).
         pdays mixes a categorical concept (-1) with a numeric one (days since contact),
         so splitting into a binary flag + numeric is more informative.
      4. Apply log1p to right-skewed positive columns (duration, campaign).
      5. Apply sign-preserving log to balance (can be negative; skew=6.55).
      6. Encode target column: 'yes' -> 1, 'no' -> 0.

    Args:
        df: Raw DataFrame returned by load_data().
        config: Full parsed config dict from config.yaml.

    Returns:
        Cleaned DataFrame ready for train/test split and preprocessing.
    """
    df = df.copy()
    feat_cfg = config.get("features", {})
    target_col = config["model"]["target_column"]

    # --- 1. Drop leakage columns ---
    drop_cols = feat_cfg.get("drop_cols", [])
    existing_drop = [c for c in drop_cols if c in df.columns]
    if existing_drop:
        df = df.drop(columns=existing_drop)
        logger.info("Dropped columns (leakage risk): %s", existing_drop)

    # --- 2. Cap implausible ages ---
    age_cap = feat_cfg.get("age_cap", 100)
    n_capped = int((df["age"] > age_cap).sum())
    if n_capped > 0:
        df["age"] = df["age"].clip(upper=age_cap)
        logger.info("Capped %d row(s) where age > %d", n_capped, age_cap)

    # --- 3. contacted_before flag (pdays == -1 means never contacted) ---
    df["contacted_before"] = (df["pdays"] != -1).astype(int)
    logger.info("Created 'contacted_before' feature (1 = was contacted previously)")

    # --- 4. Log1p transform for right-skewed positive columns ---
    for col in feat_cfg.get("log_transform_cols", []):
        if col in df.columns:
            df[col] = np.log1p(df[col].clip(lower=0))
            logger.info("Applied log1p transform to '%s'", col)

    # --- 5. Sign-preserving log for columns that can be negative (e.g. balance) ---
    # Formula: sign(x) * log1p(|x|) — preserves direction, compresses magnitude
    for col in feat_cfg.get("signed_log_cols", []):
        if col in df.columns:
            df[col] = np.sign(df[col]) * np.log1p(np.abs(df[col]))
            logger.info("Applied signed log transform to '%s'", col)

    # --- 6. Encode target (skip during prediction when target is absent) ---
    if target_col in df.columns:
        df[target_col] = (df[target_col] == "yes").astype(int)
        logger.info("Encoded target '%s': yes=1, no=0", target_col)

    return df


def split_data(
    df: pd.DataFrame, config: dict
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Split the cleaned DataFrame into stratified train/test sets.

    Stratified split ensures both sets reflect the original class distribution,
    which is important given the 7.6:1 class imbalance in this dataset.

    Args:
        df: Cleaned DataFrame from clean_data().
        config: Full parsed config dict.

    Returns:
        Tuple of (X_train, X_test, y_train, y_test).
    """
    target_col = config["model"]["target_column"]
    test_size = config["model"]["test_size"]
    random_state = config["model"]["random_state"]

    X = df.drop(columns=[target_col])
    y = df[target_col]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    logger.info(
        "Train/test split: %d train, %d test (stratified, test_size=%.0f%%)",
        len(X_train),
        len(X_test),
        test_size * 100,
    )
    return X_train, X_test, y_train, y_test


def build_preprocessor(X_train: pd.DataFrame) -> ColumnTransformer:
    """Build an unfitted ColumnTransformer for numeric and categorical columns.

    By the time data reaches this function, skew transforms have already been
    applied in clean_data(). This preprocessor handles:
      - Numeric columns : median imputation (robust to outliers) + standard scaling
      - Categorical cols: most-frequent imputation + one-hot encoding

    The returned transformer is intentionally unfitted. It is embedded inside
    the full sklearn Pipeline in train.py, so fit() only sees training data.

    Args:
        X_train: Training features — used only to identify column types.

    Returns:
        Unfitted ColumnTransformer.
    """
    numeric_cols = X_train.select_dtypes(include=np.number).columns.tolist()
    categorical_cols = X_train.select_dtypes(include="object").columns.tolist()

    logger.info(
        "Preprocessor columns — numeric: %d, categorical: %d",
        len(numeric_cols),
        len(categorical_cols),
    )

    numeric_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            # handle_unknown='ignore': unseen categories at inference become all-zero
            # sparse_output=False: dense array — required by some sklearn estimators
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    transformers = []
    if numeric_cols:
        transformers.append(("numeric", numeric_pipeline, numeric_cols))
    if categorical_cols:
        transformers.append(("categorical", categorical_pipeline, categorical_cols))

    return ColumnTransformer(transformers=transformers, remainder="drop")
