"""
Just-in-time (JIT) defect prediction: which changes are likely to introduce a bug.

    git_history   read commits and per-file line changes from a local clone
    szz           label bug-introducing commits (SZZ, Sliwerski et al. 2005)
    features      Kamei et al. (2013) change metrics, computed from history
    model         logistic regression and gradient-boosted stumps (pure Python)
                  with per-feature explanations
    predictor     train a project's bundle (candidate selection on a held-out
                  period) and score a new PR from the saved history state

Evaluation: evaluation/evaluate_risk_model.py. Design and results: RISK_MODEL.md.

Standard library only; git is called with argument lists (never a shell).
"""
