from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler


BINARY_TARGET = "label"
MULTICLASS_TARGET = "attack_cat"
IGNORED_FEATURE_COLUMNS = {"id", BINARY_TARGET, MULTICLASS_TARGET}

DEFAULT_TRAIN_FILE = "UNSW_NB15_training-set.csv"
DEFAULT_TEST_FILE = "UNSW_NB15_testing-set.csv"

SEVERITY_BY_ATTACK = {
    "analysis": "Medium",
    "backdoor": "High",
    "backdoors": "High",
    "dos": "High",
    "exploits": "High",
    "fuzzers": "Medium",
    "generic": "Medium",
    "reconnaissance": "Medium",
    "shellcode": "Critical",
    "worms": "Critical",
}

ACTION_BY_SEVERITY = {
    "Normal": "Allow and continue monitoring.",
    "Low": "Monitor the flow and keep the event for trend analysis.",
    "Medium": "Investigate the source, destination, and related recent events.",
    "High": "Generate an alert, isolate the affected flow, and review firewall rules.",
    "Critical": "Escalate immediately, block the source if policy allows, and start incident response.",
}


class SafeSelectKBest(BaseEstimator, TransformerMixin):
    """Selects up to k features and becomes a pass-through on tiny datasets."""

    def __init__(self, k: Optional[int] = 40):
        self.k = k

    def fit(self, X: Any, y: Sequence[Any]) -> "SafeSelectKBest":
        n_features = int(getattr(X, "shape", [0, 0])[1])
        if self.k is None or self.k <= 0 or self.k >= n_features:
            self.selector_ = None
        else:
            self.selector_ = SelectKBest(score_func=f_classif, k=self.k)
            self.selector_.fit(X, y)
        return self

    def transform(self, X: Any) -> Any:
        if getattr(self, "selector_", None) is None:
            return X
        return self.selector_.transform(X)

    def get_support(self) -> Optional[np.ndarray]:
        if getattr(self, "selector_", None) is None:
            return None
        return self.selector_.get_support()


@dataclass
class TrainingOutput:
    model_path: Path
    metrics_path: Path
    sample_predictions_path: Path
    metrics: Dict[str, Any]


