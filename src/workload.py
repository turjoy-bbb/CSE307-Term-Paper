"""
workload.py
Generates synthetic page-access traces with controlled workload shifts.
Phase 1: Locality-heavy (Zipfian skew + sequential looping).
Shift Point: Step 5000.
Phase 2: Low-locality, bursty, uniform random distribution (cache thrashing).
Also provides training set generation using Belady's optimal eviction labels.
"""

import numpy as np
from src.policies import PageFeatureExtractor, OptimalPolicy


def generate_synthetic_trace(
    total_steps: int = 10000,
    shift_step: int = 5000,
    seed: int = 42
) -> tuple[list[int], dict]:
    """
    Generates a 10,000-reference page access trace with a deliberate workload shift at step 5000.
    Returns:
        trace: list of integer page IDs
        meta: dictionary with trace characteristics
    """
    rng = np.random.default_rng(seed)
    trace = []

    # Phase 1: High Locality (Steps 0 -> shift_step - 1)
    # Working set: Hot pages (1 to 15), Loop pages (20 to 35), Cold pages (40 to 100)
    hot_pages = list(range(1, 16))
    loop_pages = list(range(20, 36))
    loop_idx = 0

    for step in range(shift_step):
        p_type = rng.random()
        if p_type < 0.70:
            # 70% Skewed Zipfian distribution on hot working set
            # High temporal locality
            zipf_val = rng.zipf(1.6) % len(hot_pages)
            trace.append(hot_pages[zipf_val])
        elif p_type < 0.90:
            # 20% Sequential cyclic loops (spatial locality)
            trace.append(loop_pages[loop_idx % len(loop_pages)])
            loop_idx += 1
        else:
            # 10% Background noise / cold misses
            trace.append(rng.integers(50, 120))

    # Phase 2: Shifted Workload - Random & Bursty Scans (Steps shift_step -> total_steps - 1)
    # Large page space: 100 to 400 (exceeds cache capacity, zero temporal reuse)
    burst_pool = []
    for step in range(shift_step, total_steps):
        p_type = rng.random()
        if p_type < 0.65:
            # 65% Uniform random over wide address space (cache thrashing)
            trace.append(int(rng.integers(100, 400)))
        elif p_type < 0.90:
            # 25% Bursty streaming access (each page accessed twice then abandoned)
            if not burst_pool or rng.random() < 0.3:
                new_burst = list(rng.integers(500, 900, size=5))
                burst_pool.extend(new_burst)
            trace.append(int(burst_pool.pop(0) if burst_pool else rng.integers(100, 400)))
        else:
            # 10% Occasional residual hot hits
            trace.append(int(rng.choice(hot_pages)))

    meta = {
        'total_steps': total_steps,
        'shift_step': shift_step,
        'phase1_length': shift_step,
        'phase2_length': total_steps - shift_step,
        'phase1_unique_pages': len(set(trace[:shift_step])),
        'phase2_unique_pages': len(set(trace[shift_step:])),
        'total_unique_pages': len(set(trace))
    }
    return trace, meta


def build_training_dataset(
    train_trace_length: int = 3000,
    num_frames: int = 16,
    seed: int = 101
) -> tuple[np.ndarray, np.ndarray]:
    """
    Generates a representative training trace under Phase 1 locality conditions,
    runs Belady's Optimal algorithm, and records feature vectors for candidate pages
    labeled with 1 (chosen for eviction) and 0 (retained).
    """
    rng = np.random.default_rng(seed)
    hot_pages = list(range(1, 16))
    loop_pages = list(range(20, 36))
    train_trace = []
    loop_idx = 0

    for _ in range(train_trace_length):
        p = rng.random()
        if p < 0.70:
            zipf_val = rng.zipf(1.6) % len(hot_pages)
            train_trace.append(hot_pages[zipf_val])
        elif p < 0.90:
            train_trace.append(loop_pages[loop_idx % len(loop_pages)])
            loop_idx += 1
        else:
            train_trace.append(int(rng.integers(50, 120)))

    # Run Belady's MIN algorithm to collect oracle decisions
    optimal = OptimalPolicy(num_frames=num_frames)
    optimal.prepare_future_indices(train_trace)
    extractor = PageFeatureExtractor(window_size=50)

    X_list = []
    y_list = []

    for step, page_id in enumerate(train_trace):
        extractor.record_access(page_id, step)
        
        # Advance future queue
        if page_id in optimal.future_occurrences and optimal.future_occurrences[page_id]:
            if optimal.future_occurrences[page_id][0] == step:
                optimal.future_occurrences[page_id].popleft()

        if page_id in optimal.frames:
            continue

        # Eviction needed
        if len(optimal.frames) >= optimal.num_frames:
            # Find Belady target
            best_page = None
            furthest_distance = -1
            for p in optimal.frames:
                next_use = optimal.future_occurrences[p][0] if (p in optimal.future_occurrences and optimal.future_occurrences[p]) else float('inf')
                if next_use > furthest_distance:
                    furthest_distance = next_use
                    best_page = p

            # Extract features for all resident candidates
            for p in optimal.frames:
                feat = extractor.get_features(p, step)
                label = 1 if p == best_page else 0
                X_list.append(feat)
                y_list.append(label)

            optimal.frames.remove(best_page)

        optimal.frames.add(page_id)

    X = np.array(X_list, dtype=float)
    y = np.array(y_list, dtype=int)
    return X, y
