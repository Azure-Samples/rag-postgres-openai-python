pip install -r requirements-dev.txt

python evals/generate.py

python evals/evaluate.py

# TODO: Add GPT-4 deployment with high capacity for evaluation
# TODO: Add CI workflow that can be triggered to run the evaluate on the local app
