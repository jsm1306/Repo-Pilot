import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

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

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <span key={index}>{part}</span>;
  });
}

export function MarkdownAnswer({ markdown }: { markdown: string }) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let paragraph: string[] = [];
  let list: string[] = [];
  let code: string[] = [];
  let inCode = false;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push(<p key={`p-${blocks.length}`}>{renderInline(paragraph.join(" "))}</p>);
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list.length) {
      blocks.push(<ul key={`ul-${blocks.length}`}>{list.map((item, index) => <li key={index}>{renderInline(item)}</li>)}</ul>);
      list = [];
    }
  };

  lines.forEach((line) => {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        blocks.push(<pre className="answer-code" key={`code-${blocks.length}`}><code>{code.join("\n")}</code></pre>);
        code = [];
      } else {
        flushParagraph();
        flushList();
      }
      inCode = !inCode;
      return;
    }
    if (inCode) {
      code.push(line);
      return;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push(<h3 key={`h-${blocks.length}`}>{renderInline(heading[2])}</h3>);
    } else if (/^\s*[-*]\s+/.test(line)) {
      flushParagraph();
      list.push(line.replace(/^\s*[-*]\s+/, ""));
    } else if (line.trim()) {
      paragraph.push(line.trim());
    } else {
      flushParagraph();
      flushList();
    }
  });
  flushParagraph();
  flushList();
  if (inCode && code.length) blocks.push(<pre className="answer-code" key={`code-${blocks.length}`}><code>{code.join("\n")}</code></pre>);
  return <div className="markdown-answer">{blocks}</div>;
}
