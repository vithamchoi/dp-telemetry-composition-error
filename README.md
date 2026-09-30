# DP telemetry, composition error and detection floor

Result files, experiment scripts and LaTeX sources for the paper

> V. T. Le, S. X. Ha, N. N. Phien and T. Q. Nguyen,
> "Noise Louder Than the Signal",
> submitted to IEEE Transactions on Information Forensics and Security, 2026.

## What is in here

```
results/     the measured result files. Every number, table and figure in the
             paper is computed from these and from nothing else.
scripts/     the experiment code that produced those files.
latex/       the generators that read results/ and emit the table bodies and
             figures, plus the paper source they are substituted into.
```

## What you can reproduce, and what you cannot

**From this repository alone** you can regenerate every table, figure and
inline number in the paper:

```bash
pip install -r requirements.txt
cd latex
python3 make_tables.py  ../results  tables
python3 make_figures.py ../results  figures
python3 build.py        ../results          # writes main.tex
python3 build_ieee.py                      # writes ieee/main_ieee.tex
```

`build.py` substitutes the generated values into `paper_template.tex`. No number
in the paper is typed by hand, so a mismatch between the paper and a fresh run
of these scripts is a bug and we would like to hear about it.

`build_ieee.py` then rewrites that manuscript into the IEEE two-column form that
was actually submitted: it drops the CRediT section, which IEEE has no field for,
lifts the funding statement into a page-one footnote, rebuilds the author block
in IEEE style, and widens only the tables that overflow a column.
`latex/ieee/main_ieee.tex` is checked in even though it is generated, because it
is the exact manuscript we submitted. Regenerating it must produce the same
bytes; that diff is the artifact's own self-check, and we ran it on all nine
papers before publishing.

Unlike the other artifacts in this series, this one is self-contained. The two files in `results/` are the only measured inputs, and everything else in the paper (the binomial bounds, the detection floor, the sample-size table, the two propositions, the inflation factor and the Monte-Carlo comparison) is computation over them with a fixed seed. `pip install -r requirements.txt` and the three commands above regenerate the entire paper with no API key, no GPU and no external dataset.

## Layout of `results/`

| File | Used for |
|---|---|
| `data/processed/live_telemetry.jsonl` | the live inference records: id, topic, refusal flag, turn count, provider. This is the measured input and the only measured input |
| `pilot/privacy_utility_curve.csv` | the privacy-utility curve as the pilot released it, one row per budget. It is the artefact under analysis, reproduced verbatim, not something we computed |

## Licence

Code in `scripts/` and `latex/` is MIT. The result files in `results/` are
CC BY 4.0. See `LICENSE`.
