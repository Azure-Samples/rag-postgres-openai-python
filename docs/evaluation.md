# Evaluating the RAG answer quality

Install all the dependencies for the evaluation script by running the following command:

```bash
pip install -r requirements-dev.txt
```

## Generate ground truth data

Generate ground truth data by running the following command:

```bash
python evals/generate.py
```

Review the generated data after running that script, removing any question/answer pairs that don't seem like realistic user input.

## Evaluate the RAG answer quality

Review the configuration in `evals/eval_config.json` to ensure that everything is correctly setup. You may want to adjust the metrics used. [TODO: link to evaluator docs]

By default, the evaluation script will evaluate every question in the ground truth data.
Run the evaluation script by running the following command:

```bash
python evals/evaluate.py
```

## Review the evaluation results

The evaluation script will output a summary of the evaluation results, inside the `evals/results` directory.

You can see a summary of results across all evaluation runs by running the following command:

```bash
python -m evaltools summary evals/results
```

Compare answers across runs by running the following command:

```bash
python -m evaltools diff evals/results/baseline/
```

## Run the evaluation in GitHub actions


# TODO: Add GPT-4 deployment with high capacity for evaluation
# TODO: Add CI workflow that can be triggered to run the evaluate on the local app
