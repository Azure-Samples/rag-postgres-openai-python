# RAG on PostgreSQL: Deploying with existing Azure resources

If you already have existing Azure resources, or if you want to specify the exact name of new Azure Resource, you can do so by setting `azd` environment values.
You should set these values before running `azd up`. Once you've set them, return to the [deployment steps](../README.md#deployment).

## Openai.com OpenAI account

1. Run `azd env set DEPLOY_AZURE_OPENAI false`
1. Run `azd env set OPENAI_CHAT_HOST openaicom`
2. Run `azd env set OPENAI_EMBED_HOST openaicom`
3. Run `azd env set OPENAICOM_KEY {Your OpenAI API key}`
4. Run `azd up`

You can retrieve your OpenAI key by checking [your user page](https://platform.openai.com/account/api-keys).
Learn more about creating an OpenAI free trial at [this link](https://openai.com/pricing).
Do *not* check your key into source control.

When you run `azd up` after and are prompted to select a value for `openAiResourceGroupLocation`, you can select any location as it will not be used.
