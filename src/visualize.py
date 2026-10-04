"""
visualize.py
Generates publication-quality charts for the term paper:
1. hit_ratio_comparison.png: Pre-shift vs Post-shift hit ratio comparison.
2. hit_ratio_over_time.png: Rolling hit ratio trace highlighting the workload shift at step 5000.
3. cache_size_sensitivity.png: Hit ratio scaling across physical frame allocations (4 to 64).
4. confidence_calibration.png: Bonus track reliability diagram (predicted confidence vs empirical optimality).
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os

# Set clean academic styling
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 11
plt.rcParams['axes.labelsize'] = 10
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['figure.titlesize'] = 12


def plot_hit_ratio_comparison(summary_df: pd.DataFrame, output_path: str):
    """Grouped bar chart for Phase 1 vs Phase 2 vs Overall hit ratios."""
    policies = summary_df['Policy'].tolist()
    p1_ratios = [val * 100 for val in summary_df['Phase 1 Hit Ratio']]
    p2_ratios = [val * 100 for val in summary_df['Phase 2 Hit Ratio']]
    overall_ratios = [val * 100 for val in summary_df['Overall Hit Ratio']]

    x = np.arange(len(policies))
    width = 0.25

    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=300)

    rects1 = ax.bar(x - width, p1_ratios, width, label='Phase 1 (Locality-Heavy)', color='#2b5c8f', edgecolor='black', linewidth=0.6)
    rects2 = ax.bar(x, p2_ratios, width, label='Phase 2 (Random / Bursty)', color='#d95f02', edgecolor='black', linewidth=0.6)
    rects3 = ax.bar(x + width, overall_ratios, width, label='Cumulative Overall', color='#7570b3', edgecolor='black', linewidth=0.6)

    ax.set_ylabel('Hit Ratio (%)')
    ax.set_title('Page Replacement Performance: Pre-Shift vs. Post-Shift (Frames = 16)', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(policies, fontweight='medium')
    ax.legend(frameon=True, facecolor='white', framealpha=0.9)
    ax.set_ylim(0, 100)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    # Add value labels
    for rects in (rects1, rects2, rects3):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.1f}%',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 2),  # 2 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=7.5)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()


def plot_hit_ratio_over_time(timeline_df: pd.DataFrame, shift_step: int, output_path: str):
    """Rolling hit ratio over time showing the impact of the shift at t = shift_step."""
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=300)

    colors = {
        'FIFO': '#7f7f7f',
        'LRU': '#1f77b4',
        'Learned Policy (Decision Tree)': '#2ca02c',
        'Optimal (Belady)': '#d62728'
    }

    for col in timeline_df.columns:
        if col == 'step':
            continue
        c = colors.get(col, '#333333')
        lw = 2.0 if 'Optimal' in col or 'Learned' in col else 1.2
        ax.plot(timeline_df['step'], timeline_df[col] * 100, label=col, color=c, linewidth=lw, alpha=0.85)

    # Mark shift step
    ax.axvline(x=shift_step, color='#b2182b', linestyle='--', linewidth=1.5, label='Workload Shift (t = 5000)')
    ax.annotate('Regime Shift\n(Locality -> Random/Bursty)', xy=(shift_step, 65), xytext=(shift_step + 300, 75),
                arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=5),
                fontsize=8.5, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="#fffae0", ec="#b2182b", lw=1))

    ax.set_xlabel('Memory Access Sequence Step')
    ax.set_ylabel('Rolling Hit Ratio (Window = 200) [%]')
    ax.set_title('Dynamic Hit Ratio Evolution Across Workload Regime Shift', fontweight='bold')
    ax.set_xlim(0, timeline_df['step'].max())
    ax.set_ylim(0, 100)
    ax.legend(loc='lower left', frameon=True, framealpha=0.9)
    ax.grid(True, linestyle=':', alpha=0.6)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()


def plot_cache_size_sensitivity(frame_results_df: pd.DataFrame, output_path: str):
    """Hit ratio vs frame capacity for Phase 1 and Phase 2."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 4.0), dpi=300, sharey=True)

    policies = frame_results_df['Policy'].unique()
    markers = {'FIFO': 's', 'LRU': 'o', 'Learned Policy (Decision Tree)': '^', 'Optimal (Belady)': 'D'}
    colors = {'FIFO': '#7f7f7f', 'LRU': '#1f77b4', 'Learned Policy (Decision Tree)': '#2ca02c', 'Optimal (Belady)': '#d62728'}

    for p in policies:
        sub = frame_results_df[frame_results_df['Policy'] == p]
        ax1.plot(sub['Frames'], sub['P1_Hit_Ratio'] * 100, marker=markers.get(p, 'o'), color=colors.get(p, 'k'),
                 linewidth=1.5, label=p)
        ax2.plot(sub['Frames'], sub['P2_Hit_Ratio'] * 100, marker=markers.get(p, 'o'), color=colors.get(p, 'k'),
                 linewidth=1.5, label=p)

    ax1.set_title('(a) Phase 1: High Locality Working Set', fontweight='bold', fontsize=10)
    ax1.set_xlabel('Allocated Physical Frames (M)')
    ax1.set_ylabel('Hit Ratio (%)')
    ax1.set_xticks([4, 8, 16, 32, 64])
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(loc='lower right', fontsize=8)

    ax2.set_title('(b) Phase 2: Random / Bursty Working Set', fontweight='bold', fontsize=10)
    ax2.set_xlabel('Allocated Physical Frames (M)')
    ax2.set_xticks([4, 8, 16, 32, 64])
    ax2.grid(True, linestyle=':', alpha=0.6)

    fig.suptitle('Sensitivity Analysis: Frame Capacity vs. Memory Hit Ratios', fontweight='bold', fontsize=11)
    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()


def plot_confidence_calibration(df_calib: pd.DataFrame, output_path: str):
    """Reliability diagram comparing predicted model confidence to empirical optimality."""
    # Bin confidence scores
    bins = np.linspace(0.0, 1.0, 6)
    df_calib['bin'] = pd.cut(df_calib['confidence'], bins=bins, include_lowest=True)

    grouped = df_calib.groupby('bin', observed=False).agg(
        mean_conf=('confidence', 'mean'),
        empirical_acc=('is_optimal', 'mean'),
        count=('is_optimal', 'count')
    ).reset_index()

    fig, ax = plt.subplots(figsize=(6.5, 4.2), dpi=300)

    # Reference diagonal (perfect calibration)
    ax.plot([0, 1], [0, 1], linestyle='--', color='gray', label='Perfect Calibration (Oracle)')

    valid = grouped.dropna()
    ax.plot(valid['mean_conf'], valid['empirical_acc'], marker='s', markersize=7, color='#2b5c8f',
            linewidth=2, label='Learned Decision Tree')

    # Bar distribution underneath
    ax2 = ax.twinx()
    ax2.bar(valid['mean_conf'], valid['count'], width=0.08, alpha=0.18, color='#2ca02c', label='Eviction Count')
    ax2.set_ylabel('Eviction Decision Count', color='#2ca02c')
    ax2.tick_params(axis='y', labelcolor='#2ca02c')
    ax2.grid(False)

    ax.set_xlabel('Model Predicted Eviction Confidence')
    ax.set_ylabel('Empirical Belady Optimality Rate')
    ax.set_title('Bonus Track: Confidence Calibration Reliability Diagram', fontweight='bold')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(loc='upper left', frameon=True)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
