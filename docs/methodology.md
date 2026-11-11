# Methodology

## Basic linear model

Let `x[i]` be the nonnegative quantity of food i, `c[i]` its objective coefficient, `a[j,i]` its contribution to nutrient j per quantity unit, and `L[j]` and `U[j]` the supplied daily bounds.

```text
minimize       sum(c[i] * x[i])
subject to     L[j] <= sum(a[j,i] * x[i]) <= U[j]   for every bounded nutrient j
               x[i] >= 0                        for every food i
```

Cost and nutrition scale linearly with quantity. In the small workbook, quantities are servings and `c[i]` is price per serving. In the large workbook, quantities multiply the source coefficients and `c[i]` is cholesterol. The large source does not specify a serving size or cholesterol-unit label.

## Selection rules

For each food, add binary `z[i]` equal to one when selected:

```text
0.1 * z[i] <= x[i] <= M[i] * z[i]
```

The small model uses `M[i] = maximum daily calories / calories per serving[i]`. All 64 foods have positive calories and nonnegative nutrition values, making that a valid upper bound.

The large model takes the minimum of `U[j] / a[j,i]` over positive bounded nutrient coefficients. Nonnegative contributions make each ratio a valid upper bound. The code checks that a finite bound exists.

The small exclusion rule is `z[raw celery] + z[frozen broccoli] <= 1`. The large model uses an at-most-one exclusion set containing raw celery and the frozen-broccoli descriptions. Neither survives the complete-case filter; they are present in the all-row sensitivity run.

At least three eligible food options must be chosen. The small eligible set consists of Roasted Chicken, Poached Eggs, Scrambled Eggs, Bologna Turkey, Beef Frankfurter, Extra-Lean Sliced Ham, Pork Kielbasa, Pork, Sardines in Oil, and White Tuna in Water. The code uses the exact spreadsheet names. Peanut butter, dairy, tofu, soups, and mixed dishes are excluded.

For the large workbook, explicit name prefixes identify standalone meat, poultry, eggs, seafood, and processed meats. Identical protein descriptions are grouped. For a repeated description, a group variable is one if any member row is selected; the variety constraint counts groups rather than repeated rows. Different preparation descriptions remain separate options. This interpretation does not ensure three distinct ingredients or animal sources.

## Model sizes

- Small basic model: 64 continuous variables and 22 nutrition constraints.
- Small modified model: 64 continuous variables, 64 binary variables, and 152 explicit constraints.
- Large complete-case basic model: 287 continuous variables and 54 nutrition constraints.
- Large complete-case modified model: 574 variables and 630 constraints.
- All-row basic model: 7,146 continuous variables and 54 nutrition constraints.
- All-row modified model: 14,503 variables, including repeated-description group variables, and 15,527 constraints.

Variable bounds are not included in the explicit constraint counts.

## Missing-data assumptions

Complete-case analysis retains a food only if cholesterol and all 27 bounded nutrition coefficients are observed. Missing values in the unused fatty-acid columns do not exclude a food. This retains 287 rows and excludes 6,859.

The all-row sensitivity analysis fills missing required coefficients with zero, retaining 7,146 rows. It fills 25,003 values, including 244 missing cholesterol values. This is an explicit scenario assumption, not measured data, a validated imputation model, or a claim that unknown values are absent. The original workbook is never modified.

Both Energy columns are constrained separately using their supplied bounds. The code does not silently convert them or correct source limits. Expanding the choice set and filling missing values happen together, so the comparison does not isolate these effects.

## Calculated measures

```text
Daily cost                 = sum(price per serving[i] * servings[i])
Daily nutrition total[j]   = sum(a[j,i] * x[i])
Daily cholesterol          = sum(cholesterol[i] * x[i])
Daily cost increase        = modified cost - basic cost
Percentage cost increase   = 100 * daily cost increase / basic cost
Protein variety            = count of distinct selected eligible descriptions
```

No statistical sampling or random-data experiment is performed. Solver choices among tied optima can change menus while preserving the objective. The large model retains raw objectives and treats tiny negative round-off between -0.000001 and zero as zero for reporting.

## Solving and interpretation

CBC solves the LPs and mixed-integer models through PuLP's `COIN_CMD`. Relative and absolute gap targets are zero; feasibility tolerances still apply. The large script imposes a 120-second solve limit and refuses to report a non-optimal run as final.

For the all-row modified model, a small continuous subproblem constructs a candidate menu from the basic solution and three distinct zero-cholesterol protein descriptions. If feasible, it supplies initial quantities, selections, and group values to CBC. This is a warm start, not a change to the objective or selection rules.

The objective can be zero while portions are unrealistic or assumptions are weak. Practical limits on portions, preparation, availability, and ingredient variety would require additional data and constraints.
