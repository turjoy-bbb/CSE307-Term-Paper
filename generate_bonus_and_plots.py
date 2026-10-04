"""
generate_bonus_and_plots.py
Generates the bonus track calibration data, sample explanations,
and renders the 4 publication-quality visualization figures.
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Ensure local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.policies import LearnedPolicy, OptimalPolicy, BonusExplainer
from src.workload import generate_synthetic_trace, build_training_dataset
from src.runner import evaluate_confidence_calibration
from src.visualize import (
    plot_hit_ratio_comparison,
    plot_hit_ratio_over_time,
    plot_cache_size_sensitivity,
    plot_confidence_calibration
)
from sklearn.tree import DecisionTreeClassifier


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    results_dir = os.path.join(base_dir, "results")
    figures_dir = os.path.join(results_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)

    print("Generating Bonus Track and Figures...")

    # Load existing summary and timeline data if available
    summary_path = os.path.join(results_dir, "metrics_summary.csv")
    timeline_path = os.path.join(results_dir, "timeline_trace.csv")
    scaling_path = os.path.join(results_dir, "cache_scaling.csv")

    summary_df = pd.read_csv(summary_path)
    timeline_df = pd.read_csv(timeline_path)
    scaling_df = pd.read_csv(scaling_path)

    # 1. Regenerate trace & model for calibration evaluation
    trace, meta = generate_synthetic_trace(total_steps=10000, shift_step=5000, seed=42)
    X_train, y_train = build_training_dataset(train_trace_length=3000, num_frames=16, seed=101)
    dt_model = DecisionTreeClassifier(max_depth=5, min_samples_leaf=10, random_state=42)
    dt_model.fit(X_train, y_train)

    learned_policy = LearnedPolicy(num_frames=16, model=dt_model)
    df_calib, sample_explanations = evaluate_confidence_calibration(
        learned_policy, trace, shift_step=5000, num_frames=16
    )

    calib_path = os.path.join(results_dir, "calibration_data.csv")
    df_calib.to_csv(calib_path, index=False)
    print(f"Calibration data saved to {calib_path} ({len(df_calib)} records).")

    explanations_path = os.path.join(results_dir, "sample_explanations.txt")
    with open(explanations_path, "w", encoding="utf-8") as f:
        f.write("CSE-307 OS TERM PAPER: BONUS TRACK - DECISION EXPLANATIONS & CONFIDENCE\n")
        f.write("Student: Turjoy Barua (ID: 202414084)\n")
        f.write("=" * 70 + "\n\n")
        for i, item in enumerate(sample_explanations, 1):
            f.write(f"Sample Decision #{i}:\n")
            f.write(f"  Target Page:         Page {item['page_id']}\n")
            f.write(f"  Model Confidence:    {item['confidence'] * 100:.1f}%\n")
            f.write(f"  Belady MIN Status:   {'Optimal (True Clairvoyant Target)' if item['is_optimal'] else 'Sub-optimal Heuristic Choice'}\n")
            f.write(f"  Generated Rationale: {item['rationale']}\n\n")
    print(f"Sample explanations saved to {explanations_path}.")

    # 2. Render all 4 figures
    fig1 = os.path.join(figures_dir, "hit_ratio_comparison.png")
    fig2 = os.path.join(figures_dir, "hit_ratio_over_time.png")
    fig3 = os.path.join(figures_dir, "cache_size_sensitivity.png")
    fig4 = os.path.join(figures_dir, "confidence_calibration.png")

    plot_hit_ratio_comparison(summary_df, fig1)
    print(f"Generated: {fig1}")

    plot_hit_ratio_over_time(timeline_df, shift_step=5000, output_path=fig2)
    print(f"Generated: {fig2}")

    plot_cache_size_sensitivity(scaling_df, fig3)
    print(f"Generated: {fig3}")

    plot_confidence_calibration(df_calib, fig4)
    print(f"Generated: {fig4}")

    print("\nAll figures and bonus deliverables generated successfully!")


if __name__ == "__main__":
    main()
