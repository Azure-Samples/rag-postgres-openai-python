import { Example } from "./Example";

import styles from "./Example.module.css";

const DEFAULT_EXAMPLES: string[] = [
    "Best shoe for hiking?",
    "Climbing gear cheaper than $30?",
    "Waterproof camping gear?",
];

interface Props {
    onExampleClicked: (value: string) => void
}

export const ExampleList = ({ onExampleClicked }: Props) => {
    return (
        <ul className={styles.examplesNavList}>
            {DEFAULT_EXAMPLES.map((question, i) => (
                <li key={i}>
                    <Example text={question} value={question} onClick={onExampleClicked} />
                </li>
            ))}
        </ul>
    );
};
