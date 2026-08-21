"""ToeholdDesignBench v0.3.0 single evaluator package.

All tracks and analyses consume this one kernel (contract §9 Batch 2):
no per-module metric re-implementations, no sampled random baselines,
analytic tie handling everywhere, loud failures on incomplete scores.
"""
__version__ = "0.3.0"
