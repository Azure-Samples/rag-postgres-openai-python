# Get the directory of the current script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Run the Python script
python "$scriptDir/pre-down.py"
