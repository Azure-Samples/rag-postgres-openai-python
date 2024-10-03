# Evaluating the RAG answer quality

## Deploy a GPT-4 model


1. Run this command to tell `azd` to deploy a GPT-4 model for evaluation:

    ```shell
    azd env set DEPLOY_EVAL_MODEL true
    ```

2. Set the capacity to the highest possible value to ensure that the evaluation runs quickly.

    ```shell
    azd env set AZURE_OPENAI_EVAL_DEPLOYMENT_CAPACITY 100
    ```

    By default, that will provision a `gpt-4` model, version `turbo-2024-04-09`. To change those settings, set the `AZURE_OPENAI_EVAL_DEPLOYMENT` and `AZURE_OPENAI_EVAL_DEPLOYMENT_VERSION` environment variables.

3. Then, run the following command to provision the model:

    ```shell
    azd provision
    ```

## Setup the evaluation environment

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
