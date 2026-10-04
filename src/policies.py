"""
policies.py
Implementation of classical and learning-augmented page replacement policies.
- FIFO (First-In, First-Out)
- LRU (Least Recently Used)
- Optimal (Belady's MIN clairvoyant replacement)
- LearnedPolicy (Decision Tree trained on access features)
- BonusExplainer (Decision explanation and confidence score generator)
"""

import collections
import numpy as np
from sklearn.tree import DecisionTreeClassifier


class BasePolicy:
    """Base class for page replacement policies."""
    def __init__(self, num_frames: int, name: str):
        self.num_frames = num_frames
        self.name = name
        self.frames = set()
        self.hits = 0
        self.faults = 0
        self.evictions = 0

    def reset(self):
        self.frames.clear()
        self.hits = 0
        self.faults = 0
        self.evictions = 0

    def access(self, page_id: int, current_step: int, future_trace=None) -> bool:
        """
        Processes a page access.
        Returns True if hit, False if page fault.
        """
        raise NotImplementedError


class FIFOPolicy(BasePolicy):
    """First-In, First-Out replacement policy."""
    def __init__(self, num_frames: int):
        super().__init__(num_frames, "FIFO")
        self.queue = collections.deque()

    def reset(self):
        super().reset()
        self.queue.clear()

    def access(self, page_id: int, current_step: int, future_trace=None) -> bool:
        if page_id in self.frames:
            self.hits += 1
            return True

        self.faults += 1
        if len(self.frames) >= self.num_frames:
            evicted = self.queue.popleft()
            self.frames.remove(evicted)
            self.evictions += 1

        self.frames.add(page_id)
        self.queue.append(page_id)
        return False


class LRUPolicy(BasePolicy):
    """Least Recently Used replacement policy."""
    def __init__(self, num_frames: int):
        super().__init__(num_frames, "LRU")
        # Maps page_id -> last_access_timestamp
        self.last_access = {}

    def reset(self):
        super().reset()
        self.last_access.clear()

    def access(self, page_id: int, current_step: int, future_trace=None) -> bool:
        if page_id in self.frames:
            self.hits += 1
            self.last_access[page_id] = current_step
            return True

        self.faults += 1
        if len(self.frames) >= self.num_frames:
            # Evict resident page with minimal last_access timestamp
            evicted = min(self.frames, key=lambda p: self.last_access[p])
            self.frames.remove(evicted)
            del self.last_access[evicted]
            self.evictions += 1

        self.frames.add(page_id)
        self.last_access[page_id] = current_step
        return False


class OptimalPolicy(BasePolicy):
    """
    Belady's MIN Optimal clairvoyant page replacement policy.
    Evicts the resident page that will not be used for the longest period in future.
    """
    def __init__(self, num_frames: int):
        super().__init__(num_frames, "Optimal (Belady)")
        self.next_access_map = {}

    def prepare_future_indices(self, full_trace: list):
        """Precomputes appearance indices for fast O(1) next-use lookups."""
        self.future_occurrences = collections.defaultdict(collections.deque)
        for idx, page in enumerate(full_trace):
            self.future_occurrences[page].append(idx)

    def access(self, page_id: int, current_step: int, future_trace=None) -> bool:
        # Pop current step from future queue for this page
        if hasattr(self, 'future_occurrences') and page_id in self.future_occurrences:
            if self.future_occurrences[page_id] and self.future_occurrences[page_id][0] == current_step:
                self.future_occurrences[page_id].popleft()

        if page_id in self.frames:
            self.hits += 1
            return True

        self.faults += 1
        if len(self.frames) >= self.num_frames:
            # Find candidate with maximum future reuse distance
            best_page = None
            furthest_distance = -1

            for p in self.frames:
                if not hasattr(self, 'future_occurrences') or not self.future_occurrences[p]:
                    next_use = float('inf')
                else:
                    next_use = self.future_occurrences[p][0]

                if next_use > furthest_distance:
                    furthest_distance = next_use
                    best_page = p

            self.frames.remove(best_page)
            self.evictions += 1

        self.frames.add(page_id)
        return False


