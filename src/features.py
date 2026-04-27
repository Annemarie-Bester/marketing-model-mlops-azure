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
    """Apply config-driven cleaning and feature engineering to raw data.

    Steps applied when the relevant columns are present (all skippable via config):
      1. Drop leakage columns listed under features.drop_cols.
      2. Cap implausible values in features.age_col at features.age_cap.
      3. Create 'contacted_before' binary from features.pdays_col using
         features.pdays_sentinel as the 'never contacted' marker.
      4. Apply log1p to right-skewed positive columns in features.log_transform_cols.
      5. Apply sign-preserving log to columns in features.signed_log_cols.
      6. Encode target column using model.target_positive_value -> 1, else 0.

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
    # age_col defaults to 'age'; set features.age_col in config.yaml to override.
    # age_cap defaults to 100 if not set. Step is skipped if column absent.
    age_col = feat_cfg.get("age_col", "age")
    age_cap = feat_cfg.get("age_cap", 100)
    if age_col in df.columns:
        n_capped = int((df[age_col] > age_cap).sum())
        if n_capped > 0:
            df[age_col] = df[age_col].clip(upper=age_cap)
            logger.info("Capped %d row(s) where %s > %d",
                        n_capped, age_col, age_cap)
    else:
        logger.warning(
            "Column '%s' not found — age cap step skipped.", age_col)

    # --- 3. contacted_before flag (pdays sentinel = never contacted) ---
    # pdays_col defaults to 'pdays'; pdays_sentinel defaults to -1.
    # Step is skipped if column absent (e.g. datasets without prior contact info).
    pdays_col = feat_cfg.get("pdays_col", "pdays")
    pdays_sentinel = feat_cfg.get("pdays_sentinel", -1)
    if pdays_col in df.columns:
        df["contacted_before"] = (df[pdays_col] != pdays_sentinel).astype(int)
        logger.info("Created 'contacted_before' feature from '%s' (sentinel=%s)",
                    pdays_col, pdays_sentinel)
    else:
        logger.warning(
            "Column '%s' not found — 'contacted_before' feature skipped.", pdays_col)

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
    # target_positive_value configures which string label maps to 1.
    # Defaults to 'yes' for the bank marketing dataset; override in config.yaml.
    if target_col in df.columns:
        pos_val = config["model"].get("target_positive_value", "yes")
        df[target_col] = (df[target_col] == pos_val).astype(int)
        logger.info("Encoded target '%s': %s=1, else=0", target_col, pos_val)

    return df


def split_data(
    df: pd.DataFrame, config: dict
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Split the cleaned DataFrame into stratified train/test sets.

    Stratified split ensures both sets reflect the original class distribution,
    which is important for imbalanced classification problems.

    Split parameters (test_size, random_state) are read from config.model.

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
        transformers.append(
            ("categorical", categorical_pipeline, categorical_cols))

    return ColumnTransformer(transformers=transformers, remainder="drop")
