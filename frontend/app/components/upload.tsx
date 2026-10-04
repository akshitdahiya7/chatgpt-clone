"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Message = {
  role: "user" | "assistant";
  content: string;
};

const API_URL = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/chat`;
const STREAM_URL = `${API_URL}/stream`;

export default function Home() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const [model, setModel] = useState("gpt-4o-mini");
  const [topK, setTopK] = useState(5);
  const [temperature, setTemperature] = useState(0.2);
  const [topP, setTopP] = useState(0.9);
  const [maxTokens, setMaxTokens] = useState(512);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  // ============================================================
  // FILES
  // ============================================================

  const handleFiles = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const selectedFiles = Array.from(
      event.target.files || []
    );

    if (!selectedFiles.length) {
      return;
    }

    setFiles((current) => {
      const existing = new Set(
        current.map(
          (file) =>
            `${file.name}-${file.size}-${file.lastModified}`
        )
      );

      const uniqueFiles = selectedFiles.filter(
        (file) =>
          !existing.has(
            `${file.name}-${file.size}-${file.lastModified}`
          )
      );

      return [...current, ...uniqueFiles];
    });

    event.target.value = "";
  };

  const removeFile = (index: number) => {
    if (loading) {
      return;
    }

    setFiles((current) =>
      current.filter((_, fileIndex) => fileIndex !== index)
    );
  };

  const clearFiles = () => {
    if (loading) {
      return;
    }

    setFiles([]);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // ============================================================
  // CHAT
  // ============================================================

  const askQuestion = async () => {
    const trimmed = question.trim();

    if (!trimmed || loading) {
      return;
    }

    const requestFiles = [...files];

    setMessages((current) => [
      ...current,
      { role: "user", content: trimmed },
    ]);

    setLoading(true);
    setError(null);
    setStatus(
      requestFiles.length
        ? "Reading your documents..."
        : "Searching your documents..."
    );

    // Clear the composer straight away so the UI feels responsive.
    setQuestion("");
    setFiles([]);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    try {
      const formData = new FormData();

      formData.append("question", trimmed);
      formData.append("model", model);
      formData.append("top_k", String(topK));
      formData.append("temperature", String(temperature));
      formData.append("top_p", String(topP));
      formData.append("max_tokens", String(maxTokens));

      requestFiles.forEach((file) => {
        formData.append("files", file, file.name);
      });

      const response = await fetch(STREAM_URL, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(
          `The server returned ${response.status}. Please try again.`
        );
      }

      if (!response.body) {
        throw new Error("This browser cannot read streamed responses.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let answer = "";
      let started = false;

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        const piece = decoder.decode(value, { stream: true });

        if (!piece) {
          continue;
        }

        answer += piece;

        if (started) {
          // Replace the in-progress assistant message.
          setMessages((current) => {
            const next = [...current];
            next[next.length - 1] = {
              role: "assistant",
              content: answer,
            };
            return next;
          });
        } else {
          // Add the bubble only once text actually arrives, so a failure
          // never leaves an empty one behind.
          started = true;
          setStatus(null);
          setMessages((current) => [
            ...current,
            { role: "assistant", content: answer },
          ]);
        }
      }

      if (!answer.trim()) {
        setError("The assistant returned an empty response.");
      }
    } catch (err) {
      console.error("CHAT ERROR", err);

      const message =
        err instanceof TypeError
          ? "Unable to connect to the backend."
          : err instanceof Error
            ? err.message
            : "Request failed. Please try again.";

      setError(message);
    } finally {
      setLoading(false);
      setStatus(null);

      requestAnimationFrame(() => {
        textareaRef.current?.focus();
      });
    }
  };

  // ============================================================
  // KEYBOARD
  // ============================================================

  const handleKeyDown = (
    event: React.KeyboardEvent<HTMLTextAreaElement>
  ) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      askQuestion();
    }
  };

  // ============================================================
  // HELPERS
  // ============================================================

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) {
      return `${bytes} B`;
    }

    if (bytes < 1024 * 1024) {
      return `${(
        bytes / 1024
      ).toFixed(1)} KB`;
    }

    if (bytes < 1024 * 1024 * 1024) {
      return `${(
        bytes /
        (1024 * 1024)
      ).toFixed(1)} MB`;
    }

    return `${(
      bytes /
      (1024 * 1024 * 1024)
    ).toFixed(1)} GB`;
  };

  const getFileLabel = (file: File) => {
    const extension =
      file.name
        .split(".")
        .pop()
        ?.toUpperCase() || "FILE";

    return extension.length <= 4
      ? extension
      : "FILE";
  };

  // ============================================================
  // UI
  // ============================================================

  return (
    <main className="flex h-screen flex-col bg-[#f7f7f8] text-gray-900">

      {/* HEADER */}
      <header className="shrink-0 border-b bg-white">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between px-4">

          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-black text-sm text-white">
              ✦
            </div>

            <div>
              <h1 className="text-sm font-semibold">
                RAG Assistant
              </h1>

              <p className="text-[11px] text-gray-400">
                Document Intelligence
              </p>
            </div>
          </div>

          <div className="rounded-md border bg-gray-50 px-2.5 py-1 text-[11px] text-gray-500">
            {model}
          </div>

        </div>
      </header>

      {/* CONFIGURATION */}
      <section className="shrink-0 border-b bg-white">
        <div className="mx-auto w-full max-w-5xl px-4 py-2.5">

          <div className="flex flex-wrap items-end gap-2">

            <ConfigSelect
              label="Model"
              value={model}
              onChange={setModel}
              disabled={loading}
              options={[
                ["gpt-4o-mini", "GPT-4o mini · fast"],
                ["gpt-4o", "GPT-4o · best"],
                ["gpt-4.1-mini", "GPT-4.1 mini"],
              ]}
            />

            <ConfigSelect
              label="Top K"
              value={String(topK)}
              onChange={(value) =>
                setTopK(Number(value))
              }
              disabled={loading}
              options={[
                ["3", "3 chunks"],
                ["5", "5 chunks"],
                ["10", "10 chunks"],
                ["20", "20 chunks"],
              ]}
            />

            <ConfigSelect
              label="Temperature"
              value={String(temperature)}
              onChange={(value) =>
                setTemperature(Number(value))
              }
              disabled={loading}
              options={[
                ["0.1", "0.1 · Precise"],
                ["0.2", "0.2 · Focused"],
                ["0.5", "0.5 · Balanced"],
                ["0.7", "0.7 · Creative"],
                ["1", "1.0 · Random"],
              ]}
            />

            <ConfigSelect
              label="Top P"
              value={String(topP)}
              onChange={(value) =>
                setTopP(Number(value))
              }
              disabled={loading}
              options={[
                ["0.7", "0.7"],
                ["0.9", "0.9"],
                ["0.95", "0.95"],
                ["1", "1.0"],
              ]}
            />

            <ConfigSelect
              label="Max Tokens"
              value={String(maxTokens)}
              onChange={(value) =>
                setMaxTokens(Number(value))
              }
              disabled={loading}
              options={[
                ["256", "256"],
                ["512", "512"],
                ["1024", "1024"],
                ["2048", "2048"],
              ]}
            />

          </div>
        </div>
      </section>

      {/* CHAT */}
      <section className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-8">

          {messages.length === 0 ? (

            <div className="flex min-h-[55vh] items-center justify-center">

              <div className="text-center">

                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-black text-white">
                  ✦
                </div>

                <h2 className="text-2xl font-semibold tracking-tight">
                  Ask anything
                </h2>

                <p className="mt-2 text-sm text-gray-500">
                  Ask questions about your documents.
                </p>

              </div>

            </div>

          ) : (

            <div className="space-y-8">

              {messages.map(
                (message, index) => {

                  // USER MESSAGE
                  if (
                    message.role === "user"
                  ) {
                    return (
                      <div
                        key={index}
                        className="flex justify-end"
                      >
                        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-black px-5 py-3 text-sm leading-6 text-white">
                          <div className="whitespace-pre-wrap">
                            {message.content}
                          </div>
                        </div>
                      </div>
                    );
                  }

                  // ASSISTANT MESSAGE
                  return (
                    <div
                      key={index}
                      className="flex items-start gap-3"
                    >

                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-black text-xs text-white">
                        ✦
                      </div>

                      <div className="min-w-0 max-w-[85%]">

                        <div className="rounded-2xl rounded-tl-sm border bg-white px-5 py-4 shadow-sm">

                          <div className="text-sm leading-6 text-gray-700">

                            <ReactMarkdown
                              remarkPlugins={[
                                remarkGfm,
                              ]}
                              components={{
                                h1: ({
                                  children,
                                }) => (
                                  <h1 className="mb-3 text-xl font-semibold text-gray-900">
                                    {children}
                                  </h1>
                                ),

                                h2: ({
                                  children,
                                }) => (
                                  <h2 className="mb-3 mt-5 text-lg font-semibold text-gray-900">
                                    {children}
                                  </h2>
                                ),

                                h3: ({
                                  children,
                                }) => (
                                  <h3 className="mb-2 mt-4 text-base font-semibold text-gray-900">
                                    {children}
                                  </h3>
                                ),

                                p: ({
                                  children,
                                }) => (
                                  <p className="mb-3 last:mb-0">
                                    {children}
                                  </p>
                                ),

                                ul: ({
                                  children,
                                }) => (
                                  <ul className="mb-3 ml-5 list-disc space-y-1">
                                    {children}
                                  </ul>
                                ),

                                ol: ({
                                  children,
                                }) => (
                                  <ol className="mb-3 ml-5 list-decimal space-y-1">
                                    {children}
                                  </ol>
                                ),

                                li: ({
                                  children,
                                }) => (
                                  <li className="pl-1">
                                    {children}
                                  </li>
                                ),

                                strong: ({
                                  children,
                                }) => (
                                  <strong className="font-semibold text-gray-900">
                                    {children}
                                  </strong>
                                ),

                                blockquote: ({
                                  children,
                                }) => (
                                  <blockquote className="my-3 border-l-4 border-gray-300 pl-4 text-gray-500">
                                    {children}
                                  </blockquote>
                                ),

                                code: ({
                                  children,
                                }) => (
                                  <code className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[12px] text-gray-800">
                                    {children}
                                  </code>
                                ),

                                pre: ({
                                  children,
                                }) => (
                                  <pre className="my-4 overflow-x-auto rounded-xl bg-gray-950 p-4 text-xs text-gray-100">
                                    {children}
                                  </pre>
                                ),

                                hr: () => (
                                  <hr className="my-4 border-gray-200" />
                                ),

                                table: ({
                                  children,
                                }) => (
                                  <div className="my-4 overflow-x-auto">
                                    <table className="min-w-full border-collapse text-xs">
                                      {children}
                                    </table>
                                  </div>
                                ),

                                th: ({
                                  children,
                                }) => (
                                  <th className="border border-gray-200 bg-gray-50 px-3 py-2 text-left font-semibold">
                                    {children}
                                  </th>
                                ),

                                td: ({
                                  children,
                                }) => (
                                  <td className="border border-gray-200 px-3 py-2">
                                    {children}
                                  </td>
                                ),
                              }}
                            >
                              {message.content}
                            </ReactMarkdown>

                          </div>

                        </div>

                      </div>

                    </div>
                  );
                }
              )}

              {/* LOADING */}

              {loading && status && (
                <div className="flex items-start gap-3">

                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-black text-xs text-white">
                    ✦
                  </div>

                  <div className="rounded-2xl rounded-tl-sm border bg-white px-5 py-4 shadow-sm">

                    <div className="flex items-center gap-2.5">

                      <div className="flex items-center gap-1.5">

                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" />

                      <span
                        className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
                        style={{
                          animationDelay:
                            "150ms",
                        }}
                      />

                      <span
                        className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
                        style={{
                          animationDelay:
                            "300ms",
                        }}
                      />

                      </div>

                      {status && (
                        <span className="text-xs text-gray-400">
                          {status}
                        </span>
                      )}

                    </div>

                  </div>

                </div>
              )}

              <div ref={messagesEndRef} />

            </div>
          )}

        </div>
      </section>

      {/* COMPOSER */}
      <section className="shrink-0 border-t bg-white">

        <div className="mx-auto w-full max-w-3xl px-4 py-3">

          {/* ERROR */}

          {error && (
            <div className="mb-3 flex items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-700">

              <span>{error}</span>

              <button
                type="button"
                onClick={() => setError(null)}
                className="text-red-400 hover:text-red-700"
              >
                ×
              </button>

            </div>
          )}

          {/* FILES */}

          {files.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2">

              {files.map(
                (file, index) => (

                  <div
                    key={`${file.name}-${file.size}-${index}`}
                    className="flex max-w-[270px] items-center gap-2 rounded-lg border bg-gray-50 px-2.5 py-1.5"
                  >

                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-white text-[8px] font-semibold text-gray-500">
                      {getFileLabel(file)}
                    </div>

                    <div className="min-w-0 flex-1">

                      <p className="truncate text-[11px] font-medium text-gray-700">
                        {file.name}
                      </p>

                      <p className="text-[9px] text-gray-400">
                        {formatFileSize(file.size)}
                      </p>

                    </div>

                    <button
                      type="button"
                      onClick={() =>
                        removeFile(index)
                      }
                      disabled={loading}
                      className="text-gray-400 hover:text-black disabled:opacity-30"
                    >
                      ×
                    </button>

                  </div>
                )
              )}

              {files.length > 1 && (
                <button
                  type="button"
                  onClick={clearFiles}
                  disabled={loading}
                  className="px-1 text-[10px] text-gray-400 hover:text-gray-700"
                >
                  Clear all
                </button>
              )}

            </div>
          )}

          {/* INPUT */}

          <div className="flex items-end gap-2 rounded-xl border bg-gray-50 p-1.5 shadow-sm transition focus-within:border-gray-300 focus-within:bg-white">

            <button
              type="button"
              onClick={() =>
                fileInputRef.current?.click()
              }
              disabled={loading}
              title="Attach documents"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-900 disabled:opacity-30"
            >
              📎
            </button>

            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              accept=".pdf,.txt,.doc,.docx,.md"
              onChange={handleFiles}
            />

            <textarea
              ref={textareaRef}
              value={question}
              onChange={(event) =>
                setQuestion(event.target.value)
              }
              onKeyDown={handleKeyDown}
              disabled={loading}
              rows={1}
              placeholder={
                files.length > 0
                  ? "Ask something about these documents..."
                  : "Ask a question..."
              }
              className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-2 py-2.5 text-sm outline-none placeholder:text-gray-400"
            />

            <button
              type="button"
              onClick={askQuestion}
              disabled={
                !question.trim() || loading
              }
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-black text-sm text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:bg-gray-300"
            >
              {loading ? "…" : "↑"}
            </button>

          </div>

          <div className="mt-1.5 flex justify-between px-1 text-[10px] text-gray-400">

            <span>
              Enter to send · Shift + Enter for new line
            </span>

            <span>
              {files.length > 0
                ? `${files.length} attached`
                : "No documents"}
            </span>

          </div>

        </div>
      </section>

    </main>
  );
}

// ============================================================
// CONFIG SELECT
// ============================================================

type ConfigSelectProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  options: [string, string][];
};

function ConfigSelect({
  label,
  value,
  onChange,
  disabled,
  options,
}: ConfigSelectProps) {
  return (
    <div className="min-w-[130px] flex-1">

      <label className="mb-1 block text-[9px] font-semibold uppercase tracking-wide text-gray-400">
        {label}
      </label>

      <select
        value={value}
        onChange={(event) =>
          onChange(event.target.value)
        }
        disabled={disabled}
        className="w-full rounded-lg border bg-white px-2.5 py-2 text-xs outline-none transition hover:border-gray-300 focus:border-gray-500 disabled:cursor-not-allowed disabled:bg-gray-50"
      >
        {options.map(
          ([optionValue, optionLabel]) => (
            <option
              key={optionValue}
              value={optionValue}
            >
              {optionLabel}
            </option>
          )
        )}
      </select>

    </div>
  );
}