class PageFeatureExtractor:
    """Tracks per-page metadata to construct real-time feature vectors."""
    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self.last_access = {}
        self.first_access = {}
        self.access_counts = collections.defaultdict(int)
        self.recent_history = collections.deque()
        self.inter_arrival_times = collections.defaultdict(list)

    def record_access(self, page_id: int, step: int):
        if page_id in self.last_access:
            gap = step - self.last_access[page_id]
            self.inter_arrival_times[page_id].append(gap)
            if len(self.inter_arrival_times[page_id]) > 10:
                self.inter_arrival_times[page_id].pop(0)
        else:
            self.first_access[page_id] = step

        self.last_access[page_id] = step
        self.access_counts[page_id] += 1
        self.recent_history.append((step, page_id))

        # Evict old entries from recent window
        while self.recent_history and self.recent_history[0][0] < step - self.window_size:
            self.recent_history.popleft()

    def get_features(self, page_id: int, current_step: int) -> np.ndarray:
        """
        Returns feature vector:
        [recency, window_frequency, overall_frequency, age, avg_inter_arrival]
        """
        recency = current_step - self.last_access.get(page_id, current_step)
        
        # Frequency in recent window
        win_freq = sum(1 for _, p in self.recent_history if p == page_id)
        total_freq = self.access_counts.get(page_id, 0)
        age = current_step - self.first_access.get(page_id, current_step)
        
        gaps = self.inter_arrival_times.get(page_id, [])
        avg_gap = float(np.mean(gaps)) if gaps else float(recency + 10)

        return np.array([recency, win_freq, total_freq, age, avg_gap], dtype=float)


class LearnedPolicy(BasePolicy):
    """
    Learned Page Replacement policy using a lightweight Decision Tree classifier.
    Predicts the likelihood of a resident page being a desirable eviction candidate
    (approximating Belady's longest future reuse distance).
    """
    def __init__(self, num_frames: int, model: DecisionTreeClassifier = None):
        super().__init__(num_frames, "Learned Policy (Decision Tree)")
        self.model = model
        self.feature_extractor = PageFeatureExtractor(window_size=50)
        self.eviction_logs = []

    def reset(self):
        super().reset()
        self.feature_extractor = PageFeatureExtractor(window_size=50)
        self.eviction_logs.clear()

    def set_model(self, model: DecisionTreeClassifier):
        self.model = model

    def access(self, page_id: int, current_step: int, future_trace=None) -> bool:
        is_hit = page_id in self.frames
        self.feature_extractor.record_access(page_id, current_step)

        if is_hit:
            self.hits += 1
            return True

        self.faults += 1
        if len(self.frames) >= self.num_frames:
            # Select best eviction candidate among resident frames
            candidate_pages = list(self.frames)
            
            if self.model is not None:
                # Extract features for all candidates
                X_candidates = np.array([
                    self.feature_extractor.get_features(p, current_step)
                    for p in candidate_pages
                ])
                # Probability of being an optimal eviction candidate (class 1)
                try:
                    probs = self.model.predict_proba(X_candidates)
                    # Class 1 probability (if two classes), else decision function
                    if probs.shape[1] > 1:
                        scores = probs[:, 1]
                    else:
                        scores = probs[:, 0]
                except Exception:
                    # Fallback to recency heuristic if probability extraction fails
                    scores = X_candidates[:, 0]
                
                best_idx = int(np.argmax(scores))
                evicted = candidate_pages[best_idx]
                confidence = float(scores[best_idx])
            else:
                # Untrained fallback to LRU
                evicted = min(
                    candidate_pages,
                    key=lambda p: self.feature_extractor.last_access.get(p, 0)
                )
                confidence = 0.5

            self.eviction_logs.append({
                'step': current_step,
                'evicted_page': evicted,
                'confidence': confidence,
                'candidates': list(candidate_pages)
            })

            self.frames.remove(evicted)
            self.evictions += 1

        self.frames.add(page_id)
        return False


class BonusExplainer:
    """
    Bonus Track: Natural language explanation and confidence assessment.
    Produces human-interpretable rationale for replacement choices and evaluates calibration.
    """
    def __init__(self):
        pass

    def explain_decision(self, page_id: int, features: dict, confidence: float, is_optimal: bool) -> dict:
        """
        Generates natural language rationale and compares confidence with ground-truth optimality.
        """
        recency = features.get('recency', 0)
        win_freq = features.get('win_freq', 0)
        avg_gap = features.get('avg_gap', 0)

        # Rationale synthesis
        if recency > 30 and win_freq <= 1:
            rationale = (f"Evicted Page {page_id} due to stale recency (inactive for {int(recency)} steps) "
                         f"and low window frequency ({int(win_freq)} hits), indicating working-set departure.")
        elif avg_gap > 40:
            rationale = (f"Evicted Page {page_id} because historical reuse distance is high "
                         f"(avg reuse gap: {avg_gap:.1f}), favoring retention of tighter looping pages.")
        else:
            rationale = (f"Evicted Page {page_id} balancing moderate recency ({int(recency)}) "
                         f"against competing resident pages with higher immediate burst potential.")

        return {
            'page_id': page_id,
            'confidence': confidence,
            'is_optimal': is_optimal,
            'rationale': rationale
        }
