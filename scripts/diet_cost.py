# Find the cheapest daily diet while meeting the supplied nutrition limits.

# Import the libraries and read the input and output folder options.
import argparse
from pathlib import Path
import json
import pandas as pd
import pulp

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description="Find minimum-cost diets with and without food-selection rules.")
parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw",
                    help="Folder containing diet.xls (default: data/raw).")
parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "cost",
                    help="Folder for generated results (default: outputs/cost).")
args = parser.parse_args()
data_path = args.data_dir.expanduser().resolve() / "diet.xls"
output_dir = args.output_dir.expanduser().resolve()
if not data_path.is_file():
    parser.error("diet.xls is not included. Supply it in data/raw or use --data-dir PATH.")

# Load the diet spreadsheet.
diet_data = pd.read_excel(
    data_path,
    sheet_name="Sheet1",
    engine="xlrd"
)

# Inspect the table size and first five rows.
print(diet_data.shape)
print(diet_data.head())


# Keep only rows containing a food name.
food_data = diet_data[diet_data["Foods"].notna()].copy()

# Select the nutrient columns, starting with Calories.
nutrient_columns = diet_data.columns[3:]

# Find the two daily nutrition-limit rows.
limits = diet_data.set_index("Serving Size")

minimum_intake = limits.loc[
    "Minimum daily intake", nutrient_columns
].astype(float)

maximum_intake = limits.loc[
    "Maximum daily intake", nutrient_columns
].astype(float)

# Check the food count and display the limits together.
print("Number of foods:", len(food_data))
print(pd.DataFrame({
    "Minimum": minimum_intake,
    "Maximum": maximum_intake
}))

# Create a model that minimizes cost.
diet_model = pulp.LpProblem("Diet_Part_1", pulp.LpMinimize)

# Create one servings variable for each food.
servings = {
    i: diet_model.add_variable(
        f"servings_{i}",
        lowBound=0,
        cat="Continuous"
    )
    for i in food_data.index
}

# Minimize the total cost of all chosen servings.
diet_model += pulp.lpSum(
    food_data.loc[i, "Price/ Serving"] * servings[i]
    for i in food_data.index
), "Total_Daily_Cost"

print("Decision variables created:", len(servings))


# Add minimum and maximum limits for every nutrient.
for nutrient in nutrient_columns:
    total_nutrient = pulp.lpSum(
        food_data.loc[i, nutrient] * servings[i]
        for i in food_data.index
    )

    # Create a readable constraint name without spaces.
    name = nutrient.replace(" ", "_")

    diet_model += (
        total_nutrient >= minimum_intake[nutrient],
        f"Min_{name}"
    )
    diet_model += (
        total_nutrient <= maximum_intake[nutrient],
        f"Max_{name}"
    )

print("Nutrition constraints:", len(diet_model.constraints()))


# Solve the diet model using the CBC solver.
solve_result = diet_model.solve(pulp.COIN_CMD(msg=False))

# Display the solver status and objective value.
print(solve_result)
if int(solve_result.status) != 1:
    raise RuntimeError("The basic model did not return an optimal solution.")


# Collect the foods selected by the solver.
selected_foods = []

for i in food_data.index:
    amount = servings[i].value()

    if amount > 1e-6:
        selected_foods.append({
            "Food": food_data.loc[i, "Foods"],
            "Serving size": food_data.loc[i, "Serving Size"],
            "Servings": amount,
            "Daily cost": food_data.loc[i, "Price/ Serving"] * amount
        })

# Display the selected diet, rounded for readability.
diet_solution = pd.DataFrame(selected_foods)
print(diet_solution.round(4).to_string(index=False))
print(f"Minimum daily cost: ${solve_result.objective:.4f}")


# Recalculate nutrient totals using the solved servings.
nutrient_totals = pd.Series({
    nutrient: sum(
        food_data.loc[i, nutrient] * servings[i].value()
        for i in food_data.index
    )
    for nutrient in nutrient_columns
})

