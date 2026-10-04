"""
runner.py
Experiment orchestrator for evaluating FIFO, LRU, Optimal (Belady), and Learned Policies.
Collects split metrics (Pre-shift vs Post-shift), timeline series, cache size sensitivity,
and confidence calibration statistics for the bonus track.
"""

import collections
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from src.policies import FIFOPolicy, LRUPolicy, OptimalPolicy, LearnedPolicy, BonusExplainer
from src.workload import generate_synthetic_trace, build_training_dataset


def run_single_simulation(policy, trace: list[int], shift_step: int = 5000, is_optimal: bool = False):
    """
    Executes a simulation run, recording pre-shift, post-shift, and windowed timeline metrics.
    """
    policy.reset()
    if is_optimal:
        policy.prepare_future_indices(trace)

    p1_hits = 0
    p1_faults = 0
    p2_hits = 0
    p2_faults = 0

    timeline_hits = []
    window = collections.deque(maxlen=200)
    rolling_hit_ratios = []

    for step, page in enumerate(trace):
        hit = policy.access(page, step)
        window.append(1 if hit else 0)
        rolling_hit_ratios.append(sum(window) / len(window))

        if step < shift_step:
            if hit:
                p1_hits += 1
            else:
                p1_faults += 1
        else:
            if hit:
                p2_hits += 1
            else:
                p2_faults += 1

    total_hits = p1_hits + p2_hits
    total_faults = p1_faults + p2_faults
    total_steps = len(trace)

    return {
        'policy_name': policy.name,
        'p1_hits': p1_hits,
        'p1_faults': p1_faults,
        'p1_hit_ratio': p1_hits / shift_step,
        'p2_hits': p2_hits,
        'p2_faults': p2_faults,
        'p2_hit_ratio': p2_hits / (total_steps - shift_step),
        'total_hits': total_hits,
        'total_faults': total_faults,
        'total_hit_ratio': total_hits / total_steps,
        'rolling_hit_ratios': rolling_hit_ratios
    }


def evaluate_confidence_calibration(learned_policy, trace, shift_step, num_frames):
    """
    Evaluates how well the learned classifier's confidence scores align with true Belady optimality.
    """
    # Create oracle to compute ground-truth Belady decisions at every step
    oracle = OptimalPolicy(num_frames=num_frames)
    oracle.prepare_future_indices(trace)
    explainer = BonusExplainer()

    calibration_records = []
    sample_explanations = []

    # Run learned policy and track decisions
    learned_policy.reset()
    for step, page in enumerate(trace):
        # Update oracle future queues
        if page in oracle.future_occurrences and oracle.future_occurrences[page]:
            if oracle.future_occurrences[page][0] == step:
                oracle.future_occurrences[page].popleft()

        hit = learned_policy.access(page, step)

        if not hit and learned_policy.eviction_logs and learned_policy.eviction_logs[-1]['step'] == step:
            # An eviction just happened in learned policy
            last_eviction = learned_policy.eviction_logs[-1]
            evicted_page = last_eviction['evicted_page']
            conf = last_eviction['confidence']
            candidates = last_eviction['candidates']

            # Find Belady choice among the exact candidate set available to the learned policy
            furthest_dist = -1
            belady_pick = None
            for p in candidates:
                nxt = oracle.future_occurrences[p][0] if (p in oracle.future_occurrences and oracle.future_occurrences[p]) else float('inf')
                if nxt > furthest_dist:
                    furthest_dist = nxt
                    belady_pick = p

            is_optimal = (evicted_page == belady_pick)
            calibration_records.append({
                'step': step,
                'is_p2': (step >= shift_step),
                'confidence': conf,
                'is_optimal': int(is_optimal)
            })

            if len(sample_explanations) < 5 and step > 100:
                feat = learned_policy.feature_extractor.get_features(evicted_page, step)
                feat_dict = {
                    'recency': feat[0],
                    'win_freq': feat[1],
                    'avg_gap': feat[4]
                }
                explanation = explainer.explain_decision(evicted_page, feat_dict, conf, is_optimal)
                sample_explanations.append(explanation)

        # Maintain oracle frame state for parity
        if page in oracle.frames:
            pass
        else:
            if len(oracle.frames) >= oracle.num_frames:
                # Evict optimal
                furthest_dist = -1
                b_pick = None
                for p in oracle.frames:
                    nxt = oracle.future_occurrences[p][0] if (p in oracle.future_occurrences and oracle.future_occurrences[p]) else float('inf')
                    if nxt > furthest_dist:
                        furthest_dist = nxt
                        b_pick = p
                oracle.frames.remove(b_pick)
            oracle.frames.add(page)

    df_calib = pd.DataFrame(calibration_records)
    return df_calib, sample_explanations
