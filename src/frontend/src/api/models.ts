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

export type ResponseMessage = {
    content: string;
    role: string;
};

export type Thoughts = {
    title: string;
    description: any; // It can be any output from the api
    props?: { [key: string]: string };
};

export type ResponseContext = {
    data_points: string[];
    followup_questions: string[] | null;
    thoughts: Thoughts[];
};

export type ResponseChoice = {
    index: number;
    message: ResponseMessage;
    context: ResponseContext;
    session_state: any;
};

export type ChatAppResponseOrError = {
    choices?: ResponseChoice[];
    error?: string;
};

export type ChatAppResponse = {
    choices: ResponseChoice[];
};

export type ChatAppRequestContext = {
    overrides?: ChatAppRequestOverrides;
};

export type ChatAppRequest = {
    messages: ResponseMessage[];
    context?: ChatAppRequestContext;
};