# Compare each total with its daily limits.
nutrition_check = pd.DataFrame({
    "Minimum": minimum_intake,
    "Total": nutrient_totals,
    "Maximum": maximum_intake
})

# Allow a tiny numerical tolerance: one part per million.
tolerance = 1e-6 * maximum_intake
nutrition_check["Within limits"] = nutrient_totals.between(
    minimum_intake - tolerance,
    maximum_intake + tolerance
)

print(nutrition_check.round(4).to_string())
print("All nutrient limits satisfied:",
      nutrition_check["Within limits"].all())


# Create a separate model for Part 2.
diet_model_2 = pulp.LpProblem("Diet_Part_2", pulp.LpMinimize)

# Decide how many servings of each food to include.
servings_2 = {
    i: diet_model_2.add_variable(
        f"servings_{i}",
        lowBound=0,
        cat="Continuous"
    )
    for i in food_data.index
}

# Decide whether each food is selected.
chosen = {
    i: diet_model_2.add_variable(
        f"chosen_{i}",
        cat="Binary"
    )
    for i in food_data.index
}

print("Part 2 serving variables:", len(servings_2))
print("Part 2 selection variables:", len(chosen))


# Minimize the total daily cost in Part 2.
diet_model_2 += pulp.lpSum(
    food_data.loc[i, "Price/ Serving"] * servings_2[i]
    for i in food_data.index
), "Total_Daily_Cost"

# Apply the same daily nutrition requirements.
for nutrient in nutrient_columns:
    total_nutrient_2 = pulp.lpSum(
        food_data.loc[i, nutrient] * servings_2[i]
        for i in food_data.index
    )

    name = nutrient.replace(" ", "_")

    diet_model_2 += (
        total_nutrient_2 >= minimum_intake[nutrient],
        f"Min_{name}"
    )
    diet_model_2 += (
        total_nutrient_2 <= maximum_intake[nutrient],
        f"Max_{name}"
    )

print("Part 2 nutrition constraints:",
      len(diet_model_2.constraints()))


# Calculate a valid maximum serving amount for each food.
max_servings = (
    maximum_intake["Calories"] / food_data["Calories"]
)

# Link food selection to its serving amount.
for i in food_data.index:
    diet_model_2 += (
        servings_2[i] >= 0.1 * chosen[i],
        f"Minimum_Serving_{i}"
    )

    diet_model_2 += (
        servings_2[i] <= max_servings.loc[i] * chosen[i],
        f"Selection_Link_{i}"
    )

print("Part 2 total constraints:",
      len(diet_model_2.constraints()))


# Find the rows for celery and frozen broccoli.
celery_index = food_data.index[
    food_data["Foods"] == "Celery, Raw"
][0]

broccoli_index = food_data.index[
    food_data["Foods"] == "Frozen Broccoli"
][0]

# Allow at most one of these two foods.
diet_model_2 += (
    chosen[celery_index] + chosen[broccoli_index] <= 1,
    "Celery_or_Broccoli"
)

print("Part 2 total constraints:",
      len(diet_model_2.constraints()))


# Define the meat, poultry, fish, and egg food options.
protein_foods = [
    "Roasted Chicken",
    "Poached Eggs",
    "Scrambled Eggs",
    "Bologna,Turkey",
    "Frankfurter, Beef",
    "Ham,Sliced,Extralean",
    "Kielbasa,Prk",
    "Pork",
    "Sardines in Oil",
    "White Tuna in Water"
]

# Find their rows in the food table.
protein_indices = food_data.index[
    food_data["Foods"].isin(protein_foods)
]

# Require at least three eligible food options.
diet_model_2 += (
    pulp.lpSum(chosen[i] for i in protein_indices) >= 3,
    "Protein_Variety"
)

print("Eligible protein foods:", len(protein_indices))
print("Part 2 total constraints:",
      len(diet_model_2.constraints()))


# Solve Part 2 with zero absolute and relative gap targets.
solve_result_2 = diet_model_2.solve(
    pulp.COIN_CMD(
        msg=False,
        gapRel=0,
        gapAbs=0
    )
)

