# Input data

No datasets are included in this project. Supply the original `diet.xls` and `diet_large.xls` files separately from the Georgia Tech ISYE 6501 course materials.

Create `data/raw/` locally and place both spreadsheets there, or point the scripts to an existing private folder with `--data-dir`. Input files are read only. There is no automatic download.

The `.gitignore` excludes `data/raw/`, spreadsheet and tabular data files, and the generated output directories. Do not force-add inputs or food-level results.

## Expected layouts

- `diet.xls`: Sheet1 contains 64 foods, price and serving-size columns, 11 nutrition columns, and minimum/maximum daily-intake rows. Limits are identified through the Serving Size column.
- `diet_large.xls`: Sheet1 has a blank first row and headings on Excel row 2. Food descriptions are in `Long_Desc`. There are 7,146 food rows, followed by a blank separator and minimum, unit, and maximum rows. The two Energy headings are retained as separate columns by pandas. Twenty-seven columns have numeric bounds; cholesterol is the objective. The two unbounded fatty-acid columns are unused.

The large workbook does not label the cholesterol unit or provide serving sizes. The analysis reports reference-quantity multipliers and workbook cholesterol units rather than inventing a physical unit. It retains the supplied limits without reinterpreting them as medical recommendations.
