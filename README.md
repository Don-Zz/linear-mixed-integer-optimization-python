# Linear and Mixed-Integer Optimization in Python

Linear and mixed-integer optimization in Python with PuLP, plus sensitivity analysis of missing data.

I built this project to explore a practical optimization question: how can I choose food quantities that meet a set of nutrition limits while minimizing cost or cholesterol?

The project starts with a linear program, adds binary food-selection decisions, and then examines how the answer changes when the input data have missing measurements. It shows both what an optimizer calculates and why a mathematically optimal result can still make an impractical menu.

This is a methods project developed from Georgia Tech ISYE 6501 Week 11. The source spreadsheets, course documents, and generated food-level results are not included in this repository. Obtain the inputs separately from the course materials. See [data instructions](data/README.md).

## What the code does

| Script | Decision and objective | What it calculates |
|---|---|---|
| `scripts/diet_cost.py` | Choose daily servings of 64 foods to minimize total cost. | Two food menus, daily cost, 11 nutrition totals, feasibility checks, and the dollar and percentage cost increase caused by selection rules. |
| `scripts/diet_cholesterol.py` | Choose food quantities to minimize cholesterol in a larger workbook. | Basic and modified menus under two missing-data approaches, 27 nutrition totals per model, distinct protein-option counts, and the effect of changing the available data. |

Both scripts use PuLP and the CBC solver. They read local inputs and save results locally; they do not download or upload data.

## Models and food-selection rules

The basic model uses continuous, nonnegative food quantities. It minimizes the sum of each food's quantity multiplied by its cost or cholesterol coefficient. Every nutrition total must stay between its supplied daily minimum and maximum.

The modified model also decides whether each food is selected, using a binary variable. Its rules are:

- A selected food must have at least 0.1 quantity units; an excluded food must have zero.
- Raw celery and frozen broccoli cannot both be selected. The large model groups raw celery and frozen-broccoli options into an at-most-one exclusion set.
- At least three eligible meat, poultry, fish, seafood, or egg food options must be selected.

Upper linking bounds come from the supplied nutrition limits rather than an arbitrary large number. In the cost model, each food's calorie contribution bounds its servings. The cholesterol model uses the tightest upper bound available across the bounded nutrients.

The classification is explicit. Poached and scrambled eggs count as separate preparation options. The large model groups repeated identical protein descriptions so duplicate rows do not inflate variety. Three options do not necessarily mean three animal species or three distinct protein ingredients. See [methodology and formulas](docs/methodology.md).

## Missing-data comparison

The large workbook contains 7,146 food rows. Only 287 have every bounded nutrient and cholesterol value observed. The script runs both the basic and modified model using:

1. **Complete rows:** retain those 287 foods and leave missing values unresolved.
2. **All rows with zero fill:** retain all 7,146 foods and assume missing coefficients equal zero for a sensitivity analysis.

The second approach fills 25,003 coefficients, including cholesterol for 244 rows. Zero filling is an assumption, not a verified measurement or a repair to the original file. Selected-food outputs flag which entries depend on filled coefficients. The code preserves the original spreadsheets.

## Verified example results

These numbers come from local runs using the supplied course inputs. Another optimal food combination can have the same objective.

| Cost model | Daily cost |
|---|---:|
| Basic nutrition limits | $4.3371 |
| With food-selection rules | $4.5125 |
| Increase | $0.1754, or 4.04% |

| Cholesterol model | Food rows | Basic objective | With food-selection rules |
|---|---:|---:|---:|
| Complete rows | 287 | 0.0000 | 3.1000 |
| All rows, assuming blanks equal zero | 7,146 | 0.0000 | 0.0000 |

The large workbook supplies no cholesterol-unit label or serving-size column, so the cholesterol figures are reported in workbook coefficient units and quantities as reference-quantity multipliers. They are not dollar amounts or physical serving counts. Both Energy columns and their supplied limits are retained separately.

The cost increase measures the combined effect of the added rules. It does not isolate the cost of each rule. In the large-model comparison, expanding the choice set and filling missing values happen together, so their effects are not separately identified.

## Run locally

The verified environment used Python 3.14.8. The requirements file pins the tested direct dependencies; it is not a complete lockfile for all transitive dependencies.

From the project root on macOS or Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Obtain `diet.xls` and `diet_large.xls` from the course materials and place them in the ignored `data/raw/` folder, creating that folder locally if needed. Then run:

```sh
python scripts/diet_cost.py
python scripts/diet_cholesterol.py
```

If the inputs are already stored elsewhere, keep them outside this project:

```sh
python scripts/diet_cost.py --data-dir "/path/to/private/data"
python scripts/diet_cholesterol.py --data-dir "/path/to/private/data"
```

Both scripts support `--help` and `--output-dir`. Their input paths are based on the project location or the supplied folder, so they also work when called from another working directory.

## Calculations and local outputs

The cost script writes results to `outputs/cost/`. The cholesterol script writes complete-row results to `outputs/cholesterol/` and all-row sensitivity results to `outputs/cholesterol/all_rows_zero_fill/`.

Generated outputs include selected food quantities, cost or cholesterol contributions, each nutrition minimum/total/maximum, and solution checks. The large model also saves classifications, missing-input flags, all modified-model decisions, software versions, input/script hashes, and `comparison.json` for the two approaches. These outputs are ignored by Git because they can contain source food records.

The scripts stop if a solver does not return an optimal solution. CBC is asked for zero relative and absolute objective gaps; numerical feasibility tolerances still apply. The large models have a 120-second solver limit. A feasible starting menu helps the all-row binary model solve faster without changing its objective or constraints.

## Project structure

```text
README.md                  Project explanation, calculations, results, and usage
requirements.txt           Tested Python dependencies
.gitignore                 Excludes input data, generated data, and local files
scripts/
  diet_cost.py             Minimum-cost LP and food-selection MILP
  diet_cholesterol.py      Cholesterol models and missing-data comparison
data/
  README.md                How to supply the inputs without committing them
docs/
  methodology.md           Variables, formulas, assumptions, and interpretation
  validation.md            Local checks and their limits
```

## What I learned and what I would change

A solver can find the cheapest mathematically feasible menu while choosing unrealistic quantities. The models do not encode taste, preparation effort, meal balance, or practical portion caps. The supplied prices and nutrition limits are fixed inputs, not current grocery prices or personalized dietary advice.

Missing values also affect which actions an optimizer can choose. Complete-case analysis discards many options. Zero filling can understate nutrient and cholesterol contributions. Passing the assumed model does not establish that the actual diet satisfies all limits.

The next steps would be to resolve missing measurements, confirm reference quantities and units, define variety more strictly, and add food-specific portion limits. Those improvements are not presented as already implemented. See [validation details](docs/validation.md).
