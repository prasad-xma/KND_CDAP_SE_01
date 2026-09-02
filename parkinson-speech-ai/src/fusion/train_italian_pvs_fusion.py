"""Fusion ablation study — closes the gap between what the proposal promises
for Component 3 (slide 28/30: "investigate feature-level and decision-level
fusion", "evaluate weighted-ensemble and stacking strategies", "ablation
study across feature-level, decision-level and stacked fusion strategies",
"does Score A + B beat either alone?") and what existed in the repo before
this script (nothing — no fusion code at all).

Both components already independently trained on the Italian PVS dataset
(22 Elderly HC, 24 PD); the same 46 participants did both the vowel task and
the "pa"/"ta" DDK task, which is what makes a real, non-fabricated fusion
comparison possible here.

Four things are compared, all under the same participant-grouped 5-fold CV
(a held-out participant's data never touches training in ANY strategy):
  - vowel_only:      Component 2 alone
  - ddk_only:         Component 3 alone
  - decision_level:   average of the two components' predicted probabilities
                       (no extra fitting — just arithmetic on two already-
                       independent models' outputs)
  - feature_level:    concatenate vowel + DDK features into one row per
                       participant (mean-aggregated across each person's
                       recordings) and train a single classifier on that
  - stacked:          a small meta-learner (logistic regression) trained on
                       [vowel_prob, ddk_prob] as its two input features,
                       fit only on the training folds' out-of-fold
                       predictions (nested CV) so the meta-learner never
                       sees a label it's being scored against

Usage:
    python -m src.fusion.train_italian_pvs_fusion
"""

import os
import json

import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
)

from ..component2_phonation.features import FEATURE_NAMES as VOWEL_FEATURES
from ..component3_ddk.features import FEATURE_NAMES as DDK_FEATURES
from ..common.model_evaluation import RANDOM_STATE, MODELS_DIR

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_DIR = os.path.join(REPO_ROOT, "results", "fusion")
VOWEL_CSV = os.path.join(REPO_ROOT, "results", "component2_phonation", "italian_pvs_vowel_features.csv")
DDK_CSV = os.path.join(REPO_ROOT, "results", "component3_ddk", "italian_pvs_ddk_features.csv")

N_SPLITS = 5
INNER_SPLITS = 4  # for the stacked meta-learner's nested CV within each training fold


def _make_model():
    return RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=RANDOM_STATE)


