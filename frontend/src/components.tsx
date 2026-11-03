import { Children, isValidElement, useEffect, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  children: ReactNode;
};

export function Button({ variant = "secondary", children, className = "", ...props }: ButtonProps) {
  return (
    <button className={`button button-${variant} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Panel({
  children,
  className = "",
  title,
  action,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  action?: ReactNode;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="panel-heading">
          <h2>{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatusBadge({
  tone,
  children,
}: {
  tone: "success" | "warning" | "danger" | "evidence" | "neutral";
  children: ReactNode;
}) {
  return (
    <span className={`status status-${tone}`}>
      <span className="status-dot" aria-hidden="true" />
      {children}
    </span>
  );
}

export function Alert({
  tone,
  title,
  children,
}: {
  tone: "success" | "warning" | "danger";
  title: string;
  children: ReactNode;
}) {
  return (
    <div className={`alert alert-${tone}`} role="status">
      <span className="alert-mark" aria-hidden="true">
        {tone === "success" ? "OK" : tone === "warning" ? "!" : "X"}
      </span>
      <div>
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
    </div>
  );
}

export function TextInput({
  label,
  hint,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <input {...props} />
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function TextArea({
  label,
  hint,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; hint?: string }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <textarea {...props} />
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function CodeLine({ number, children, changed }: { number: number; children: ReactNode; changed?: "add" | "remove" }) {
  return (
    <div className={`code-line ${changed ? `code-${changed}` : ""}`}>
      <span className="line-number">{number}</span>
      <code>{children}</code>
    </div>
  );
}

export function MarkdownAnswer({ markdown }: { markdown: string }) {
  function getCodeText(children: ReactNode): string {
    const child = Children.toArray(children)[0];
    if (isValidElement<{ children?: ReactNode }>(child)) {
      return String(child.props.children ?? "").replace(/\n$/, "");
    }
    return String(children).replace(/\n$/, "");
  }

  return (
    <div className="markdown-answer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            return <code className={className} {...props}>{children}</code>;
          },
          pre({ children }) {
            const codeText = getCodeText(children);
            return (
              <div className="answer-code-wrap">
                <CopyCodeButton code={codeText} />
                <pre className="answer-code">{children}</pre>
              </div>
            );
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}

export function AnimatedMarkdownAnswer({ markdown }: { markdown: string }) {
  const [displayed, setDisplayed] = useState(() => (
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? markdown
      : ""
  ));
  const [isComplete, setIsComplete] = useState(displayed === markdown);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setDisplayed(markdown);
      setIsComplete(true);
      return;
    }

    setDisplayed("");
    setIsComplete(false);
    let position = 0;
    let timer: number | undefined;
    const reveal = () => {
      position = Math.min(markdown.length, position + 2);
      setDisplayed(markdown.slice(0, position));
      if (position < markdown.length) {
        timer = window.setTimeout(reveal, 16);
      } else {
        setIsComplete(true);
      }
    };
    timer = window.setTimeout(reveal, 40);
    return () => {
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [markdown]);

  return (
    <div className="answer-generation" aria-busy={!isComplete}>
      <MarkdownAnswer markdown={displayed} />
      {!isComplete && <span className="answer-caret" aria-hidden="true" />}
    </div>
  );
}

function CopyCodeButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  async function copyCode() {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return <button className="copy-code" type="button" onClick={copyCode}>{copied ? "Copied" : "Copy"}</button>;
}
