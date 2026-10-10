import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

export interface AnswerMarkdownProps {
  text: string;
}

export function AnswerMarkdown({ text }: AnswerMarkdownProps): JSX.Element {
  return (
    <div className="md-body">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
