# Compare low-cholesterol diets and two ways of handling missing values.
# Find a diet with the lowest cholesterol using diet_large.xls.

# Import the libraries needed to read the data, solve the models, and save results.
from pathlib import Path
import argparse
import hashlib
import json
import platform

import numpy as np
import pandas as pd
import pulp


# Set the default folders for the spreadsheet and generated results.
ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "raw" / "diet_large.xls"
OUTPUT = ROOT / "outputs" / "cholesterol"

# Define the meat, poultry, fish, seafood, and egg food options.
# Count different preparations separately and leave out mixed dishes and dairy.
PROTEIN_PREFIXES = (
    "Egg,", "Eggs,", "Beef,", "Pork,", "Chicken,", "Turkey,", "Duck,",
    "Goose,", "Lamb,", "Veal,", "Game meat,", "Fish,", "Crustaceans,",
    "Mollusks,", "Whale,", "Beerwurst,", "Bologna,", "Bratwurst,",
    "Braunschweiger", "Brotwurst,", "Cheesefurter,", "Dutch brand loaf,",
    "Frankfurter,", "Honey loaf,", "Olive loaf,", "Peppered loaf,",
    "Pepperoni,", "Pickle and pimiento loaf,", "Pork sausage,",
    "Pork and beef sausage,", "Turkey sausage,", "Salami,", "Sausage,",
)


# Load the foods and separate them from the daily nutrition limits.
def load_data(zero_fill=False):
    # Read the large spreadsheet. The column headings are in Excel row 2.
    raw = pd.read_excel(DATA_PATH, sheet_name="Sheet1", header=1, engine="xlrd")
    assert raw.columns[0] == "Long_Desc"

    # Separate the food rows from the minimum, unit, and maximum rows.
    all_foods = raw.loc[raw["Long_Desc"].notna()].copy()
    tail = raw.loc[raw["Long_Desc"].isna()].dropna(how="all")
    assert len(tail) == 3, "Expected minimum, units, and maximum rows."

    # Read the daily limits and keep nutrients that have both limits.
    minimum = pd.to_numeric(tail.iloc[0, 1:], errors="coerce")
    units = tail.iloc[1, 1:]
    maximum = pd.to_numeric(tail.iloc[2, 1:], errors="coerce")
    nutrients = list(minimum.index[minimum.notna() & maximum.notna()])
    assert len(nutrients) == 27
    assert minimum[nutrients].le(maximum[nutrients]).all()

    # Keep foods with all values needed for the nutrition rules and cholesterol.
    # Leave missing values as missing instead of replacing them with zero.
    required = nutrients + ["Cholesterol"]
    values = all_foods[required].apply(pd.to_numeric, errors="coerce")
    complete = values.notna().all(axis=1)

    # Record which foods were left out and which values were missing.
    excluded = all_foods.loc[~complete, ["Long_Desc"]].copy()
    excluded.insert(0, "Excel row", excluded.index + 3)
    excluded["Missing required columns"] = values.loc[~complete].apply(
        lambda row: "; ".join(row.index[row.isna()]), axis=1
    )

    # Use complete rows normally, or all rows for the zero-fill sensitivity run.
    # Zero filling is an assumption for comparison, not a correction to the data.
    keep = pd.Series(True, index=all_foods.index) if zero_fill else complete
    used_values = values.fillna(0) if zero_fill else values
    foods = all_foods.loc[keep, ["Long_Desc"]].join(used_values.loc[keep])
    foods["Imputed coefficient count"] = values.loc[keep].isna().sum(axis=1)
    foods["Cholesterol imputed"] = values.loc[keep, "Cholesterol"].isna()
    foods.insert(0, "Excel row", foods.index + 3)
    foods = foods.reset_index(drop=True)

    # Check that the values used in the model are finite and nonnegative.
    assert np.isfinite(foods[required].to_numpy()).all()
    assert foods[required].ge(0).all().all()

    # Return the cleaned foods, limits, and excluded rows.
    return foods, nutrients, minimum[nutrients], maximum[nutrients], units, excluded, len(all_foods)


