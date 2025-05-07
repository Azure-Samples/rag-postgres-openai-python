import ast
import csv
import json

# Read CSV file - Using the correct dialect to handle quotes properly
with open("data.csv", encoding="utf-8") as csv_file:
    # Use the csv.reader with proper quoting parameters
    csv_reader = csv.reader(csv_file, quoting=csv.QUOTE_ALL, doublequote=True, escapechar="\\")
    header = next(csv_reader)  # Get the header row
    data = list(csv_reader)  # Get all data rows

# Convert to JSON format
json_data = []
for row in data:
    item = {}
    for i in range(len(header)):
        if i < len(row):  # Ensure we don't go out of bounds
            value = row[i].strip()
            # Check if the value looks like a JSON array
            if value.startswith("[") and value.endswith("]"):
                try:
                    # Parse the JSON-like string into a Python object
                    value = json.loads(value.replace("'", '"'))
                except (ValueError, SyntaxError):
                    try:
                        # Try with ast as a fallback
                        value = ast.literal_eval(value)
                    except (ValueError, SyntaxError):
                        # If parsing fails, keep it as a string
                        pass
            # Convert boolean strings
            elif value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            # Try to convert numbers
            elif value.isdigit():
                value = int(value)
            elif value.replace(".", "", 1).isdigit() and value.count(".") <= 1:
                value = float(value)

            item[header[i]] = value
    # remove is_open column
    del item["is_open"]
    json_data.append(item)

# Write to JSON file
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(json_data, f, indent=4, ensure_ascii=False)

print(f"Successfully converted CSV data to JSON format with {len(json_data)} records")
