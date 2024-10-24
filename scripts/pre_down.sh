#!/bin/bash

. ./scripts/load_python_env.sh

# Get the directory of the current script
script_dir=$(dirname "$0")

# Run the Python script with the retrieved values
.venv/bin/python "$script_dir/pre_down.py" --subscription-id $subscription_id --resource-name $resource_name --resource-group $resource_group --tenant-id $tenant_id
