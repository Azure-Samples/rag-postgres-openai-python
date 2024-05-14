class Global:
    def __init__(self):
        self.engine = None
        self.openai_chat_client = None
        self.openai_embed_client = None
        self.openai_chat_model = None
        self.openai_embed_model = None
        self.openai_embed_dimensions = None
        self.openai_chat_deployment = None
        self.openai_embed_deployment = None


global_storage = Global()