class UNSWNB15Pipeline:
    """End-to-end ML pipeline for the UNSW-NB15 CSV intrusion dataset."""

    def __init__(
        self,
        model_type: str = "random_forest",
        feature_k: int = 40,
        contamination: float = 0.08,
        random_state: int = 42,
        n_estimators: int = 200,
    ) -> None:
        self.model_type = model_type
        self.feature_k = feature_k
        self.contamination = contamination
        self.random_state = random_state
        self.n_estimators = n_estimators

        self.binary_model: Optional[Pipeline] = None
        self.multiclass_model: Optional[Pipeline] = None
        self.attack_encoder: Optional[LabelEncoder] = None
        self.anomaly_model: Optional[Pipeline] = None
        self.feature_columns: List[str] = []
        self.metrics_: Dict[str, Any] = {}
        self.anomaly_score_min_: float = 0.0
        self.anomaly_score_max_: float = 1.0

    @staticmethod
    def load_train_test(data_dir: Union[str, Path]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        data_path = Path(data_dir)
        train_path = data_path / DEFAULT_TRAIN_FILE
        test_path = data_path / DEFAULT_TEST_FILE
        if not train_path.exists() or not test_path.exists():
            raise FileNotFoundError(
                "Expected UNSW-NB15 prepared train/test CSV files at "
                f"{train_path} and {test_path}."
            )
        return pd.read_csv(train_path), pd.read_csv(test_path)

    def fit(self, train_df: pd.DataFrame, test_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        train_df = self.clean_dataframe(train_df)
        if test_df is None:
            train_df, test_df = self._split_train_test(train_df)
        else:
            test_df = self.clean_dataframe(test_df)

        self._prepare_for_fit(train_df)
        X_train = self._feature_frame(train_df)
        X_test = self._feature_frame(test_df)

        y_train_binary = self._binary_target(train_df)
        y_test_binary = self._binary_target(test_df)

        y_train_attack = self._attack_target(train_df)
        y_test_attack = self._attack_target(test_df)
        self.attack_encoder = LabelEncoder()
        y_train_attack_encoded = self.attack_encoder.fit_transform(y_train_attack)
        y_test_attack_encoded = self.attack_encoder.transform(y_test_attack)

        self.binary_model = self._build_classifier("binary", num_classes=2)
        self.binary_model.fit(X_train, y_train_binary)

        self.multiclass_model = self._build_classifier(
            "multiclass",
            num_classes=len(self.attack_encoder.classes_),
        )
        self.multiclass_model.fit(X_train, y_train_attack_encoded)

        self.anomaly_model = self._build_anomaly_model()
        normal_mask = y_train_binary == 0
        anomaly_train = X_train.loc[normal_mask] if normal_mask.any() else X_train
        self.anomaly_model.fit(anomaly_train)
        self._calibrate_anomaly_scores(X_train)

        self.metrics_ = {
            "model_type": self.model_type,
            "feature_count": len(self.feature_columns),
            "selected_feature_k": self.feature_k,
            "binary": self._evaluate_binary(X_test, y_test_binary),
            "multiclass": self._evaluate_multiclass(X_test, y_test_attack_encoded),
            "anomaly": self._evaluate_anomaly(X_test, y_test_binary),
        }
        return self.metrics_

    def predict_records(
        self,
        records: Union[Mapping[str, Any], Iterable[Mapping[str, Any]], pd.DataFrame],
    ) -> List[Dict[str, Any]]:
        self._ensure_fitted()
        if isinstance(records, pd.DataFrame):
            input_df = records.copy()
        elif isinstance(records, Mapping):
            input_df = pd.DataFrame([records])
        else:
            input_df = pd.DataFrame(list(records))

        cleaned = self.clean_dataframe(input_df)
        X = self._feature_frame(cleaned)

        binary_predictions = self.binary_model.predict(X)
        binary_probabilities = self._predict_proba(self.binary_model, X)

        attack_encoded = self.multiclass_model.predict(X)
        attack_predictions = self.attack_encoder.inverse_transform(attack_encoded)
        attack_probabilities = self._predict_proba(self.multiclass_model, X)
        anomaly_scores = self.anomaly_scores(X)

        outputs = []
        for index, binary_value in enumerate(binary_predictions):
            attack_probability = self._attack_probability(binary_probabilities, index)
            status = "Attack" if int(binary_value) == 1 else "Normal"
            attack_type = self._resolve_attack_type(status, attack_predictions[index], attack_probabilities, index)
            anomaly_score = float(anomaly_scores[index])
            severity = self._severity(status, attack_type, anomaly_score, attack_probability)
            outputs.append(
                {
                    "normal_attack": status,
                    "attack_type": attack_type,
                    "severity": severity,
                    "anomaly_score": round(anomaly_score, 4),
                    "action": ACTION_BY_SEVERITY[severity],
                    "binary_attack_probability": round(float(attack_probability), 4),
                }
            )
        return outputs

    def anomaly_scores(self, X: pd.DataFrame) -> np.ndarray:
        self._ensure_fitted()
        transformed = self.anomaly_model.named_steps["preprocess"].transform(X)
        raw_scores = -self.anomaly_model.named_steps["model"].decision_function(transformed)
        denom = self.anomaly_score_max_ - self.anomaly_score_min_
        if denom < 1e-9:
            return np.zeros_like(raw_scores, dtype="float64")
        normalized = (raw_scores - self.anomaly_score_min_) / denom
        return np.clip(normalized, 0.0, 1.0)

    def save(self, path: Union[str, Path]) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, output_path, compress=3)
        return output_path

    @classmethod
    def load(cls, path: Union[str, Path]) -> "UNSWNB15Pipeline":
        loaded = joblib.load(path)
        if not isinstance(loaded, cls):
            raise TypeError(f"Model at {path} is not a UNSWNB15Pipeline bundle.")
        loaded._ensure_fitted()
        return loaded

    @staticmethod
    def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        cleaned = df.copy()
        cleaned.columns = [str(column).strip() for column in cleaned.columns]
        cleaned = cleaned.replace([np.inf, -np.inf], np.nan).drop_duplicates()

        object_columns = cleaned.select_dtypes(include=["object", "string"]).columns
        for column in object_columns:
            cleaned[column] = cleaned[column].astype("string").str.strip()
            cleaned[column] = cleaned[column].replace({"": pd.NA, "-": "unknown"})

        if MULTICLASS_TARGET in cleaned.columns:
            cleaned[MULTICLASS_TARGET] = cleaned[MULTICLASS_TARGET].fillna("Normal")
            cleaned[MULTICLASS_TARGET] = cleaned[MULTICLASS_TARGET].replace({"unknown": "Normal"})

        return cleaned

    def _split_train_test(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        y = self._binary_target(df)
        stratify = y if y.value_counts().min() > 1 else None
        return train_test_split(
            df,
            test_size=0.25,
            random_state=self.random_state,
            stratify=stratify,
        )

    def _feature_frame(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        features = df.drop(columns=[column for column in IGNORED_FEATURE_COLUMNS if column in df.columns], errors="ignore")
        if fit:
            self.feature_columns = list(features.columns)
        else:
            for column in self.feature_columns:
                if column not in features.columns:
                    features[column] = np.nan
            features = features[self.feature_columns]
        return features

    @staticmethod
    def _binary_target(df: pd.DataFrame) -> pd.Series:
        if BINARY_TARGET not in df.columns:
            raise KeyError(f"Missing required binary target column: {BINARY_TARGET}")

        target = df[BINARY_TARGET]
        numeric = pd.to_numeric(target, errors="coerce")
        if numeric.notna().all():
            return numeric.fillna(0).astype(int).clip(0, 1)

        normalized = target.astype("string").str.strip().str.lower()
        return normalized.map(lambda value: 0 if value in {"0", "normal", "false", "benign"} else 1).astype(int)

    @staticmethod
    def _attack_target(df: pd.DataFrame) -> pd.Series:
        if MULTICLASS_TARGET not in df.columns:
            raise KeyError(f"Missing required attack category column: {MULTICLASS_TARGET}")
        return df[MULTICLASS_TARGET].fillna("Normal").astype(str).str.strip().replace({"": "Normal", "unknown": "Normal"})

    def _build_classifier(self, task: str, num_classes: int) -> Pipeline:
        estimator = self._make_estimator(task, num_classes)
        return Pipeline(
            steps=[
                ("preprocess", self._build_preprocessor()),
                ("feature_selection", SafeSelectKBest(k=self.feature_k)),
                ("model", estimator),
            ]
        )

    def _build_anomaly_model(self) -> Pipeline:
        return Pipeline(
            steps=[
                ("preprocess", self._build_preprocessor()),
                (
                    "model",
                    IsolationForest(
                        n_estimators=self.n_estimators,
                        contamination=self.contamination,
                        random_state=self.random_state,
                        n_jobs=-1,
                    ),
                ),
            ]
        )

    def _build_preprocessor(self) -> ColumnTransformer:
        numeric_features = [column for column in self.feature_columns if column not in self._categorical_columns]
        categorical_features = [column for column in self.feature_columns if column in self._categorical_columns]

        numeric_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler(with_mean=False)),
            ]
        )
        categorical_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", self._one_hot_encoder()),
            ]
        )

        transformers = []
        if numeric_features:
            transformers.append(("numeric", numeric_pipeline, numeric_features))
        if categorical_features:
            transformers.append(("categorical", categorical_pipeline, categorical_features))
        return ColumnTransformer(transformers=transformers, remainder="drop")

    @property
    def _categorical_columns(self) -> List[str]:
        return getattr(self, "_categorical_columns_cache", [])

    @_categorical_columns.setter
    def _categorical_columns(self, value: List[str]) -> None:
        self._categorical_columns_cache = value

    def _make_estimator(self, task: str, num_classes: int) -> Any:
        if self.model_type == "xgboost":
            try:
                from xgboost import XGBClassifier
            except ImportError as exc:
                raise RuntimeError(
                    "XGBoost support was requested but xgboost is not installed. "
                    "Install project requirements or run with --model random_forest."
                ) from exc

            params = {
                "n_estimators": max(self.n_estimators, 250),
                "max_depth": 6,
                "learning_rate": 0.08,
                "subsample": 0.9,
                "colsample_bytree": 0.9,
                "tree_method": "hist",
                "random_state": self.random_state,
                "n_jobs": -1,
                "eval_metric": "logloss" if task == "binary" else "mlogloss",
            }
            if task == "multiclass":
                params.update({"objective": "multi:softprob", "num_class": num_classes})
            else:
                params.update({"objective": "binary:logistic"})
            return XGBClassifier(**params)

        if self.model_type != "random_forest":
            raise ValueError("model_type must be 'random_forest' or 'xgboost'.")

        return RandomForestClassifier(
            n_estimators=self.n_estimators,
            class_weight="balanced",
            random_state=self.random_state,
            n_jobs=-1,
        )

    @staticmethod
    def _one_hot_encoder() -> OneHotEncoder:
        try:
            return OneHotEncoder(handle_unknown="ignore", sparse_output=True)
        except TypeError:
            return OneHotEncoder(handle_unknown="ignore", sparse=True)

    def _cache_column_types(self, X: pd.DataFrame) -> None:
        self._categorical_columns = list(X.select_dtypes(include=["object", "string", "category"]).columns)

    def _evaluate_binary(self, X_test: pd.DataFrame, y_true: pd.Series) -> Dict[str, Any]:
        predictions = self.binary_model.predict(X_test)
        probabilities = self._predict_proba(self.binary_model, X_test)
        metrics = self._classification_metrics(y_true, predictions, probabilities, labels=[0, 1], average="binary")

        tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
        metrics["false_positive_rate"] = float(fp / (fp + tn)) if fp + tn else 0.0
        metrics["false_negative_rate"] = float(fn / (fn + tp)) if fn + tp else 0.0
        return metrics

    def _evaluate_multiclass(self, X_test: pd.DataFrame, y_true: np.ndarray) -> Dict[str, Any]:
        predictions = self.multiclass_model.predict(X_test)
        probabilities = self._predict_proba(self.multiclass_model, X_test)
        labels = list(range(len(self.attack_encoder.classes_)))
        metrics = self._classification_metrics(y_true, predictions, probabilities, labels=labels, average="weighted")
        metrics["classes"] = self.attack_encoder.classes_.tolist()
        return metrics

    def _evaluate_anomaly(self, X_test: pd.DataFrame, y_binary: pd.Series) -> Dict[str, Any]:
        scores = self.anomaly_scores(X_test)
        predictions = (scores >= 0.65).astype(int)
        return {
            "roc_auc": self._safe_roc_auc(y_binary, scores),
            "mean_anomaly_score": float(np.mean(scores)) if len(scores) else 0.0,
            "confusion_matrix_at_0_65": confusion_matrix(y_binary, predictions, labels=[0, 1]).tolist(),
        }

    def _classification_metrics(
        self,
        y_true: Sequence[Any],
        predictions: Sequence[Any],
        probabilities: Optional[np.ndarray],
        labels: Sequence[Any],
        average: str,
    ) -> Dict[str, Any]:
        metrics = {
            "accuracy": float(accuracy_score(y_true, predictions)),
            "precision": float(precision_score(y_true, predictions, average=average, zero_division=0)),
            "recall": float(recall_score(y_true, predictions, average=average, zero_division=0)),
            "f1_score": float(f1_score(y_true, predictions, average=average, zero_division=0)),
            "confusion_matrix": confusion_matrix(y_true, predictions, labels=labels).tolist(),
            "classification_report": classification_report(y_true, predictions, zero_division=0, output_dict=True),
        }
        metrics["roc_auc"] = self._roc_auc_for_probabilities(y_true, probabilities, labels)
        return metrics

    @staticmethod
    def _predict_proba(model: Pipeline, X: pd.DataFrame) -> Optional[np.ndarray]:
        if hasattr(model, "predict_proba"):
            return model.predict_proba(X)
        return None

    @staticmethod
    def _roc_auc_for_probabilities(
        y_true: Sequence[Any],
        probabilities: Optional[np.ndarray],
        labels: Sequence[Any],
    ) -> Optional[float]:
        if probabilities is None or len(set(y_true)) < 2:
            return None
        try:
            if len(labels) == 2:
                return float(roc_auc_score(y_true, probabilities[:, 1]))
            return float(roc_auc_score(y_true, probabilities, labels=labels, multi_class="ovr", average="weighted"))
        except ValueError:
            return None

    @staticmethod
    def _safe_roc_auc(y_true: Sequence[Any], scores: Sequence[float]) -> Optional[float]:
        if len(set(y_true)) < 2:
            return None
        try:
            return float(roc_auc_score(y_true, scores))
        except ValueError:
            return None

    def _calibrate_anomaly_scores(self, X_train: pd.DataFrame) -> None:
        transformed = self.anomaly_model.named_steps["preprocess"].transform(X_train)
        raw_scores = -self.anomaly_model.named_steps["model"].decision_function(transformed)
        self.anomaly_score_min_ = float(np.min(raw_scores)) if len(raw_scores) else 0.0
        self.anomaly_score_max_ = float(np.max(raw_scores)) if len(raw_scores) else 1.0

    @staticmethod
    def _attack_probability(probabilities: Optional[np.ndarray], index: int) -> float:
        if probabilities is None:
            return 0.0
        if probabilities.shape[1] == 1:
            return float(probabilities[index, 0])
        return float(probabilities[index, 1])

    def _resolve_attack_type(
        self,
        status: str,
        predicted_attack: str,
        probabilities: Optional[np.ndarray],
        index: int,
    ) -> str:
        if status == "Normal":
            return "Normal"
        if predicted_attack.lower() != "normal":
            return predicted_attack
        if probabilities is None:
            return "Unknown Attack"

        classes = self.attack_encoder.classes_
        non_normal_indices = [i for i, name in enumerate(classes) if str(name).lower() != "normal"]
        if not non_normal_indices:
            return "Unknown Attack"
        best_index = max(non_normal_indices, key=lambda class_index: probabilities[index, class_index])
        return str(classes[best_index])

    @staticmethod
    def _severity(status: str, attack_type: str, anomaly_score: float, attack_probability: float) -> str:
        if status == "Normal":
            if anomaly_score >= 0.85:
                return "Medium"
            if anomaly_score >= 0.65:
                return "Low"
            return "Normal"

        base = SEVERITY_BY_ATTACK.get(attack_type.lower(), "High")
        if anomaly_score >= 0.9 or attack_probability >= 0.95:
            return "Critical" if base == "High" else base
        if anomaly_score < 0.35 and attack_probability < 0.6:
            return "Medium"
        return base

    def _ensure_fitted(self) -> None:
        if not all([self.binary_model, self.multiclass_model, self.attack_encoder, self.anomaly_model, self.feature_columns]):
            raise RuntimeError("UNSW-NB15 pipeline is not fitted yet.")

    def _prepare_for_fit(self, train_df: pd.DataFrame) -> None:
        X_train = self._feature_frame(train_df, fit=True)
        self._cache_column_types(X_train)


