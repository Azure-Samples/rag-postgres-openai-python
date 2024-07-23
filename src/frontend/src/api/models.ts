import { AIChatCompletion, AIChatCompletionDelta, AIChatCompletionOperationOptions } from "@microsoft/ai-chat-protocol";

export const enum RetrievalMode {
    Hybrid = "hybrid",
    Vectors = "vectors",
    Text = "text"
}

export type ChatAppRequestOverrides = {
    use_advanced_flow?: boolean;
    retrieval_mode?: RetrievalMode;
    top?: number;
    temperature?: number;
    prompt_template?: string;
};

export type ChatAppRequestContext = {
    overrides: ChatAppRequestOverrides;
};

export interface ChatAppRequestOptions extends AIChatCompletionOperationOptions {
    context: ChatAppRequestContext
}

export type Thoughts = {
    title: string;
    description: any; // It can be any output from the api
    props?: { [key: string]: string };
};

export type RAGContext = {
    data_points: { [key: string]: any };
    followup_questions: string[] | null;
    thoughts: Thoughts[];
};

export interface RAGChatCompletion extends AIChatCompletion {
    context: RAGContext;
}

export interface RAGChatCompletionDelta extends AIChatCompletionDelta {
    context: RAGContext;
}
