# Life Protection Model

**Business question.** How should an Irish life insurer price a term-assurance book, monitor emerging mortality and lapse experience, and translate assumption changes into profitability, IFRS 17 earnings and Solvency II capital?

> Work in progress. This README will only describe what is implemented and tested.

Synthetic book of 50,000 level term and mortgage protection policies issued on 1 Jan 2023; illustrative assumptions. Mortality base tables (CMI 00 series) and discount curves (EIOPA) are real; policies and experience are simulated.

## Setup

```bash
uv sync
uv run pytest
```

Raw data must be downloaded manually — see [data/raw/README.md](data/raw/README.md).

## Specification

The full build specification is in [SPEC.md](SPEC.md).