def _participant_features(df, feature_cols):
    """Mean-aggregate a recording-level feature table to one row per participant."""
    return df.groupby("participant_id")[feature_cols].mean()


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)

    vowel_df = pd.read_csv(VOWEL_CSV)
    ddk_df = pd.read_csv(DDK_CSV)

    participants = ddk_df[["participant_id", "label"]].drop_duplicates().reset_index(drop=True)
    missing = set(participants["participant_id"]) ^ set(vowel_df["participant_id"].unique())
    if missing:
        raise ValueError(f"Vowel and DDK participant sets don't match: {missing}")

    print(f"Participants: {len(participants)} "
          f"({sum(participants['label'] == 0)} HC, {sum(participants['label'] == 1)} PD)")

    # Participant-level feature table for the feature-level strategy: mean-aggregate
    # each person's recordings, then concatenate the two modalities' features.
    vowel_participant_feats = _participant_features(vowel_df, VOWEL_FEATURES)
    ddk_participant_feats = _participant_features(ddk_df, DDK_FEATURES)
    combined_feats = vowel_participant_feats.join(ddk_participant_feats, how="inner",
                                                    lsuffix="_vowel", rsuffix="_ddk")
    combined_feature_cols = list(combined_feats.columns)

    cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)

    rows = []
    fold_vowel_weights = []
    for fold, (train_idx, test_idx) in enumerate(
        cv.split(participants["participant_id"], participants["label"])
    ):
        train_ids = set(participants.loc[train_idx, "participant_id"])
        test_ids = set(participants.loc[test_idx, "participant_id"])

        # --- vowel-only / ddk-only base models (also feed decision-level + stacked) ---
        vowel_train = vowel_df[vowel_df["participant_id"].isin(train_ids)]
        vowel_test = vowel_df[vowel_df["participant_id"].isin(test_ids)]
        ddk_train = ddk_df[ddk_df["participant_id"].isin(train_ids)]
        ddk_test = ddk_df[ddk_df["participant_id"].isin(test_ids)]

        vowel_model = _make_model().fit(vowel_train[VOWEL_FEATURES], vowel_train["label"])
        ddk_model = _make_model().fit(ddk_train[DDK_FEATURES], ddk_train["label"])

        vowel_test_prob = vowel_test.assign(
            pd_prob=vowel_model.predict_proba(vowel_test[VOWEL_FEATURES])[:, 1]
        ).groupby("participant_id")["pd_prob"].mean()
        ddk_test_prob = ddk_test.assign(
            pd_prob=ddk_model.predict_proba(ddk_test[DDK_FEATURES])[:, 1]
        ).groupby("participant_id")["pd_prob"].mean()

        # --- feature-level: single model trained on concatenated features ---
        train_participants = [p for p in train_ids if p in combined_feats.index]
        test_participants_fl = [p for p in test_ids if p in combined_feats.index]
        feat_model = _make_model().fit(
            combined_feats.loc[train_participants, combined_feature_cols],
            participants.set_index("participant_id").loc[train_participants, "label"],
        )
        feat_level_prob = pd.Series(
            feat_model.predict_proba(combined_feats.loc[test_participants_fl, combined_feature_cols])[:, 1],
            index=test_participants_fl,
        )

        # --- stacked: meta-learner on [vowel_prob, ddk_prob], fit via nested CV
        # on the TRAINING participants only (so the meta-learner never sees a
        # label it's later scored against) ---
        inner_cv = StratifiedKFold(n_splits=INNER_SPLITS, shuffle=True, random_state=RANDOM_STATE)
        train_participants_arr = participants.set_index("participant_id").loc[list(train_ids)]
        meta_rows = []
        for inner_train_idx, inner_val_idx in inner_cv.split(
            train_participants_arr.index, train_participants_arr["label"]
        ):
            inner_train_ids = set(train_participants_arr.index[inner_train_idx])
            inner_val_ids = set(train_participants_arr.index[inner_val_idx])

            iv_train = vowel_df[vowel_df["participant_id"].isin(inner_train_ids)]
            iv_val = vowel_df[vowel_df["participant_id"].isin(inner_val_ids)]
            id_train = ddk_df[ddk_df["participant_id"].isin(inner_train_ids)]
            id_val = ddk_df[ddk_df["participant_id"].isin(inner_val_ids)]

            iv_model = _make_model().fit(iv_train[VOWEL_FEATURES], iv_train["label"])
            id_model = _make_model().fit(id_train[DDK_FEATURES], id_train["label"])

            v_prob = iv_val.assign(p=iv_model.predict_proba(iv_val[VOWEL_FEATURES])[:, 1]).groupby("participant_id")["p"].mean()
            d_prob = id_val.assign(p=id_model.predict_proba(id_val[DDK_FEATURES])[:, 1]).groupby("participant_id")["p"].mean()

            for pid in inner_val_ids:
                if pid in v_prob.index and pid in d_prob.index:
                    label = int(participants.set_index("participant_id").loc[pid, "label"])
                    meta_rows.append({"vowel_prob": v_prob[pid], "ddk_prob": d_prob[pid], "label": label})

        meta_df = pd.DataFrame(meta_rows)
        meta_learner = LogisticRegression().fit(meta_df[["vowel_prob", "ddk_prob"]], meta_df["label"])

        # --- weighted-ensemble: each modality's weight is its own inner-CV
        # balanced accuracy (reusing the same out-of-fold meta_df above), so a
        # modality that's actually more reliable on the training participants
        # gets more say — distinct from stacked (which lets logistic
        # regression learn an arbitrary combining function) and from
        # decision-level (which is a fixed 50/50 average). ---
        vowel_inner_bal_acc = balanced_accuracy_score(meta_df["label"], (meta_df["vowel_prob"] >= 0.5).astype(int))
        ddk_inner_bal_acc = balanced_accuracy_score(meta_df["label"], (meta_df["ddk_prob"] >= 0.5).astype(int))
        weight_sum = vowel_inner_bal_acc + ddk_inner_bal_acc
        if weight_sum <= 0:
            vowel_weight, ddk_weight = 0.5, 0.5
        else:
            vowel_weight = vowel_inner_bal_acc / weight_sum
            ddk_weight = ddk_inner_bal_acc / weight_sum
        fold_vowel_weights.append(vowel_weight)

        test_meta_X = pd.DataFrame({
            "vowel_prob": vowel_test_prob,
            "ddk_prob": ddk_test_prob,
        }).dropna()
        stacked_prob = pd.Series(
            meta_learner.predict_proba(test_meta_X[["vowel_prob", "ddk_prob"]])[:, 1],
            index=test_meta_X.index,
        )

        for pid in sorted(test_ids):
            label = int(participants.loc[participants["participant_id"] == pid, "label"].iloc[0])
            v_prob = float(vowel_test_prob.get(pid, np.nan))
            d_prob = float(ddk_test_prob.get(pid, np.nan))
            decision_prob = (v_prob + d_prob) / 2
            weighted_prob = vowel_weight * v_prob + ddk_weight * d_prob
            rows.append({
                "fold": fold,
                "participant_id": pid,
                "label": label,
                "vowel_prob": v_prob,
                "ddk_prob": d_prob,
                "decision_level_prob": decision_prob,
                "feature_level_prob": float(feat_level_prob.get(pid, np.nan)),
                "stacked_prob": float(stacked_prob.get(pid, np.nan)),
                "weighted_ensemble_prob": weighted_prob,
                "weighted_ensemble_vowel_weight": vowel_weight,
            })

    out = pd.DataFrame(rows).sort_values("participant_id").reset_index(drop=True)
    for col, prob_col in [
        ("vowel_pred", "vowel_prob"),
        ("ddk_pred", "ddk_prob"),
        ("decision_level_pred", "decision_level_prob"),
        ("feature_level_pred", "feature_level_prob"),
        ("stacked_pred", "stacked_prob"),
        ("weighted_ensemble_pred", "weighted_ensemble_prob"),
    ]:
        out[col] = (out[prob_col] >= 0.5).astype(int)

    out_path = os.path.join(RESULTS_DIR, "italian_pvs_fusion_ablation_predictions.csv")
    out.to_csv(out_path, index=False)

    def _summarize(pred_col):
        acc = accuracy_score(out["label"], out[pred_col])
        bal_acc = balanced_accuracy_score(out["label"], out[pred_col])
        report = classification_report(out["label"], out[pred_col], target_names=["HC", "PD"], digits=4, output_dict=True)
        cm = confusion_matrix(out["label"], out[pred_col])
        return acc, bal_acc, report, cm

    metrics = {}
    strategy_cols = [
        ("vowel_only", "vowel_pred"),
        ("ddk_only", "ddk_pred"),
        ("decision_level", "decision_level_pred"),
        ("feature_level", "feature_level_pred"),
        ("stacked", "stacked_pred"),
        ("weighted_ensemble", "weighted_ensemble_pred"),
    ]
    print("\n=== Fusion ablation (participant-level, 5-fold CV) ===")
    for label, col in strategy_cols:
        acc, bal_acc, report, cm = _summarize(col)
        print(f"{label:16s} accuracy={acc:.4f}  balanced_accuracy={bal_acc:.4f}")
        metrics[label] = {
            "accuracy": float(acc),
            "balanced_accuracy": float(bal_acc),
            "classification_report": report,
            "confusion_matrix": cm.tolist(),
        }

    fig, axes = plt.subplots(1, len(strategy_cols), figsize=(4 * len(strategy_cols), 4))
    for ax, (label, col) in zip(axes, strategy_cols):
        cm = np.array(metrics[label]["confusion_matrix"])
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=["HC", "PD"])
        disp.plot(ax=ax, colorbar=False)
        ax.set_title(f"{label}\nacc={metrics[label]['accuracy']:.2f}")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "italian_pvs_fusion_ablation_confusion_matrices.png"), bbox_inches="tight")
    plt.close()

    best_strategy = max(strategy_cols, key=lambda sc: metrics[sc[0]]["balanced_accuracy"])[0]
    metrics["n_participants"] = int(len(participants))
    metrics["n_hc"] = int(sum(participants["label"] == 0))
    metrics["n_pd"] = int(sum(participants["label"] == 1))
    metrics["cv_splits"] = N_SPLITS
    metrics["best_strategy_by_balanced_accuracy"] = best_strategy
    metrics["does_fusion_beat_either_alone"] = bool(
        max(metrics["decision_level"]["balanced_accuracy"],
            metrics["feature_level"]["balanced_accuracy"],
            metrics["stacked"]["balanced_accuracy"],
            metrics["weighted_ensemble"]["balanced_accuracy"])
        > max(metrics["vowel_only"]["balanced_accuracy"], metrics["ddk_only"]["balanced_accuracy"])
    )

    metrics_path = os.path.join(RESULTS_DIR, "italian_pvs_fusion_ablation_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nBest strategy by balanced accuracy: {best_strategy}")
    print(f"Does any fusion strategy beat both single-biomarker models? {metrics['does_fusion_beat_either_alone']}")
    print(f"Saved metrics to {metrics_path}")
    print(f"Saved per-participant predictions to {out_path}")

    # Final artifacts fit on ALL participants, for the end-to-end screening pipeline.
    final_vowel_model = _make_model().fit(vowel_df[VOWEL_FEATURES], vowel_df["label"])
    final_ddk_model = _make_model().fit(ddk_df[DDK_FEATURES], ddk_df["label"])

    all_vowel_prob = vowel_df.assign(
        p=final_vowel_model.predict_proba(vowel_df[VOWEL_FEATURES])[:, 1]
    ).groupby("participant_id")["p"].mean()
    all_ddk_prob = ddk_df.assign(
        p=final_ddk_model.predict_proba(ddk_df[DDK_FEATURES])[:, 1]
    ).groupby("participant_id")["p"].mean()
    final_meta_df = pd.DataFrame({"vowel_prob": all_vowel_prob, "ddk_prob": all_ddk_prob}).dropna()
    final_meta_labels = participants.set_index("participant_id").loc[final_meta_df.index, "label"]
    final_meta_learner = LogisticRegression().fit(final_meta_df, final_meta_labels)

    fusion_model_path = os.path.join(MODELS_DIR, "fusion_italian_pvs.joblib")
    joblib.dump({
        "vowel_model": final_vowel_model,
        "vowel_feature_names": VOWEL_FEATURES,
        "ddk_model": final_ddk_model,
        "ddk_feature_names": DDK_FEATURES,
        "stacked_meta_learner": final_meta_learner,
        "best_strategy": best_strategy,
        "weighted_ensemble_vowel_weight": float(np.mean(fold_vowel_weights)),
    }, fusion_model_path)
    print(f"Saved fusion model bundle to {fusion_model_path}")


if __name__ == "__main__":
    main()
