"""
run_experiments.py
Main experiment driver for CSE-307 Term Paper (Track 1: Learned Page Replacement).
Executes all benchmarks, collects empirical metrics, produces CSV artifacts, and generates publication plots.
"""

import os
import sys
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

# Ensure local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.policies import FIFOPolicy, LRUPolicy, OptimalPolicy, LearnedPolicy
from src.workload import generate_synthetic_trace, build_training_dataset
from src.runner import run_single_simulation, evaluate_confidence_calibration
from src.visualize import (
    plot_hit_ratio_comparison,
    plot_hit_ratio_over_time,
    plot_cache_size_sensitivity,
    plot_confidence_calibration
)


def main():
    print("=" * 75)
    print("CSE-307: OPERATING SYSTEMS TERM PAPER EXPERIMENTAL EVALUATION")
    print("Track 1: Learned Page Replacement (Memory Management)")
    print("Student: Turjoy Barua | ID: 202414084 | Dept: CSE")
    print("=" * 75)

    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    figures_dir = os.path.join(results_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)

    # 1. Generate Synthetic Trace with deliberate shift at step 5000
    print("\n[Step 1] Generating synthetic page reference trace (N = 10,000)...")
    trace, meta = generate_synthetic_trace(total_steps=10000, shift_step=5000, seed=42)
    print(f"  - Phase 1 (Locality-heavy): Steps 0 -> {meta['shift_step']-1} ({meta['phase1_unique_pages']} unique pages)")
    print(f"  - Phase 2 (Random / Bursty): Steps {meta['shift_step']} -> {meta['total_steps']-1} ({meta['phase2_unique_pages']} unique pages)")
    print(f"  - Total unique pages across entire workload: {meta['total_unique_pages']}")

    # 2. Train Learned Decision Tree Model on Oracle Eviction Decisions
    print("\n[Step 2] Extracting training dataset and fitting Decision Tree classifier...")
    X_train, y_train = build_training_dataset(train_trace_length=3000, num_frames=16, seed=101)
    print(f"  - Training samples extracted: {len(X_train)} (Positive eviction targets: {np.sum(y_train)})")
    
    dt_model = DecisionTreeClassifier(max_depth=5, min_samples_leaf=10, random_state=42)
    dt_model.fit(X_train, y_train)
    train_acc = dt_model.score(X_train, y_train)
    print(f"  - Decision Tree fitted successfully. Training accuracy: {train_acc * 100:.2f}%")
    feature_names = ['Recency', 'Win_Freq', 'Total_Freq', 'Age', 'Avg_Inter_Arrival']
    print("  - Feature Importances:")
    for name, imp in zip(feature_names, dt_model.feature_importances_):
        print(f"    * {name:18s}: {imp:.4f}")

    # 3. Benchmark Base Policies under M = 16 frames
    print("\n[Step 3] Running simulation across policies with M = 16 physical frames...")
    base_frame_size = 16
    policies = [
        FIFOPolicy(num_frames=base_frame_size),
        LRUPolicy(num_frames=base_frame_size),
        LearnedPolicy(num_frames=base_frame_size, model=dt_model),
        OptimalPolicy(num_frames=base_frame_size)
    ]

    summary_rows = []
    timeline_dict = {'step': list(range(len(trace)))}

    for policy in policies:
        is_opt = isinstance(policy, OptimalPolicy)
        print(f"  - Evaluating {policy.name}...")
        res = run_single_simulation(policy, trace, shift_step=5000, is_optimal=is_opt)

        summary_rows.append({
            'Policy': policy.name,
            'Phase 1 Faults': res['p1_faults'],
            'Phase 1 Hits': res['p1_hits'],
            'Phase 1 Hit Ratio': res['p1_hit_ratio'],
            'Phase 2 Faults': res['p2_faults'],
            'Phase 2 Hits': res['p2_hits'],
            'Phase 2 Hit Ratio': res['p2_hit_ratio'],
            'Overall Faults': res['total_faults'],
            'Overall Hits': res['total_hits'],
            'Overall Hit Ratio': res['total_hit_ratio']
        })
        timeline_dict[policy.name] = res['rolling_hit_ratios']

    summary_df = pd.DataFrame(summary_rows)
    metrics_path = os.path.join(results_dir, "metrics_summary.csv")
    summary_df.to_csv(metrics_path, index=False)
    print(f"\n[Saved] Performance metrics saved to: {metrics_path}")

    # Print clean table to console
    print("\n" + "=" * 95)
    print(f"{'Policy':<30} | {'P1 Hit Ratio':<12} | {'P2 Hit Ratio':<12} | {'Overall Hit Ratio':<18} | {'Total Faults':<12}")
    print("-" * 95)
    for _, row in summary_df.iterrows():
        print(f"{row['Policy']:<30} | {row['Phase 1 Hit Ratio']*100:>10.2f}% | {row['Phase 2 Hit Ratio']*100:>10.2f}% | {row['Overall Hit Ratio']*100:>16.2f}% | {row['Overall Faults']:>12}")
    print("=" * 95)

    timeline_df = pd.DataFrame(timeline_dict)
    timeline_path = os.path.join(results_dir, "timeline_trace.csv")
    timeline_df.to_csv(timeline_path, index=False)

    # 4. Sensitivity Analysis across Frame Capacities (M in [4, 8, 16, 32, 64])
    print("\n[Step 4] Running sensitivity analysis across physical frame allocations...")
    frame_sizes = [4, 8, 16, 32, 64]
    frame_records = []

    for M in frame_sizes:
        print(f"  - Frame capacity M = {M}...")
        # Train frame-matched tree for fair comparison
        X_m, y_m = build_training_dataset(train_trace_length=2000, num_frames=M, seed=101 + M)
        m_model = DecisionTreeClassifier(max_depth=5, min_samples_leaf=5, random_state=42)
        m_model.fit(X_m, y_m)

        test_policies = [
            FIFOPolicy(num_frames=M),
            LRUPolicy(num_frames=M),
            LearnedPolicy(num_frames=M, model=m_model),
            OptimalPolicy(num_frames=M)
        ]

        for p in test_policies:
            res = run_single_simulation(p, trace, shift_step=5000, is_optimal=isinstance(p, OptimalPolicy))
            frame_records.append({
                'Frames': M,
                'Policy': p.name,
                'P1_Hit_Ratio': res['p1_hit_ratio'],
                'P2_Hit_Ratio': res['p2_hit_ratio'],
                'Overall_Hit_Ratio': res['total_hit_ratio'],
                'Total_Faults': res['total_faults']
            })

    frame_df = pd.DataFrame(frame_records)
    scaling_path = os.path.join(results_dir, "cache_scaling.csv")
    frame_df.to_csv(scaling_path, index=False)
    print(f"[Saved] Sensitivity scaling data saved to: {scaling_path}")

    # 5. Bonus Track: Confidence Calibration & Natural Language Explanations
    print("\n[Step 5] Evaluating Bonus Track: Confidence Calibration and Decision Explanations...")
    eval_learned = LearnedPolicy(num_frames=base_frame_size, model=dt_model)
    df_calib, sample_explanations = evaluate_confidence_calibration(eval_learned, trace, shift_step=5000, num_frames=base_frame_size)
    calib_path = os.path.join(results_dir, "calibration_data.csv")
    df_calib.to_csv(calib_path, index=False)

    explanations_path = os.path.join(results_dir, "sample_explanations.txt")
    with open(explanations_path, "w") as f:
        f.write("SAMPLE DECISION EXPLANATIONS (BONUS TRACK)\n")
        f.write("=" * 60 + "\n\n")
        for i, item in enumerate(sample_explanations, 1):
            f.write(f"Sample {i}:\n")
            f.write(f"  Evicted Page: {item['page_id']}\n")
            f.write(f"  Confidence:   {item['confidence']:.3f}\n")
            f.write(f"  Belady MIN Optimality: {'Optimal' if item['is_optimal'] else 'Sub-optimal'}\n")
            f.write(f"  Explanation:  {item['rationale']}\n\n")
    print(f"[Saved] Calibration data and explanations saved.")

    # 6. Render High-Resolution Figures
    print("\n[Step 6] Generating publication-quality visualization figures...")
    plot_hit_ratio_comparison(summary_df, os.path.join(figures_dir, "hit_ratio_comparison.png"))
    plot_hit_ratio_over_time(timeline_df, shift_step=5000, output_path=os.path.join(figures_dir, "hit_ratio_over_time.png"))
    plot_cache_size_sensitivity(frame_df, os.path.join(figures_dir, "cache_size_sensitivity.png"))
    plot_confidence_calibration(df_calib, os.path.join(figures_dir, "confidence_calibration.png"))
    print("  * results/figures/hit_ratio_comparison.png created")
    print("  * results/figures/hit_ratio_over_time.png created")
    print("  * results/figures/cache_size_sensitivity.png created")
    print("  * results/figures/confidence_calibration.png created")

    print("\n[Success] Experimental pipeline complete! Ready for report generation.")


if __name__ == "__main__":
    main()
