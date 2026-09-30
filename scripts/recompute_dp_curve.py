"""Recompute privacy-utility curve from extracted live telemetry dataset (N=1000)."""
import csv
import json
from pathlib import Path
from diffprivlib.mechanisms import Laplace
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
IN_DATA = ROOT / "data" / "processed" / "live_telemetry.jsonl"
OUT_CURVE = ROOT / "results" / "pilot" / "privacy_utility_curve.csv"

def main():
    if not IN_DATA.exists():
        raise SystemExit(f"Input file not found: {IN_DATA}")

    records = []
    with open(IN_DATA, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    n_samples = len(records)
    print(f"[Loaded] {n_samples} real telemetry records from {IN_DATA}")

    true_refusals = sum(1 for r in records if r.get("refused"))
    true_rate = true_refusals / n_samples
    print(f"[Ground Truth] true_refusals={true_refusals}, true_refusal_rate={true_rate:.4f}")

    # Compute empirical Laplace mechanism distortion across epsilons
    epsilons = [0.5, 1.0, 2.0, 4.0]
    trials_per_eps = 50  # Monte Carlo repetition to get stable empirical expectation & std
    np.random.seed(42)

    rows = []
    for eps in epsilons:
        m = Laplace(epsilon=eps, sensitivity=1)
        trial_noisy_rates = []
        for _ in range(trials_per_eps):
            noisy_sum = sum(m.randomise(int(r.get("refused", False))) for r in records)
            noisy_rate = max(0.0, min(1.0, noisy_sum / n_samples))
            trial_noisy_rates.append(noisy_rate)
        
        mean_noisy_rate = float(np.mean(trial_noisy_rates))
        std_noisy_rate = float(np.std(trial_noisy_rates))
        rows.append((eps, true_rate, mean_noisy_rate, std_noisy_rate))
        print(f"  eps={eps:.1f} -> mean_dp_rate={mean_noisy_rate:.4f}, std={std_noisy_rate:.4f}")

    OUT_CURVE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CURVE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["epsilon", "true_refusal_rate", "dp_refusal_rate", "dp_std", "n_samples", "provider"])
        for eps, tr, mr, sr in rows:
            w.writerow([eps, f"{tr:.4f}", f"{mr:.4f}", f"{sr:.4f}", n_samples, "groq"])

    print(f"[Success] Successfully saved updated curve to {OUT_CURVE}")

if __name__ == "__main__":
    main()
