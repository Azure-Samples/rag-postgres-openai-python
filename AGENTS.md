# Instructions for coding agents

## Adding new azd environment variables

An azd environment variable is stored by the azd CLI for each environment. It is passed to the "azd up" command and can configure both provisioning options and application settings.
When adding new azd environment variables, update:

1. infra/main.parameters.json : Add the new parameter with a Bicep-friendly variable name and map to the new environment variable
1. infra/main.bicep: Add the new Bicep parameter at the top, and add it to the `webAppEnv` object
1. .github/workflows/azure-dev.yml: Add the new environment variable under `env` section. If it's a @secure variable in main.bicep, it should come from `secrets`, otherwise from `vars`.