# Build and solve either the basic model or the model with the extra food rules.
def solve_model(foods, nutrients, minimum, maximum, add_rules, output_dir=OUTPUT, basic_result=None):
    # Create a model that minimizes daily cholesterol.
    label = "modified" if add_rules else "basic"
    model = pulp.LpProblem(f"Large_Diet_{label}", pulp.LpMinimize)

    # Create one nonnegative quantity variable for each food.
    # Quantities multiply the spreadsheet values; serving sizes are not supplied.
    x = {i: model.add_variable(f"quantity_{i}", lowBound=0, cat="Continuous")
         for i in foods.index}

    # Add the cholesterol from every food to form the objective.
    model += pulp.lpSum(float(foods.at[i, "Cholesterol"]) * x[i]
                        for i in foods.index), "Total_cholesterol"

    # Apply the minimum and maximum daily limits for all 27 nutrients.
    for j, nutrient in enumerate(nutrients):
        total = pulp.lpSum(float(foods.at[i, nutrient]) * x[i] for i in foods.index)
        model += total >= float(minimum[nutrient]), f"Minimum_{j}"
        model += total <= float(maximum[nutrient]), f"Maximum_{j}"

    # Calculate a valid maximum quantity for each food from its nutrition limits.
    # Use the tightest limit when more than one nutrient gives an upper bound.
    a = foods[nutrients].to_numpy(dtype=float)
    bounds = np.full_like(a, np.inf)
    np.divide(maximum.to_numpy(dtype=float), a, out=bounds, where=a > 0)
    big_m = bounds.min(axis=1)
    assert np.isfinite(big_m).all()

    # Find the eligible protein foods, raw celery, and frozen broccoli.
    names = foods["Long_Desc"].str.strip()
    eligible = names.str.startswith(PROTEIN_PREFIXES)
    celery = names.eq("Celery, raw")
    broccoli = names.str.startswith("Broccoli, frozen,")
    z = None
    group_variables = []
    group_rows = []

    # Add selection variables and food rules only for the modified model.
    if add_rules:
        # Decide whether each food is selected.
        z = {i: model.add_variable(f"chosen_{i}", cat="Binary") for i in foods.index}

        # Link each food's quantity to its selection variable.
        # A selected food must have at least a 0.1 quantity multiplier.
        for i in foods.index:
            model += x[i] >= 0.1 * z[i], f"Minimum_quantity_{i}"
            model += x[i] <= float(big_m[i]) * z[i], f"Selection_link_{i}"
        # Allow at most one option from raw celery and frozen broccoli.
        # This rule also applies when these foods are present in the all-row run.
        model += pulp.lpSum(z[i] for i in foods.index[celery | broccoli]) <= 1, "Celery_or_broccoli"

        # Count each distinct protein description once, even if rows repeat it.
        protein_choices = []
        for number, (_, members) in enumerate(names[eligible].groupby(names[eligible])):
            indices = list(members.index)
            if len(indices) == 1:
                protein_choices.append(z[indices[0]])
            else:
                group = model.add_variable(f"protein_group_{number}", cat="Binary")
                group_variables.append(group)
                group_rows.append(indices)
                for i in indices:
                    model += z[i] <= group, f"Protein_group_member_{i}"
                model += group <= pulp.lpSum(z[i] for i in indices), f"Protein_group_used_{number}"
                protein_choices.append(group)

        # Require at least three distinct eligible food descriptions.
        assert len(protein_choices) >= 3
        model += pulp.lpSum(protein_choices) >= 3, "Protein_variety"

    # Give the large binary model a feasible starting menu to speed up the solve.
    # This changes the starting point, not the cholesterol objective or its rules.
    warm_start = False
    if add_rules and len(foods) > 1000 and basic_result["objective"] == 0:
        start_rows = {int(row["Excel row"]) for row in basic_result["selected_foods"]}
        zero_protein = foods.loc[eligible & foods["Cholesterol"].eq(0)]
        start_rows.update(zero_protein.drop_duplicates("Long_Desc")["Excel row"].head(3))
        indices = list(foods.index[foods["Excel row"].isin(start_rows)])
        start_model = pulp.LpProblem("Starting_menu", pulp.LpMinimize)
        q = {i: start_model.add_variable(f"start_{i}", lowBound=0.1) for i in indices}
        start_model += pulp.lpSum(q.values())
        for j, nutrient in enumerate(nutrients):
            total = pulp.lpSum(float(foods.at[i, nutrient]) * q[i] for i in indices)
            start_model += total >= float(minimum[nutrient]), f"Start_min_{j}"
            start_model += total <= float(maximum[nutrient]), f"Start_max_{j}"
        start_result = start_model.solve(pulp.COIN_CMD(msg=False))
        if int(start_result.status) == 1 and not (celery | broccoli).loc[indices].any():
            for i in foods.index:
                x[i].setInitialValue(q[i].value() if i in q else 0)
                z[i].setInitialValue(1 if i in q else 0)
            for group, members in zip(group_variables, group_rows):
                group.setInitialValue(int(any(i in q for i in members)))
            warm_start = True

    # Solve the model and display the solver status.
    result = model.solve(pulp.COIN_CMD(msg=False, gapRel=0, gapAbs=0,
                                     warmStart=warm_start, timeLimit=120))
    print(f"\n{label.upper()} MODEL\n{result}")

    # Stop if the solver has not found an optimal solution.
    if not result.has_solution or int(result.status) != 1:
        raise RuntimeError(f"{label} did not return Optimal; no final result exported.")

    # Read the solved quantities and recalculate total cholesterol.
    amounts = np.array([x[i].value() for i in foods.index], dtype=float)
    cholesterol = float(foods["Cholesterol"].to_numpy(dtype=float) @ amounts)
    # Display tiny negative round-off as zero and retain the raw value for checking.
    raw_cholesterol = cholesterol
    if -1e-6 < cholesterol < 0:
        cholesterol = 0.0

    # Recalculate the nutrition totals from the solved quantities.
    totals = a.T @ amounts

    # Allow a small numerical tolerance when checking the daily limits.
    lower_tol = 1e-6 * np.maximum(1, np.abs(minimum.to_numpy(dtype=float)))
    upper_tol = 1e-6 * np.maximum(1, np.abs(maximum.to_numpy(dtype=float)))

    # Check the quantities, nutrition limits, and cholesterol total.
    checks = {
        "optimal_status": int(result.status) == 1,
        "nonnegative_quantities": bool((amounts >= -1e-6).all()),
        "all_nutrient_bounds": bool(((totals >= minimum.to_numpy() - lower_tol)
                                    & (totals <= maximum.to_numpy() + upper_tol)).all()),
        "objective_matches": bool(np.isclose(cholesterol, result.objective, atol=1e-6)),
    }
    # Check the additional selection rules for the modified model.
    chosen_values = None
    if add_rules:
        chosen_values = np.array([z[i].value() for i in foods.index], dtype=float)
        checks.update({
            "binary_selections": bool((np.isclose(chosen_values, np.round(chosen_values), atol=1e-6)
                                       & (chosen_values >= -1e-6) & (chosen_values <= 1 + 1e-6)).all()),
            "both_linking_bounds": bool(((amounts >= 0.1 * chosen_values - 1e-6)
                                         & (amounts <= big_m * chosen_values + 1e-6)).all()),
            "celery_broccoli_rule": bool(chosen_values[celery | broccoli].sum() <= 1 + 1e-6),
            "protein_variety": names[eligible & (chosen_values > 0.5)].nunique() >= 3,
        })
    # Stop if any solution check fails.
    assert all(checks.values()), checks

    # Collect only the foods with a positive quantity in the solution.
    selected = foods.loc[amounts > 1e-7, ["Excel row", "Long_Desc", "Imputed coefficient count", "Cholesterol imputed"]].copy()
    selected["Quantity multiplier"] = amounts[amounts > 1e-7]
    selected["Cholesterol contribution"] = (
        foods.loc[amounts > 1e-7, "Cholesterol"].to_numpy() * amounts[amounts > 1e-7]
    )
    selected["Eligible protein option"] = eligible[amounts > 1e-7].to_numpy()
    selected["Selection value"] = chosen_values[amounts > 1e-7] if add_rules else np.nan

    # Put every nutrition total beside its daily minimum and maximum.
    nutrition = pd.DataFrame({"Nutrient": nutrients, "Minimum": minimum.to_numpy(),
                              "Total": totals, "Maximum": maximum.to_numpy()})
    nutrition["Within limits"] = ((totals >= minimum.to_numpy() - lower_tol)
                                   & (totals <= maximum.to_numpy() + upper_tol))

    # Save the selected foods and nutrition checks without display rounding.
    selected.to_csv(output_dir / f"{label}_selected_foods.csv", index=False)
    nutrition.to_csv(output_dir / f"{label}_nutrition_check.csv", index=False)
    if add_rules:
        # Save all selection variables so every link and group can be checked.
        decisions = foods[["Excel row", "Long_Desc"]].copy()
        decisions["Quantity multiplier"] = amounts
        decisions["Selection value"] = chosen_values
        decisions["Maximum quantity"] = big_m
        decisions["Eligible protein option"] = eligible
        decisions.to_csv(output_dir / "modified_all_decisions.csv", index=False)

    # Display the selected diet, cholesterol total, and verification result.
    print(selected.round(6).to_string(index=False))
    print(f"Total cholesterol: {cholesterol:.6f} workbook cholesterol units/day")
    print("All verification checks:", all(checks.values()))
    # Return the results so they can be included in the final summary.
    return {"objective": cholesterol, "raw_objective": raw_cholesterol,
            "warm_start_used": warm_start, "status": str(result.status), "checks": checks,
            "selected_foods": json.loads(selected.to_json(orient="records")),
            "selected_count": len(selected), "variables": len(x) + (len(z) if z else 0) + len(group_variables),
            "constraints": len(model.constraints()),
            "eligible_selected": int(names[eligible & (chosen_values > 0.5)].nunique()) if add_rules else None}