def train_from_csv(
    data_dir: Union[str, Path],
    output_dir: Union[str, Path],
    model_type: str = "random_forest",
    feature_k: int = 40,
    sample_size: Optional[int] = None,
    random_state: int = 42,
    n_estimators: int = 200,
) -> TrainingOutput:
    train_df, test_df = UNSWNB15Pipeline.load_train_test(data_dir)
    sample_target = MULTICLASS_TARGET if MULTICLASS_TARGET in train_df.columns else BINARY_TARGET
    train_df = stratified_sample(train_df, sample_size, sample_target, random_state)
    test_sample_size = max(sample_size // 3, 100) if sample_size else None
    test_target = MULTICLASS_TARGET if MULTICLASS_TARGET in test_df.columns else BINARY_TARGET
    test_df = stratified_sample(test_df, test_sample_size, test_target, random_state)

    pipeline = UNSWNB15Pipeline(
        model_type=model_type,
        feature_k=feature_k,
        random_state=random_state,
        n_estimators=n_estimators,
    )
    metrics = pipeline.fit(train_df, test_df)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model_path = pipeline.save(output_path / "unsw_nb15_model.joblib")

    metrics_path = output_path / "unsw_nb15_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    sample_predictions = pipeline.predict_records(test_df.head(25))
    sample_predictions_path = output_path / "unsw_nb15_sample_predictions.csv"
    pd.DataFrame(sample_predictions).to_csv(sample_predictions_path, index=False)

    return TrainingOutput(
        model_path=model_path,
        metrics_path=metrics_path,
        sample_predictions_path=sample_predictions_path,
        metrics=metrics,
    )


def stratified_sample(
    df: pd.DataFrame,
    sample_size: Optional[int],
    target_column: str,
    random_state: int,
) -> pd.DataFrame:
    if sample_size is None or sample_size <= 0 or sample_size >= len(df):
        return df

    if target_column not in df.columns:
        return df.sample(n=sample_size, random_state=random_state)

    fractions = df[target_column].value_counts(normalize=True)
    sampled_parts = []
    remaining = sample_size
    for label, fraction in fractions.items():
        label_rows = df[df[target_column] == label]
        label_sample_size = min(len(label_rows), max(1, int(round(sample_size * fraction))))
        remaining -= label_sample_size
        sampled_parts.append(label_rows.sample(n=label_sample_size, random_state=random_state))

    sampled = pd.concat(sampled_parts, axis=0)
    if remaining > 0 and len(sampled) < len(df):
        extra = df.drop(index=sampled.index).sample(n=min(remaining, len(df) - len(sampled)), random_state=random_state)
        sampled = pd.concat([sampled, extra], axis=0)

    if len(sampled) > sample_size:
        sampled = sampled.sample(n=sample_size, random_state=random_state)
    return sampled.sample(frac=1.0, random_state=random_state).reset_index(drop=True)


__all__ = [
    "BINARY_TARGET",
    "MULTICLASS_TARGET",
    "TrainingOutput",
    "UNSWNB15Pipeline",
    "train_from_csv",
    "stratified_sample",
]
