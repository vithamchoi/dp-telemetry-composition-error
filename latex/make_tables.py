#!/usr/bin/env python3
"""Generate LaTeX table bodies and inline macros for the DP telemetry paper."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis import Data, EPSILONS, ALARM_TAU, TRIALS, SEED  # noqa: E402

RES = Path(sys.argv[1] if len(sys.argv) > 1 else "../results")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "tables")
OUT.mkdir(parents=True, exist_ok=True)
D = Data(RES)


def write(name, body):
    (OUT / name).write_text(body.rstrip() + "\n", encoding="utf-8")
    print(f"wrote {OUT / name}")


def pc(x, d=2):
    return f"{100 * x:.{d}f}"


def sci(x, d=2):
    if x == 0:
        return "$0$"
    import math
    e = math.floor(math.log10(abs(x)))
    m = x / 10 ** e
    return f"${m:.{d}f}\\times 10^{{{e}}}$"


MECHS = [
    ("laplace", r"Aggregate Laplace (correct central DP)"),
    ("perrecord", r"Per-record Laplace (as released)"),
    ("rr", r"Randomised response (local DP)"),
]

# --------------------------------------------------- Table: telemetry composition
rows = []
for topic, n in sorted(D.topics.items()):
    refused = sum(1 for r in D.records if r["topic"] == topic and r["refused"])
    rows.append(" & ".join([
        topic.capitalize(), str(n), str(refused), pc(refused / n),
        pc(D.wilson_upper(refused, n)),
    ]) + r" \\")
rows.append(r"\addlinespace")
rows.append(" & ".join([
    r"\textbf{All topics}", r"\textbf{" + str(D.n) + "}",
    r"\textbf{" + str(D.refused) + "}", r"\textbf{" + pc(D.true_rate) + "}",
    r"\textbf{" + pc(D.wilson_upper(D.refused, D.n)) + "}",
]) + r" \\")
write("tab_telemetry.tex", "\n".join(rows))

# --------------------------------------------------- Table: the released curve
rows = []
for r in D.pilot_rows():
    err = abs(r["dp"] - r["true"])
    bold = (lambda t: r"\textbf{" + t + "}") if err == D.pilot_max_error() else (lambda t: t)
    rows.append(" & ".join([
        f"${r['eps']:.1f}$", pc(r["true"]), bold(pc(r["dp"])),
        bold(f"{100 * err:.2f}"),
        f"{err / D.theory_sd_aggregate(r['eps']):.0f}",
    ]) + r" \\")
write("tab_released.tex", "\n".join(rows))

# --------------------------------------------------- Table: mechanism comparison

def alarm_cell(mech, eps, p):
    """Mot ty le mo phong bang 0 khong phai so do duoc.

    Voi co che dung ta co cong thuc dong, nen in gia tri do. Voi cac co che
    khac, khi mo phong ra 0 thi in can tren rule-of-three chu khong in 0.00.
    Cac o khac in kem sai so chuan Monte Carlo.
    """
    if p <= 0.0:
        if mech == "laplace":
            return sci(D.analytic_alarm_aggregate(eps)) + r"$^{\dagger}$"
        return rf"$<{100 * D.mc_rule_of_three():.3f}$"
    return f"{100 * p:.2f} $\\pm$ {100 * D.mc_se(p):.2f}"


rows = []
for mi, (mech, label) in enumerate(MECHS):
    if mi:
        rows.append(r"\addlinespace")
    tab = D.mechanism_table(mech)
    for i, eps in enumerate(EPSILONS):
        s = tab[eps]
        rows.append(" & ".join([
            label if i == 0 else "",
            f"${eps:g}$",
            f"{100 * s['sd']:.3f}",
            f"{100 * s['p95']:.3f}",
            f"{100 * s['p99']:.3f}",
            f"{100 * s['max']:.2f}",
            alarm_cell(mech, eps, s["alarm"]),
        ]) + r" \\")
write("tab_mechanisms.tex", "\n".join(rows))

# --------------------------------------------------- Table: theory
rows = []
for eps in EPSILONS:
    a = D.theory_sd_aggregate(eps)
    p = D.theory_sd_perrecord(eps)
    rr = D.theory_sd_rr(eps)
    rows.append(" & ".join([
        f"${eps:g}$", sci(a), sci(p), sci(rr), f"{p / a:.2f}",
        f"{D.n_required(eps, 0.005)}", f"{D.n_required(eps, 0.001)}",
    ]) + r" \\")
write("tab_theory.tex", "\n".join(rows))

# --------------------------------------------------- Table: alarm thresholds
rows = []
for eps in EPSILONS:
    cells = [f"${eps:g}$"]
    for mech, _ in MECHS:
        cells.append(f"{100 * D.threshold_for_alarm(eps, 0.01, mech):.3f}")
    rows.append(" & ".join(cells) + r" \\")
write("tab_thresholds.tex", "\n".join(rows))

# --------------------------------------------------- macros
lap = D.mechanism_table("laplace")
per = D.mechanism_table("perrecord")
rr = D.mechanism_table("rr")
worst = max(D.pilot_rows(), key=lambda r: abs(r["dp"] - r["true"]))

macros = [
    (r"\Nrec", f"{D.n:,}".replace(",", "{,}")),
    (r"\Ntopics", str(len(D.topics))),
    (r"\Nper", str(next(iter(D.topics.values())))),
    (r"\Nrefused", str(D.refused)),
    (r"\Truerate", pc(D.true_rate)),
    (r"\WilsonUp", pc(D.wilson_upper(D.refused, D.n))),
    (r"\RuleThree", pc(D.rule_of_three())),
    (r"\Provider", D.provider),
    (r"\Trials", f"{TRIALS:,}".replace(",", "{,}")),
    (r"\Seed", str(SEED)),
    (r"\AlarmTau", pc(ALARM_TAU, 0)),
    (r"\WorstEps", f"{worst['eps']:g}"),
    (r"\WorstRelease", pc(worst["dp"])),
    (r"\WorstErrSD", f"{abs(worst['dp'] - worst['true']) / D.theory_sd_aggregate(worst['eps']):.0f}"),
    (r"\Inflation", f"{D.inflation_factor():.1f}"),
    (r"\LapSDhalf", f"{100 * lap[0.5]['sd']:.3f}"),
    (r"\LapMaxhalf", f"{100 * lap[0.5]['max']:.2f}"),
    (r"\LapAlarmhalf", f"{100 * lap[0.5]['alarm']:.2f}"),
    (r"\PerSDhalf", f"{100 * per[0.5]['sd']:.2f}"),
    (r"\PerPninefive", f"{100 * per[0.5]['p95']:.1f}"),
    (r"\PerMaxhalf", f"{100 * per[0.5]['max']:.1f}"),
    (r"\PerAlarmhalf", f"{100 * per[0.5]['alarm']:.1f}"),
    (r"\PerAlarmone", f"{100 * per[1.0]['alarm']:.1f}"),
    (r"\PerAlarmtwo", f"{100 * per[2.0]['alarm']:.1f}"),
    (r"\RRAlarmhalf", f"{100 * rr[0.5]['alarm']:.1f}"),
    (r"\RRSDhalf", f"{100 * rr[0.5]['sd']:.2f}"),
    (r"\SDratio", f"{per[0.5]['sd'] / lap[0.5]['sd']:.2f}"),
    # --- v2: cac con so da sua sau phan bien
    (r"\GateFactor", f"{D.zero_gate_factor(0.5)[0]:.1f}"),
    (r"\GatePc", f"{100 * D.zero_gate_factor(0.5)[1]:.2f}"),
    (r"\LapAlarmExact", sci(D.analytic_alarm_aggregate(0.5))),
    (r"\LapAlarmBound", f"{100 * D.mc_rule_of_three():.3f}"),
    (r"\PerAlarmCLT", f"{100 * D.analytic_alarm_perrecord(0.5):.1f}"),
    (r"\PerAlarmSE", f"{100 * D.mc_se(per[0.5]['alarm']):.2f}"),
    (r"\PerAlarmCIlo", f"{100 * D.mc_ci(per[0.5]['alarm'])[0]:.1f}"),
    (r"\PerAlarmCIhi", f"{100 * D.mc_ci(per[0.5]['alarm'])[1]:.1f}"),
    (r"\RRAlarmSE", f"{100 * D.mc_se(rr[0.5]['alarm']):.2f}"),
    (r"\SqrtN", f"{D.inflation_factor():.2f}"),
    (r"\LapSDtheoryhalf", f"{100 * D.theory_sd_aggregate(0.5):.3f}"),
    (r"\PerSDtheoryhalf", f"{100 * D.theory_sd_perrecord(0.5):.2f}"),
    (r"\RRSDtheoryhalf", f"{100 * D.theory_sd_rr(0.5):.2f}"),
    (r"\Nequiv", f"{D.n_equivalent_perrecord():,}".replace(",", "{,}")),
    (r"\Nfive", str(D.n_required(1.0, 0.005))),
    (r"\Nonetenth", str(D.n_required(1.0, 0.001))),
]
write("macros.tex", "\n".join(rf"\newcommand{{{n}}}{{{v}}}" for n, v in macros))
print("\nAll tables generated from:", RES.resolve())


# ===========================================================================
# Phan them: do phan giai cua phep do, va gia phai tra khi chia thanh 5 tang.
# Doc tu data/processed/live_telemetry.jsonl. 0 refusal tren 1.000 ban ghi,
# 200 ban ghi moi chu de. Moi so duoi day la mot ham thuan cua file do cong
# voi so hoc nhi thuc; khong mo phong.
# ===========================================================================
import collections as _c3
import json as _j3
import math as _m3

_TEL = RES / "data" / "processed" / "live_telemetry.jsonl"
if _TEL.exists():
    _recs = [_j3.loads(_l) for _l in _TEL.read_text(encoding="utf-8").splitlines() if _l.strip()]
    _ntel = len(_recs)
    _bytopic = _c3.Counter(_r["topic"] for _r in _recs)
    _refused = _c3.Counter(_r["topic"] for _r in _recs if _r.get("refused"))
    _turns = _c3.Counter(_r.get("turn_count") for _r in _recs)

    def _cp_up(n, alpha):
        """Bien tren Clopper-Pearson mot phia khi so su kien la 0."""
        return 1.0 - alpha ** (1.0 / n)

    def _wilson_up(k, n, z=1.96):
        p = k / n
        d = 1 + z * z / n
        c = p + z * z / (2 * n)
        h = z * _m3.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
        return (c + h) / d

    def _detectable(n, power):
        """Ty le nho nhat de thay it nhat mot su kien voi xac suat `power`."""
        return 1.0 - (1.0 - power) ** (1.0 / n)

    _nper = min(_bytopic.values())

    # --- bang: bien tren theo tung tang
    _rows_st = []
    for _tp in sorted(_bytopic):
        _nn = _bytopic[_tp]
        _kk = _refused.get(_tp, 0)
        _rows_st.append(r"%s & %d & %d & %s & %s & %s \\"
                        % (_tp.capitalize(), _nn, _kk,
                           pc(_wilson_up(_kk, _nn), 2),
                           pc(_cp_up(_nn, 0.05), 2),
                           pc(3.0 / _nn, 2)))
    _rows_st.append(r"\midrule")
    _rows_st.append(r"Pooled & %d & %d & %s & %s & %s \\"
                    % (_ntel, sum(_refused.values()),
                       pc(_wilson_up(0, _ntel), 2),
                       pc(_cp_up(_ntel, 0.05), 2),
                       pc(3.0 / _ntel, 2)))
    write("tab_strata_bounds.tex", "\n".join(_rows_st))

    # --- bang: do phan giai
    _rows_res = []
    for _pw in (0.80, 0.95, 0.99):
        _rows_res.append(r"%.0f\%% & %s & %s \\"
                         % (100 * _pw,
                            pc(_detectable(_ntel, _pw), 3),
                            pc(_detectable(_nper, _pw), 3)))
    write("tab_resolution.tex", "\n".join(_rows_res))

    # --- bang: co mau can cho mot bien tren cho truoc
    _rows_need = []
    for _tgt in (0.02, 0.01, 0.005, 0.002, 0.001):
        _need = _m3.ceil(_m3.log(0.05) / _m3.log(1 - _tgt))
        _rows_need.append(r"%s & %s \\"
                          % (pc(_tgt, 2), f"{_need:,}".replace(",", "{,}")))
    write("tab_needed.tex", "\n".join(_rows_need))

    _sid = 1 - (1 - 0.05) ** (1.0 / len(_bytopic))
    _m4 = [
        (r"\TNtel", f"{_ntel:,}".replace(",", "{,}")),
        (r"\TNper", str(_nper)),
        (r"\TNstrata", str(len(_bytopic))),
        (r"\TCpPooled", pc(_cp_up(_ntel, 0.05), 4)),
        (r"\TCpPerStratum", pc(_cp_up(_nper, 0.05), 4)),
        (r"\TCpRatio", "%.1f" % (_cp_up(_nper, 0.05) / _cp_up(_ntel, 0.05))),
        (r"\TBonf", pc(_cp_up(_nper, 0.05 / len(_bytopic)), 4)),
        (r"\TSidak", pc(_cp_up(_nper, _sid), 4)),
        (r"\TDetectPooled", pc(_detectable(_ntel, 0.80), 4)),
        (r"\TDetectStratum", pc(_detectable(_nper, 0.80), 4)),
        (r"\TNeedTenth", f"{_m3.ceil(_m3.log(0.05) / _m3.log(1 - 0.001)):,}".replace(",", "{,}")),
        (r"\TTurnsOne", str(_turns.get(1, 0))),
        (r"\TTurnKinds", str(len(_turns))),
        (r"\TRelRatio", "%.1f" % (0.1597 / _cp_up(_ntel, 0.05))),
    ]
    with open(OUT / "macros.tex", "a", encoding="utf-8") as _f:
        _f.write("\n%% --- do phan giai va cai gia cua phan tang ---\n")
        for _n, _v in _m4:
            _f.write(rf"\newcommand{{{_n}}}{{{_v}}}" + "\n")
    print(f"wrote {len(_m4)} macro do phan giai + 3 bang")


# ===========================================================================
# Phan them 2: ban cong bo cach su that bao nhieu do lech chuan, tinh RIENG
# cho tung co che. Day la phep kiem ma nguoi doc co the tu chay chi voi 4 dong
# cua privacy_utility_curve.csv.
# ===========================================================================
_rel_half = None
import csv as _csv3
with open(RES / "pilot" / "privacy_utility_curve.csv", newline="", encoding="utf-8") as _f:
    for _r in _csv3.DictReader(_f):
        if abs(float(_r["epsilon"]) - 0.5) < 1e-9:
            _rel_half = float(_r["dp_refusal_rate"])
assert _rel_half is not None

_sd_agg = D.theory_sd_aggregate(0.5)
_sd_per = D.theory_sd_perrecord(0.5)
_m5 = [
    (r"\ZRelHalf", pc(_rel_half, 2)),
    (r"\ZSdAgg", pc(_sd_agg, 3)),
    (r"\ZSdPer", pc(_sd_per, 2)),
    (r"\ZSigmaAgg", "%.0f" % (_rel_half / _sd_agg)),
    (r"\ZSigmaPer", "%.1f" % (_rel_half / _sd_per)),
]
with open(OUT / "macros.tex", "a", encoding="utf-8") as _f:
    _f.write("\n%% --- ban cong bo cach su that bao nhieu sigma, theo tung co che ---\n")
    for _n, _v in _m5:
        _f.write(rf"\newcommand{{{_n}}}{{{_v}}}" + "\n")
print(f"wrote {len(_m5)} macro sigma")
