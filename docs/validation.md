# Validation

## Local verification

The source analyses were verified locally with Python 3.14.8, PuLP 4.2.0, CBC supplied through cbcbox 2.929, pandas 3.1.1, numpy 2.5.4, and xlrd 2.0.2. The repository copies keep the same optimization logic, add portable input/output folder options, and keep generated files outside version control.

Local verification covers the two cost models and four cholesterol models. It checks optimal solver statuses and independently recalculates objective values and nutrition totals from source coefficients and solved quantities. Selection checks cover binary values, both quantity links, the celery/broccoli rule, and at least three distinct eligible descriptions. The all-row audit checks all 7,146 modified-model decisions, not only the displayed food menu.

The documented cost objectives are 4.3371167974 and 4.51254342699, an increase of about 4.0448%. The complete-case cholesterol objectives are 0 and 3.1; the all-row zero-fill sensitivity objectives are zero within numerical tolerance. These are verified example results, not assertions about unknown nutrition measurements.

The packaged scripts were also executed from outside the project folder using `--data-dir` and `--output-dir`. All six models returned Optimal and passed the checks. Both help commands were checked without data. The package was inspected for input and generated files, and the ignore rules were checked for spreadsheets, CSV files, outputs, environments, and submission documents. Relative documentation links were checked locally.

## Numerical checks

The small models allow a feasibility tolerance equal to one millionth of each nutrient maximum. The large models check lower and upper bounds separately using one millionth of the corresponding bound, with a minimum scale of one. Linking checks allow 0.000001 quantity units. Values are checked before display rounding.

All modeled cholesterol coefficients are nonnegative. A feasible zero-cholesterol menu therefore reaches the objective lower bound. In the complete-case modified model, the three smallest eligible coefficients are 0, 13, and 18; selecting at least 0.1 of three distinct options gives a lower bound of 3.1, which the solution attains.

## Scope of the evidence

Local runs use separately supplied course inputs; input files and generated food records are not distributed here. Reproduction requires access to those spreadsheets and the expected schema. Matching a numerical objective does not identify a unique menu.

The 287-row filter changes which foods are available. The all-row run assumes missing coefficients are zero. Its constraint checks verify that assumed model, not the actual values of unknown measurements. Neither approach establishes that a menu is realistic, medically appropriate, or preferred by a person.

This project does not include a GitHub Actions workflow; the verification described here was run locally. No automated downloader, external data service, or deployment is part of the project.
