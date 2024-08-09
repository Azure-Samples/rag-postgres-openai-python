import { useRef, useState, useEffect } from "react";
import { Panel, DefaultButton, TextField, SpinButton, Slider, Checkbox } from "@fluentui/react";
import { SparkleFilled } from "@fluentui/react-icons";

import styles from "./Chat.module.css";

import { RetrievalMode, RAGChatCompletion, RAGChatCompletionDelta, ChatAppRequestOptions } from "../../api";
import { AIChatProtocolClient, AIChatMessage } from "@microsoft/ai-chat-protocol";
import { Answer, AnswerError, AnswerLoading } from "../../components/Answer";
import { QuestionInput } from "../../components/QuestionInput";
import { ExampleList } from "../../components/Example";
import { UserChatMessage } from "../../components/UserChatMessage";
import { AnalysisPanel, AnalysisPanelTabs } from "../../components/AnalysisPanel";
import { SettingsButton } from "../../components/SettingsButton";
import { ClearChatButton } from "../../components/ClearChatButton";
import { VectorSettings } from "../../components/VectorSettings";

const Chat = () => {
    const [isConfigPanelOpen, setIsConfigPanelOpen] = useState(false);
    const [promptTemplate, setPromptTemplate] = useState<string>("");
    const [temperature, setTemperature] = useState<number>(0.3);
    const [retrieveCount, setRetrieveCount] = useState<number>(3);
    const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>(RetrievalMode.Hybrid);
    const [useAdvancedFlow, setUseAdvancedFlow] = useState<boolean>(true);
    const [shouldStream, setShouldStream] = useState<boolean>(true);

    const lastQuestionRef = useRef<string>("");
    const chatMessageStreamEnd = useRef<HTMLDivElement | null>(null);

    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [isStreaming, setIsStreaming] = useState<boolean>(false);
    const [error, setError] = useState<unknown>();

    const [activeCitation, setActiveCitation] = useState<string>();
    const [activeAnalysisPanelTab, setActiveAnalysisPanelTab] = useState<AnalysisPanelTabs | undefined>(undefined);

    const [selectedAnswer, setSelectedAnswer] = useState<number>(0);
    const [answers, setAnswers] = useState<[user: string, response: RAGChatCompletion][]>([]);
    const [streamedAnswers, setStreamedAnswers] = useState<[user: string, response: RAGChatCompletion][]>([]);

    const handleAsyncRequest = async (question: string, answers: [string, RAGChatCompletion][], result: AsyncIterable<RAGChatCompletionDelta>) => {
        let answer = "";
        let chatCompletion: RAGChatCompletion = {
            context: {
                data_points: {},
                followup_questions: null,
                thoughts: []
            },
            message: { content: "", role: "assistant" }
        };
        const updateState = (newContent: string) => {
            return new Promise(resolve => {
                setTimeout(() => {
                    answer += newContent;
                    // We need to create a new object to trigger a re-render
                    const latestCompletion: RAGChatCompletion = {
                        ...chatCompletion,
                        message: { content: answer, role: chatCompletion.message.role }
                    };
                    setStreamedAnswers([...answers, [question, latestCompletion]]);
                    resolve(null);
                }, 33);
            });
        };
        try {
            setIsStreaming(true);
            for await (const response of result) {
                if (response.context) {
                    chatCompletion.context = {
                        ...chatCompletion.context,
                        ...response.context
                    };
                }
                if (response.delta && response.delta.role) {
                    chatCompletion.message.role = response.delta.role;
                }
                if (response.delta && response.delta.content) {
                    setIsLoading(false);
                    await updateState(response.delta.content);
                }
            }
        } finally {
            setIsStreaming(false);
        }
        chatCompletion.message.content = answer;
        return chatCompletion;
    };
    const makeApiRequest = async (question: string) => {
        lastQuestionRef.current = question;

        error && setError(undefined);
        setIsLoading(true);
        setActiveCitation(undefined);
        setActiveAnalysisPanelTab(undefined);

        try {
            const messages: AIChatMessage[] = answers.flatMap(answer => [
                { content: answer[0], role: "user" },
                { content: answer[1].message.content, role: "assistant" }
            ]);
            const allMessages: AIChatMessage[] = [...messages, { content: question, role: "user" }];
            const options: ChatAppRequestOptions = {
                context: {
                    overrides: {
                        use_advanced_flow: useAdvancedFlow,
                        top: retrieveCount,
                        retrieval_mode: retrievalMode,
                        prompt_template: promptTemplate.length === 0 ? undefined : promptTemplate,
                        temperature: temperature
                    }
                },
                sessionState: answers.length ? answers[answers.length - 1][1].sessionState : null
            };
            const chatClient: AIChatProtocolClient = new AIChatProtocolClient("/chat");
            if (shouldStream) {
                const result = (await chatClient.getStreamedCompletion(allMessages, options)) as AsyncIterable<RAGChatCompletionDelta>;
                const parsedResponse = await handleAsyncRequest(question, answers, result);
                setAnswers([...answers, [question, parsedResponse]]);
            } else {
                const result = (await chatClient.getCompletion(allMessages, options)) as RAGChatCompletion;
                setAnswers([...answers, [question, result]]);
            }
        } catch (e) {
            setError(e);
        } finally {
            setIsLoading(false);
        }
    };

    const clearChat = () => {
        lastQuestionRef.current = "";
        error && setError(undefined);
        setActiveCitation(undefined);
        setActiveAnalysisPanelTab(undefined);
        setAnswers([]);
        setStreamedAnswers([]);
        setIsLoading(false);
        setIsStreaming(false);
    };

    useEffect(() => chatMessageStreamEnd.current?.scrollIntoView({ behavior: "smooth" }), [isLoading]);
    useEffect(() => chatMessageStreamEnd.current?.scrollIntoView({ behavior: "auto" }), [streamedAnswers]);

    const onPromptTemplateChange = (_ev?: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>, newValue?: string) => {
        setPromptTemplate(newValue || "");
    };

    const onTemperatureChange = (
        newValue: number,
        range?: [number, number],
        event?: React.MouseEvent | React.TouchEvent | MouseEvent | TouchEvent | React.KeyboardEvent
    ) => {
        setTemperature(newValue);
    };

    const onRetrieveCountChange = (_ev?: React.SyntheticEvent<HTMLElement, Event>, newValue?: string) => {
        setRetrieveCount(parseInt(newValue || "3"));
    };

    const onUseAdvancedFlowChange = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        setUseAdvancedFlow(!!checked);
    };

    const onShouldStreamChange = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        setShouldStream(!!checked);
    };

    const onExampleClicked = (example: string) => {
        makeApiRequest(example);
    };

    const onShowCitation = (citation: string, index: number) => {
        if (activeCitation === citation && activeAnalysisPanelTab === AnalysisPanelTabs.CitationTab && selectedAnswer === index) {
            setActiveAnalysisPanelTab(undefined);
        } else {
            setActiveCitation(citation);
            setActiveAnalysisPanelTab(AnalysisPanelTabs.CitationTab);
        }

        setSelectedAnswer(index);
    };

    const onToggleTab = (tab: AnalysisPanelTabs, index: number) => {
        if (activeAnalysisPanelTab === tab && selectedAnswer === index) {
            setActiveAnalysisPanelTab(undefined);
        } else {
            setActiveAnalysisPanelTab(tab);
        }

        setSelectedAnswer(index);
    };

    return (
        <div className={styles.container}>
            <div className={styles.commandsContainer}>
                <ClearChatButton className={styles.commandButton} onClick={clearChat} disabled={!lastQuestionRef.current || isLoading} />
                <SettingsButton className={styles.commandButton} onClick={() => setIsConfigPanelOpen(!isConfigPanelOpen)} />
            </div>
            <div className={styles.chatRoot}>
                <div className={styles.chatContainer}>
                    {!lastQuestionRef.current ? (
                        <div className={styles.chatEmptyState}>
                            <SparkleFilled fontSize={"120px"} primaryFill={"rgba(115, 118, 225, 1)"} aria-hidden="true" aria-label="Chat logo" />
                            <h1 className={styles.chatEmptyStateTitle}>Product chat</h1>
                            <h2 className={styles.chatEmptyStateSubtitle}>Ask anything or try an example</h2>
                            <ExampleList onExampleClicked={onExampleClicked} />
                        </div>
                    ) : (
                        <div className={styles.chatMessageStream}>
                            {isStreaming &&
                                streamedAnswers.map((streamedAnswer, index) => (
                                    <div key={index}>
                                        <UserChatMessage message={streamedAnswer[0]} />
                                        <div className={styles.chatMessageGpt}>
                                            <Answer
                                                isStreaming={true}
                                                key={index}
                                                answer={streamedAnswer[1]}
                                                isSelected={false}
                                                onCitationClicked={c => onShowCitation(c, index)}
                                                onThoughtProcessClicked={() => onToggleTab(AnalysisPanelTabs.ThoughtProcessTab, index)}
                                                onSupportingContentClicked={() => onToggleTab(AnalysisPanelTabs.SupportingContentTab, index)}
                                                onFollowupQuestionClicked={q => makeApiRequest(q)}
                                            />
                                        </div>
                                    </div>
                                ))}
                            {!isStreaming &&
                                answers.map((answer, index) => (
                                    <div key={index}>
                                        <UserChatMessage message={answer[0]} />
                                        <div className={styles.chatMessageGpt}>
                                            <Answer
                                                isStreaming={false}
                                                key={index}
                                                answer={answer[1]}
                                                isSelected={selectedAnswer === index && activeAnalysisPanelTab !== undefined}
                                                onCitationClicked={c => onShowCitation(c, index)}
                                                onThoughtProcessClicked={() => onToggleTab(AnalysisPanelTabs.ThoughtProcessTab, index)}
                                                onSupportingContentClicked={() => onToggleTab(AnalysisPanelTabs.SupportingContentTab, index)}
                                                onFollowupQuestionClicked={q => makeApiRequest(q)}
                                            />
                                        </div>
                                    </div>
                                ))}
                            {isLoading && (
                                <>
                                    <UserChatMessage message={lastQuestionRef.current} />
                                    <div className={styles.chatMessageGptMinWidth}>
                                        <AnswerLoading />
                                    </div>
                                </>
                            )}
                            {error ? (
                                <>
                                    <UserChatMessage message={lastQuestionRef.current} />
                                    <div className={styles.chatMessageGptMinWidth}>
                                        <AnswerError error={error.toString()} onRetry={() => makeApiRequest(lastQuestionRef.current)} />
                                    </div>
                                </>
                            ) : null}
                            <div ref={chatMessageStreamEnd} />
                        </div>
                    )}

                    <div className={styles.chatInput}>
                        <QuestionInput
                            clearOnSend
                            placeholder="Type a new question (e.g. does my plan cover annual eye exams?)"
                            disabled={isLoading}
                            onSend={question => makeApiRequest(question)}
                        />
                    </div>
                </div>

                {answers.length > 0 && activeAnalysisPanelTab && (
                    <AnalysisPanel
                        className={styles.chatAnalysisPanel}
                        activeCitation={activeCitation}
                        onActiveTabChanged={x => onToggleTab(x, selectedAnswer)}
                        citationHeight="810px"
                        answer={answers[selectedAnswer][1]}
                        activeTab={activeAnalysisPanelTab}
                    />
                )}

                <Panel
                    headerText="Configure answer generation"
                    isOpen={isConfigPanelOpen}
                    isBlocking={false}
                    onDismiss={() => setIsConfigPanelOpen(false)}
                    closeButtonAriaLabel="Close"
                    onRenderFooterContent={() => <DefaultButton onClick={() => setIsConfigPanelOpen(false)}>Close</DefaultButton>}
                    isFooterAtBottom={true}
                >
                    <Checkbox
                        className={styles.chatSettingsSeparator}
                        checked={useAdvancedFlow}
                        label="Use advanced flow with query rewriting and filter formulation. Not compatible with Ollama models."
                        onChange={onUseAdvancedFlowChange}
                    />

                    <h3>Settings for database search:</h3>

                    <SpinButton
                        className={styles.chatSettingsSeparator}
                        label="Retrieve this many matching rows:"
                        min={1}
                        max={50}
                        defaultValue={retrieveCount.toString()}
                        onChange={onRetrieveCountChange}
                    />

                    <VectorSettings updateRetrievalMode={(retrievalMode: RetrievalMode) => setRetrievalMode(retrievalMode)} />

                    <h3>Settings for final chat completion:</h3>

                    <TextField
                        className={styles.chatSettingsSeparator}
                        defaultValue={promptTemplate}
                        label="Override prompt template"
                        multiline
                        autoAdjustHeight
                        onChange={onPromptTemplateChange}
                    />

                    <Slider
                        className={styles.chatSettingsSeparator}
                        label="Temperature"
                        min={0}
                        max={1}
                        step={0.1}
                        defaultValue={temperature}
                        onChange={onTemperatureChange}
                        showValue
                        snapToStep
                    />

                    <Checkbox
                        className={styles.chatSettingsSeparator}
                        checked={shouldStream}
                        label="Stream chat completion responses"
                        onChange={onShouldStreamChange}
                    />
                </Panel>
            </div>
        </div>
    );
};

export default Chat;
