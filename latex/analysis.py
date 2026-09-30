#!/usr/bin/env python3
"""Analysis layer for the DP telemetry paper.

Two clearly separated layers, and the paper labels them as such:

  MEASURED   data/processed/live_telemetry.jsonl -- 1,000 live Groq inference
             records collected by sandbox/pilot.py, each carrying the topic and
             the keyword-classifier refusal verdict.
             results/pilot/privacy_utility_curve.csv -- the single differentially
             private release that the pilot actually emitted from those records.

  DERIVED    Everything else here is a Monte-Carlo study of standard DP
             mechanisms applied to the measured count. It is arithmetic on the
             measured value, not a second experiment, and every table and figure
             that uses it says so.

Imported by make_tables.py and make_figures.py so both read one code path.
"""
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path

import numpy as np

SEED = 20260904          # fixed so every number in the paper is reproducible
TRIALS = 20000           # Monte-Carlo repetitions per (mechanism, epsilon)
EPSILONS = [0.5, 1.0, 2.0, 4.0, 8.0]
ALARM_TAU = 0.05         # the alert threshold used in the operational analysis


def jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class Data:
    def __init__(self, res: Path):
        self.res = Path(res)
        self.records = jsonl(self.res / "data" / "processed" / "live_telemetry.jsonl")
        with open(self.res / "pilot" / "privacy_utility_curve.csv",
                  newline="", encoding="utf-8") as f:
            self.pilot_curve = list(csv.DictReader(f))
        self.rng = np.random.default_rng(SEED)

    # ------------------------------------------------------------- measured
    @property
    def n(self):
        return len(self.records)

    @property
    def topics(self):
        return Counter(r["topic"] for r in self.records)

    @property
    def refused(self):
        return sum(1 for r in self.records if r["refused"])

    @property
    def true_rate(self):
        return self.refused / self.n

    @property
    def provider(self):
        return self.records[0].get("provider", "unknown")

    def turn_counts(self):
        return Counter(r.get("turn_count") for r in self.records)

    @staticmethod
    def wilson_upper(k, n, z=1.96):
        """Upper Wilson bound: the honest way to report a zero count."""
        p = k / n
        d = 1 + z * z / n
        c = p + z * z / (2 * n)
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
        return min(1.0, (c + h) / d)

    def rule_of_three(self):
        """Classical 95% upper bound on a probability after k=0 in n trials."""
        return 3.0 / self.n

    # ------------------------------------------------------------- derived
    def laplace_draws(self, eps, trials=TRIALS):
        """Central DP: Laplace(1/eps) added to the refusal COUNT, then divided
        by n and clipped to [0,1] -- exactly what the pilot script does."""
        rng = np.random.default_rng(SEED + int(eps * 1000))
        noise = rng.laplace(0.0, 1.0 / eps, trials)
        return np.clip((self.refused + noise) / self.n, 0.0, 1.0)

    def perrecord_draws(self, eps, trials=TRIALS):
        """What the pilot release actually did: add an independent
        Laplace(1/eps) draw to EACH record's 0/1 indicator, then average.

        This is not the central-DP release it is labelled as. Summing n
        independent draws inflates the noise standard deviation on the rate by
        a factor of sqrt(n) relative to perturbing the aggregate count once.
        """
        rng = np.random.default_rng(SEED + 31337 + int(eps * 1000))
        noise = rng.laplace(0.0, 1.0 / eps, (trials, self.n)).sum(axis=1)
        return np.clip((self.refused + noise) / self.n, 0.0, 1.0)

    def theory_sd_aggregate(self, eps):
        """SD of the correct central release: Laplace(1/eps)/n."""
        return math.sqrt(2.0) / (eps * self.n)

    def theory_sd_perrecord(self, eps):
        """SD of the per-record release: sqrt(n)*sqrt(2)/(eps*n)."""
        return math.sqrt(2.0 * self.n) / (eps * self.n)

    def inflation_factor(self):
        return math.sqrt(self.n)

    def rr_draws(self, eps, trials=TRIALS):
        """Local DP: binary randomised response on each record, then debiased."""
        rng = np.random.default_rng(SEED + 7919 + int(eps * 1000))
        p = math.exp(eps) / (math.exp(eps) + 1.0)
        truth = np.zeros(self.n, dtype=bool)
        truth[: self.refused] = True
        keep = rng.random((trials, self.n)) < p
        reported = np.where(keep, truth[None, :], ~truth[None, :])
        raw = reported.mean(axis=1)
        out = (raw + p - 1.0) / (2.0 * p - 1.0)
        return np.clip(out, 0.0, 1.0)

    def theory_sd_rr(self, eps):
        """SD of the debiased randomised-response estimator (local DP).

        With p = e^eps/(e^eps+1) and a true rate r, the reported mean has
        variance q(1-q)/n where q = r*p + (1-r)*(1-p); debiasing divides by
        (2p-1). Evaluated at the MEASURED true rate.
        """
        p = math.exp(eps) / (math.exp(eps) + 1.0)
        r = self.true_rate
        q = r * p + (1.0 - r) * (1.0 - p)
        return math.sqrt(q * (1.0 - q) / self.n) / (2.0 * p - 1.0)

    def n_equivalent_perrecord(self):
        """Records the per-record release needs to match the SD the correct
        aggregate release already achieves at the measured n. Solving
        sqrt(2)/(eps*sqrt(n')) = sqrt(2)/(eps*n) gives n' = n^2, independent
        of epsilon."""
        return self.n ** 2

    def rr_support_spacing(self, eps):
        """The debiased RR estimator lives on a lattice: consecutive reported
        counts map to released rates 1/(n(2p-1)) apart. Histograms of it must
        use bin widths that are integer multiples of this, or they alias."""
        p = math.exp(eps) / (math.exp(eps) + 1.0)
        return 1.0 / (self.n * (2.0 * p - 1.0))

    def summary(self, draws):
        return dict(
            mean=float(np.mean(draws)),
            sd=float(np.std(draws, ddof=1)),
            p50=float(np.quantile(draws, 0.50)),
            p95=float(np.quantile(draws, 0.95)),
            p99=float(np.quantile(draws, 0.99)),
            max=float(np.max(draws)),
            alarm=float(np.mean(draws >= ALARM_TAU)),
        )

    MECHS = {}

    def draws(self, mech, eps):
        return {"laplace": self.laplace_draws,
                "perrecord": self.perrecord_draws,
                "rr": self.rr_draws}[mech](eps)

    def mechanism_table(self, mech="laplace"):
        return {eps: self.summary(self.draws(mech, eps)) for eps in EPSILONS}

    def threshold_for_alarm(self, eps, alpha=0.01, mech="laplace"):
        """Smallest release value tau such that P(release >= tau) <= alpha
        when the true rate is the measured one."""
        return float(np.quantile(self.draws(mech, eps), 1.0 - alpha))

    def n_required(self, eps, target_sd):
        """Sample size at which Laplace noise SD on the RATE falls below
        target_sd. SD of Laplace(1/eps)/n is sqrt(2)/(eps*n)."""
        return math.ceil(math.sqrt(2.0) / (eps * target_sd))

    # ---------------------------------------------------- measured release
    def pilot_rows(self):
        out = []
        for r in self.pilot_curve:
            out.append(dict(
                eps=float(r["epsilon"]),
                true=float(r["true_refusal_rate"]),
                dp=float(r["dp_refusal_rate"]),
                provider=r["provider"],
            ))
        return out

    def pilot_max_error(self):
        return max(abs(r["dp"] - r["true"]) for r in self.pilot_rows())

    # ---------------------------------------------------------------- v2 fixes
    def analytic_alarm_aggregate(self, eps, tau=ALARM_TAU):
        """P(release >= tau) for the CORRECT central mechanism, in closed form.

        With the measured count 0, the release is Lap(0, 1/(eps*n)) clipped to
        [0,1], so P(X >= tau) = 0.5*exp(-tau*eps*n). At eps=0.5, n=1000, tau=0.05
        this is about 7e-12: no Monte Carlo with 20,000 draws can measure it, and
        reporting the simulated 0.00 as if it were the value is wrong. We report
        the closed form and label the simulated column as a bound.
        """
        return 0.5 * math.exp(-tau * eps * self.n)

    def analytic_alarm_perrecord(self, eps, tau=ALARM_TAU):
        """Same quantity for the per-record mechanism.

        The sum of n iid Laplace(1/eps) has no elementary CDF, so we give the
        Gaussian approximation implied by the CLT at n = 1000, which is what the
        simulated figure should be compared against.
        """
        sd = self.theory_sd_perrecord(eps)
        z = (tau - self.true_rate) / sd
        return 0.5 * math.erfc(z / math.sqrt(2.0))

    @staticmethod
    def mc_se(p, trials=TRIALS):
        """Monte-Carlo standard error of a simulated proportion."""
        return math.sqrt(max(p * (1.0 - p), 0.0) / trials)

    @staticmethod
    def mc_ci(p, trials=TRIALS, z=1.96):
        se = Data.mc_se(p, trials)
        return max(0.0, p - z * se), min(1.0, p + z * se)

    def mc_rule_of_three(self, trials=TRIALS):
        """Upper bound when a simulated proportion comes back exactly 0."""
        return 3.0 / trials

    def empirical_sd_ratio(self, eps):
        """Ratio of EMPIRICAL (clipped) SDs, per-record over aggregate.

        Distinct from the analytic inflation factor sqrt(n) = 31.62: clipping at
        zero removes the lower half of each distribution, and it does not remove
        the same fraction from both, so the empirical ratio is not sqrt(n).
        """
        a = float(np.std(self.laplace_draws(eps), ddof=1))
        b = float(np.std(self.perrecord_draws(eps), ddof=1))
        return b / a

    def zero_gate_factor(self, eps, q=0.999):
        """Check 2: by what factor does the pilot release breach the gate?

        The gate is the q-th percentile of |Lap(1/(eps*n))|, which for the
        two-sided Laplace is (1/(eps*n))*ln(1/(1-q)). The released rate is
        divided by that. The old text used WorstErrSD/3, which is not this
        quantity and overstates the factor.
        """
        b = 1.0 / (eps * self.n)
        gate = b * math.log(1.0 / (1.0 - q))
        released = self.pilot_release_at(eps)
        return released / gate, gate

    def pilot_release_at(self, eps):
        """The released rate at this epsilon, from the measured curve."""
        for row in self.pilot_rows():
            if abs(row["eps"] - eps) < 1e-9:
                return row["dp"]
        raise KeyError(eps)

