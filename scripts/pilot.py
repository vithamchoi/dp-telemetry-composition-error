"""Collect live LLM telemetry via Groq, then DP aggregate (no random synthetic chat)."""
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "scripts"))
from groq_client import call_groq, require_groq_key  # noqa: E402

OUT_DATA = ROOT / "data" / "processed" / "live_telemetry.jsonl"
OUT_CURVE = ROOT / "results" / "pilot" / "privacy_utility_curve.csv"

TOPICS = ["security", "finance", "health", "coding", "general"]
REFUSAL_MARKERS = ["i cannot", "i can't", "unable to", "sorry", "not able to"]


def classify_refusal(text: str) -> bool:
    t = text.lower()
    return any(m in t for m in REFUSAL_MARKERS)


def main():
    require_groq_key()
    try:
        from diffprivlib.mechanisms import Laplace
    except ImportError:
        raise SystemExit("diffprivlib is required for project 06; refusing non-DP fallback.")

    OUT_DATA.parent.mkdir(parents=True, exist_ok=True)
    OUT_CURVE.parent.mkdir(parents=True, exist_ok=True)
    if OUT_DATA.exists():
        OUT_DATA.unlink()

    records = []
    n = int(os.getenv("TELEMETRY_LLM_SAMPLES", "20"))
    for i in range(n):
        topic = TOPICS[i % len(TOPICS)]
        prompt = f"User question about {topic}: give a one-sentence helpful answer."
        print(f"[LLM telemetry {i+1}/{n}] topic={topic}", flush=True)
        text = call_groq(prompt, max_tokens=120)
        refused = classify_refusal(text)
        rec = {
            "id": i,
            "topic": topic,
            "refused": refused,
            "turn_count": 1,
            "provider": "groq",
        }
        records.append(rec)
        with open(OUT_DATA, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    true_rate = sum(1 for r in records if r["refused"]) / len(records)
    epsilons = [0.5, 1.0, 2.0, 4.0]
    rows = []
    for eps in epsilons:
        m = Laplace(epsilon=eps, sensitivity=1)
        noisy = sum(m.randomise(int(r["refused"])) for r in records) / len(records)
        rows.append((eps, true_rate, max(0.0, min(1.0, noisy))))

    with open(OUT_CURVE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["epsilon", "true_refusal_rate", "dp_refusal_rate", "provider"])
        for eps, tr, nr in rows:
            w.writerow([eps, f"{tr:.4f}", f"{nr:.4f}", "groq"])
    print(f"[ok] records={len(records)} true_refusal_rate={true_rate:.4f}")
    print(f"[ok] wrote {OUT_DATA} and {OUT_CURVE} (diffprivlib=True)")


if __name__ == "__main__":
    main()