# Run both versions of the optional diet model and save their results.
def run_analysis(zero_fill=False):
    # Create the results folder and load the food data.
    output_dir = OUTPUT / "all_rows_zero_fill" if zero_fill else OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)
    foods, nutrients, minimum, maximum, units, excluded, original_count = load_data(zero_fill)

    # Save the excluded foods and the protein-food classification.
    excluded.to_csv(output_dir / ("rows_with_missing_inputs.csv" if zero_fill else "excluded_incomplete_rows.csv"), index=False)
    classification = foods[["Excel row", "Long_Desc"]].copy()
    classification["Eligible protein option"] = foods["Long_Desc"].str.strip().str.startswith(PROTEIN_PREFIXES)
    classification.to_csv(output_dir / "food_classification.csv", index=False)

    # Display how many foods are available and explain the quantity units.
    policy = "Assume missing coefficients are zero, for sensitivity analysis only." if zero_fill else "Exclude rows missing any bounded nutrient or cholesterol."
    print("\nALL-ROW ZERO-FILL SENSITIVITY" if zero_fill else "\nCOMPLETE-ROW ANALYSIS")
    print(f"Source food rows: {original_count}; rows used: {len(foods)}; rows with missing inputs: {len(excluded)}")
    print(policy)
    print("Quantities are workbook reference-quantity multipliers; serving sizes are not supplied.")
    print("Both Energy columns and every numeric minimum/maximum are retained as supplied.")
    print("Raw celery/frozen broccoli rows retained:", int(foods.Long_Desc.str.strip().eq("Celery, raw").sum()),
          int(foods.Long_Desc.str.strip().str.startswith("Broccoli, frozen,").sum()))
    # Solve the basic model and then the model with the extra food-selection rules.
    basic = solve_model(foods, nutrients, minimum, maximum, add_rules=False, output_dir=output_dir)
    modified = solve_model(foods, nutrients, minimum, maximum, add_rules=True,
                           output_dir=output_dir, basic_result=basic)

    # Check that adding restrictions has not reduced the minimum cholesterol.
    assert modified["objective"] >= basic["objective"] - 1e-6

    # Collect the results, data assumptions, and software versions in one summary.
    summary = {"source_rows": original_count, "used_rows": len(foods), "excluded_rows": 0 if zero_fill else len(excluded),
               "bounded_nutrients": len(nutrients), "minimum_selected_quantity": 0.1,
               "missing_data_policy": policy, "sensitivity_only": zero_fill,
               "imputed_coefficients": int(foods["Imputed coefficient count"].sum()) if zero_fill else 0,
               "imputed_cholesterol_rows": int(foods["Cholesterol imputed"].sum()) if zero_fill else 0,
               "quantity_unit": "Multiplier of workbook reference quantity; serving size not stated.",
               "cholesterol_unit": "Workbook does not supply a cholesterol-unit label.",
               "eligible_protein_rows": int(classification["Eligible protein option"].sum()),
               "distinct_eligible_descriptions": int(foods.loc[classification["Eligible protein option"], "Long_Desc"].str.strip().nunique()),
               "basic": basic, "modified": modified,
               "versions": {"python": platform.python_version(), "pulp": pulp.__version__,
                            "pandas": pd.__version__},
               "data_sha256": hashlib.sha256(DATA_PATH.read_bytes()).hexdigest(),
               "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    # Save the summary and display the location of the output files.
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSaved full-precision results in {output_dir}")
    return summary


# Compare complete rows with all rows under the stated zero-fill assumption.
def main():
    # Let the data stay outside the repository if it is stored in another folder.
    global DATA_PATH, OUTPUT
    parser = argparse.ArgumentParser(description="Compare complete-case and all-row zero-fill cholesterol models.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw",
                        help="Folder containing diet_large.xls (default: data/raw).")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "cholesterol",
                        help="Folder for generated results (default: outputs/cholesterol).")
    args = parser.parse_args()
    DATA_PATH = args.data_dir.expanduser().resolve() / "diet_large.xls"
    OUTPUT = args.output_dir.expanduser().resolve()
    if not DATA_PATH.is_file():
        parser.error("diet_large.xls is not included. Supply it in data/raw or use --data-dir PATH.")

    # Run the original complete-row approach and the all-row sensitivity analysis.
    complete = run_analysis(zero_fill=False)
    all_rows = run_analysis(zero_fill=True)
    comparison = {"complete_rows": complete, "all_rows_zero_fill": all_rows}
    (OUTPUT / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print("\nComparison: complete rows versus all-row zero-fill sensitivity")
    for label, result in comparison.items():
        print(label, "foods:", result["used_rows"], "basic:", result["basic"]["objective"],
              "modified:", result["modified"]["objective"])


# Run the analysis when this file is executed.
if __name__ == "__main__":
    main()