print(solve_result_2)
if int(solve_result_2.status) != 1:
    raise RuntimeError("The modified model did not return an optimal solution.")


# Collect the foods selected in Part 2.
selected_foods_2 = []

for i in food_data.index:
    amount = servings_2[i].value()

    if amount > 1e-6:
        selected_foods_2.append({
            "Food": food_data.loc[i, "Foods"],
            "Serving size": food_data.loc[i, "Serving Size"],
            "Servings": amount,
            "Daily cost": food_data.loc[i, "Price/ Serving"] * amount
        })

# Display the Part 2 diet.
diet_solution_2 = pd.DataFrame(selected_foods_2)
print(diet_solution_2.round(4).to_string(index=False))
print(f"Part 2 minimum daily cost: ${solve_result_2.objective:.4f}")


# Recalculate nutrient totals for the Part 2 diet.
nutrient_totals_2 = pd.Series({
    nutrient: sum(
        food_data.loc[i, nutrient] * servings_2[i].value()
        for i in food_data.index
    )
    for nutrient in nutrient_columns
})

# Compare Part 2 totals with the daily limits.
nutrition_check_2 = pd.DataFrame({
    "Minimum": minimum_intake,
    "Total": nutrient_totals_2,
    "Maximum": maximum_intake
})

nutrition_check_2["Within limits"] = nutrient_totals_2.between(
    minimum_intake - tolerance,
    maximum_intake + tolerance
)

print(nutrition_check_2.round(4).to_string())
print("Part 2 nutrient limits satisfied:",
      nutrition_check_2["Within limits"].all())

# Check both linking constraints for every food.
linking_ok = all(
    0.1 * chosen[i].value() - 1e-6
    <= servings_2[i].value()
    <= max_servings.loc[i] * chosen[i].value() + 1e-6
    for i in food_data.index
)

# Count the selected celery/broccoli options.
celery_broccoli_count = (
    chosen[celery_index].value()
    + chosen[broccoli_index].value()
)

# Count selected foods in our eligible protein group.
protein_count = sum(
    chosen[i].value() > 0.5
    for i in protein_indices
)

print("Serving-selection links satisfied:", linking_ok)
print("Celery/broccoli rule satisfied:",
      celery_broccoli_count <= 1 + 1e-6)
print("Eligible protein foods selected:", protein_count)
print("Protein-variety rule satisfied:", protein_count >= 3)


# Compare the costs of the two diets.
cost_1 = solve_result.objective
cost_2 = solve_result_2.objective

cost_increase = cost_2 - cost_1
percent_increase = 100 * cost_increase / cost_1

print(f"Part 1 daily cost: ${cost_1:.4f}")
print(f"Part 2 daily cost: ${cost_2:.4f}")
print(f"Daily cost increase: ${cost_increase:.4f}")
print(f"Percentage increase: {percent_increase:.2f}%")

# Check the solutions before saving the calculated results.
assert nutrition_check["Within limits"].all()
assert nutrition_check_2["Within limits"].all()
assert linking_ok and celery_broccoli_count <= 1 + 1e-6 and protein_count >= 3
assert cost_2 >= cost_1 - 1e-6

# Save the two menus, nutrition checks, and daily cost comparison locally.
output_dir.mkdir(parents=True, exist_ok=True)
diet_solution.to_csv(output_dir / "basic_selected_foods.csv", index=False)
diet_solution_2.to_csv(output_dir / "modified_selected_foods.csv", index=False)
nutrition_check.to_csv(output_dir / "basic_nutrition_check.csv")
nutrition_check_2.to_csv(output_dir / "modified_nutrition_check.csv")
summary = {"foods": len(food_data), "nutrients": len(nutrient_columns),
           "basic_daily_cost": cost_1, "modified_daily_cost": cost_2,
           "daily_increase": cost_increase, "percent_increase": percent_increase,
           "selected_protein_options": int(protein_count)}
(output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(f"Saved results in {output_dir}")
