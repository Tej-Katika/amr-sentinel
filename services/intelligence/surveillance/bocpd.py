"""Bayesian Online Changepoint Detection (Adams & MacKay, 2007).

Beta-Bernoulli conjugate model for binary AMR data. Maintains a posterior
distribution over run lengths (time since last changepoint).
"""
from __future__ import annotations

import numpy as np


class BOCPD:
    def __init__(
        self,
        hazard_rate: float = 1 / 250,
        max_run_length: int = 500,
        alpha_prior: float = 1.0,
        beta_prior: float = 1.0,
        changepoint_threshold: float = 0.5,
    ) -> None:
        self.hazard = hazard_rate
        self.max_rl = max_run_length
        self.alpha0 = alpha_prior
        self.beta0 = beta_prior
        self.threshold = changepoint_threshold

        self.run_length_probs = np.array([1.0])
        self.alphas = np.array([alpha_prior])
        self.betas = np.array([beta_prior])

    def update(self, observation: int) -> tuple[bool, float]:
        T = len(self.run_length_probs)

        pred_probs = self.alphas / (self.alphas + self.betas)
        likelihoods = pred_probs if observation == 1 else (1.0 - pred_probs)

        growth_probs = self.run_length_probs * likelihoods * (1 - self.hazard)
        changepoint_prob = float(np.sum(self.run_length_probs * likelihoods * self.hazard))

        new_probs = np.zeros(T + 1)
        new_probs[0] = changepoint_prob
        new_probs[1:T + 1] = growth_probs

        evidence = new_probs.sum()
        if evidence > 0:
            new_probs /= evidence

        new_alphas = np.zeros(T + 1)
        new_betas = np.zeros(T + 1)
        new_alphas[0] = self.alpha0
        new_betas[0] = self.beta0
        new_alphas[1:T + 1] = self.alphas + observation
        new_betas[1:T + 1] = self.betas + (1 - observation)

        if len(new_probs) > self.max_rl:
            new_probs = new_probs[: self.max_rl]
            new_alphas = new_alphas[: self.max_rl]
            new_betas = new_betas[: self.max_rl]
            total = new_probs.sum()
            if total > 0:
                new_probs /= total

        self.run_length_probs = new_probs
        self.alphas = new_alphas
        self.betas = new_betas

        return new_probs[0] > self.threshold, float(new_probs[0])

    def get_state_dict(self) -> dict:
        return {
            "run_length_probs": self.run_length_probs.tolist(),
            "alphas": self.alphas.tolist(),
            "betas": self.betas.tolist(),
            "hazard_rate": self.hazard,
            "max_run_length": self.max_rl,
            "changepoint_threshold": self.threshold,
        }

    @classmethod
    def from_state_dict(cls, state: dict) -> "BOCPD":
        obj = cls(
            hazard_rate=state.get("hazard_rate", 1 / 250),
            max_run_length=state.get("max_run_length", 500),
            changepoint_threshold=state.get("changepoint_threshold", 0.5),
        )
        obj.run_length_probs = np.array(state["run_length_probs"])
        obj.alphas = np.array(state["alphas"])
        obj.betas = np.array(state["betas"])
        return obj
