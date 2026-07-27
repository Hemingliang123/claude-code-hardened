import React, { useMemo, useState } from 'react';

type Role = 'assistant' | 'user';

type Message = {
  id: string;
  role: Role;
  content: string;
  timestamp: string;
};

type Conversation = {
  id: string;
  title: string;
  summary: string;
  updatedAt: string;
  messages: Message[];
};

const starterConversations: Conversation[] = [
  {
    id: 'conv-product',
    title: 'Landing page strategy',
    summary: 'Hero section, product proof, CTA copy',
    updatedAt: '2m ago',
    messages: [
      {
        id: 'm-1',
        role: 'assistant',
        content:
          'Ready when you are. I can help design the page structure, write the copy, and shape a launch-ready visual direction.',
        timestamp: '09:41',
      },
      {
        id: 'm-2',
        role: 'user',
        content: 'Build me a cleaner SaaS landing page with a premium feel.',
        timestamp: '09:42',
      },
      {
        id: 'm-3',
        role: 'assistant',
        content:
          'Start with a restrained dark palette, a strong headline, compact trust signals, and a focused CTA. I can also draft the full page section-by-section.',
        timestamp: '09:42',
      },
    ],
  },
  {
    id: 'conv-research',
    title: 'Market research notes',
    summary: 'Competitors, positioning, pricing tiers',
    updatedAt: '18m ago',
    messages: [
      {
        id: 'm-4',
        role: 'user',
        content: 'Summarize the top three trends in AI productivity tools.',
        timestamp: '08:57',
      },
      {
        id: 'm-5',
        role: 'assistant',
        content:
          'The biggest trends are workflow consolidation, chat-to-action product patterns, and increased emphasis on trust, permissions, and enterprise controls.',
        timestamp: '08:58',
      },
    ],
  },
];

const suggestedPrompts = [
  'Design a pricing page for an AI tool',
  'Rewrite my hero section to sound more premium',
  'Map a chatbot onboarding flow',
  'Turn product notes into launch copy',
];

function makeId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function createEmptyConversation(): Conversation {
  return {
    id: makeId('conv'),
    title: 'New chat',
    summary: 'Fresh conversation',
    updatedAt: 'now',
    messages: [],
  };
}

function buildAssistantReply(input: string): string {
  const compact = input.trim();

  if (!compact) {
    return 'Send a prompt and I will help you shape it into a stronger answer, feature list, or page direction.';
  }

  return `Here is a stronger next step for "${compact}": define the outcome, break it into three focused sections, and ship the clearest version first. If you want, I can now turn this into UI copy, a component structure, or an implementation plan.`;
}

export function ChatGptStylePage(): React.ReactNode {
  const [conversations, setConversations] = useState<Conversation[]>(starterConversations);
  const [activeId, setActiveId] = useState<string>(starterConversations[0]?.id ?? '');
  const [draft, setDraft] = useState('');

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) ?? conversations[0],
    [activeId, conversations],
  );

  const createConversation = (): void => {
    const nextConversation = createEmptyConversation();
    setConversations((current) => [nextConversation, ...current]);
    setActiveId(nextConversation.id);
    setDraft('');
  };

  const sendMessage = (preset?: string): void => {
    const content = (preset ?? draft).trim();
    if (!content || !activeConversation) {
      return;
    }

    const userMessage: Message = {
      id: makeId('msg'),
      role: 'user',
      content,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const assistantMessage: Message = {
      id: makeId('msg'),
      role: 'assistant',
      content: buildAssistantReply(content),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setConversations((current) =>
      current.map((conversation) => {
        if (conversation.id !== activeConversation.id) {
          return conversation;
        }

        const nextTitle =
          conversation.messages.length === 0
            ? content.slice(0, 28) + (content.length > 28 ? '...' : '')
            : conversation.title;

        return {
          ...conversation,
          title: nextTitle || 'New chat',
          summary: assistantMessage.content.slice(0, 54) + (assistantMessage.content.length > 54 ? '...' : ''),
          updatedAt: 'now',
          messages: [...conversation.messages, userMessage, assistantMessage],
        };
      }),
    );

    setDraft('');
  };

  const handleComposerKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      <style>{pageStyles}</style>
      <div className="chat-shell">
        <aside className="chat-sidebar">
          <div className="brand-block">
            <div className="brand-mark">AI</div>
            <div>
              <p className="eyebrow">Workspace</p>
              <h1>Nova Chat</h1>
            </div>
          </div>

          <button type="button" className="new-chat-button" onClick={createConversation}>
            <span>+</span>
            New chat
          </button>

          <div className="sidebar-section">
            <p className="section-label">Recent</p>
            <div className="conversation-list">
              {conversations.map((conversation) => {
                const isActive = conversation.id === activeConversation?.id;
                return (
                  <button
                    type="button"
                    key={conversation.id}
                    className={`conversation-card${isActive ? ' active' : ''}`}
                    onClick={() => setActiveId(conversation.id)}
                  >
                    <div className="conversation-title-row">
                      <strong>{conversation.title}</strong>
                      <span>{conversation.updatedAt}</span>
                    </div>
                    <p>{conversation.summary}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="sidebar-footer">
            <div className="status-dot" />
            <div>
              <strong>Pro workspace</strong>
              <p>Ready for API integration</p>
            </div>
          </div>
        </aside>

        <main className="chat-main">
          <header className="topbar">
            <div>
              <p className="eyebrow">Model</p>
              <h2>Nova GPT 4.1</h2>
            </div>
            <div className="topbar-actions">
              <button type="button" className="ghost-button">
                Share
              </button>
              <button type="button" className="ghost-button">
                Settings
              </button>
            </div>
          </header>

          <section className="chat-stage">
            {activeConversation?.messages.length ? (
              <div className="messages">
                {activeConversation.messages.map((message) => (
                  <article key={message.id} className={`message-row ${message.role}`}>
                    <div className="avatar">{message.role === 'assistant' ? 'N' : 'U'}</div>
                    <div className="message-bubble">
                      <p>{message.content}</p>
                      <span>{message.timestamp}</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <p className="eyebrow">Start Here</p>
                <h3>Ask for a page, a plan, or sharper product copy.</h3>
                <p>
                  This page is a self-contained React mockup of a ChatGPT-style interface with conversations,
                  message bubbles, and a working composer.
                </p>
                <div className="prompt-grid">
                  {suggestedPrompts.map((prompt) => (
                    <button type="button" key={prompt} className="prompt-card" onClick={() => sendMessage(prompt)}>
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </section>

          <footer className="composer-wrap">
            <div className="composer">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder="Message Nova Chat..."
                rows={1}
              />
              <button type="button" className="send-button" onClick={() => sendMessage()}>
                Send
              </button>
            </div>
            <p className="composer-hint">Press Enter to send, Shift + Enter for a new line.</p>
          </footer>
        </main>
      </div>
    </>
  );
}

const pageStyles = `
  :root {
    color-scheme: dark;
    --bg: #0b1020;
    --panel: rgba(12, 18, 36, 0.86);
    --panel-strong: rgba(19, 27, 51, 0.98);
    --line: rgba(255, 255, 255, 0.08);
    --line-strong: rgba(130, 160, 255, 0.22);
    --text: #ecf2ff;
    --muted: #92a0bd;
    --accent: #7c9cff;
    --accent-strong: #9bb2ff;
    --assistant: rgba(126, 156, 255, 0.14);
    --user: rgba(255, 255, 255, 0.07);
    --shadow: 0 28px 80px rgba(0, 0, 0, 0.34);
    --radius-xl: 28px;
    --radius-lg: 20px;
    --radius-md: 16px;
  }

  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    font-family: "Segoe UI", "Helvetica Neue", sans-serif;
    background:
      radial-gradient(circle at top left, rgba(124, 156, 255, 0.22), transparent 28%),
      radial-gradient(circle at right center, rgba(94, 233, 197, 0.12), transparent 18%),
      linear-gradient(180deg, #09101f 0%, #060912 100%);
    color: var(--text);
  }

  button,
  textarea {
    font: inherit;
  }

  .chat-shell {
    min-height: 100vh;
    display: grid;
    grid-template-columns: 320px 1fr;
    gap: 18px;
    padding: 18px;
    background-image:
      linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
    background-size: 32px 32px;
  }

  .chat-sidebar,
  .chat-main {
    border: 1px solid var(--line);
    background: var(--panel);
    backdrop-filter: blur(24px);
    box-shadow: var(--shadow);
  }

  .chat-sidebar {
    border-radius: var(--radius-xl);
    padding: 22px;
    display: flex;
    flex-direction: column;
    gap: 22px;
  }

  .brand-block {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .brand-block h1,
  .topbar h2,
  .empty-state h3,
  .conversation-title-row strong {
    margin: 0;
  }

  .brand-mark {
    width: 48px;
    height: 48px;
    display: grid;
    place-items: center;
    border-radius: 16px;
    color: #081120;
    font-weight: 800;
    background: linear-gradient(135deg, #d8e3ff 0%, #83a0ff 100%);
  }

  .eyebrow,
  .section-label,
  .composer-hint,
  .conversation-title-row span,
  .message-bubble span,
  .sidebar-footer p,
  .empty-state p {
    margin: 0;
    color: var(--muted);
  }

  .eyebrow,
  .section-label {
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 11px;
  }

  .new-chat-button,
  .ghost-button,
  .prompt-card,
  .send-button,
  .conversation-card {
    border: 1px solid transparent;
    cursor: pointer;
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      background 160ms ease;
  }

  .new-chat-button:hover,
  .ghost-button:hover,
  .prompt-card:hover,
  .send-button:hover,
  .conversation-card:hover {
    transform: translateY(-1px);
  }

  .new-chat-button {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    border-radius: 18px;
    padding: 14px 16px;
    color: var(--text);
    background: linear-gradient(135deg, rgba(117, 146, 255, 0.22), rgba(117, 146, 255, 0.08));
    border-color: var(--line-strong);
  }

  .sidebar-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
    flex: 1;
  }

  .conversation-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow: auto;
  }

  .conversation-card {
    width: 100%;
    text-align: left;
    padding: 14px;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.03);
    border-color: var(--line);
  }

  .conversation-card.active {
    background: rgba(124, 156, 255, 0.12);
    border-color: var(--line-strong);
  }

  .conversation-title-row {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 8px;
  }

  .conversation-card p {
    margin: 0;
    color: var(--muted);
    line-height: 1.5;
  }

  .sidebar-footer {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--line);
  }

  .status-dot {
    width: 12px;
    height: 12px;
    border-radius: 999px;
    background: #5ee9c5;
    box-shadow: 0 0 18px rgba(94, 233, 197, 0.8);
  }

  .chat-main {
    border-radius: 32px;
    padding: 22px;
    display: grid;
    grid-template-rows: auto 1fr auto;
    gap: 18px;
    min-height: calc(100vh - 36px);
  }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 4px 4px 0;
  }

  .topbar-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .ghost-button {
    border-radius: 14px;
    padding: 10px 14px;
    color: var(--text);
    background: rgba(255, 255, 255, 0.04);
    border-color: var(--line);
  }

  .chat-stage {
    min-height: 0;
    overflow: auto;
    border-radius: 28px;
    padding: 14px 8px;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0)),
      rgba(6, 10, 20, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.04);
  }

  .messages {
    display: flex;
    flex-direction: column;
    gap: 18px;
    padding: 10px;
  }

  .message-row {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    max-width: 860px;
  }

  .message-row.user {
    margin-left: auto;
    flex-direction: row-reverse;
  }

  .avatar {
    width: 38px;
    height: 38px;
    border-radius: 14px;
    display: grid;
    place-items: center;
    font-size: 13px;
    font-weight: 700;
    flex: 0 0 auto;
    background: var(--panel-strong);
    border: 1px solid var(--line);
  }

  .message-bubble {
    max-width: min(100%, 720px);
    padding: 16px 18px;
    border-radius: 22px;
    border: 1px solid var(--line);
    background: var(--assistant);
  }

  .message-row.user .message-bubble {
    background: var(--user);
  }

  .message-bubble p {
    margin: 0 0 10px;
    line-height: 1.7;
    white-space: pre-wrap;
  }

  .empty-state {
    min-height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 56px 20px;
  }

  .empty-state h3 {
    font-size: clamp(34px, 4vw, 56px);
    max-width: 780px;
    line-height: 1.02;
    margin-top: 10px;
  }

  .empty-state p {
    max-width: 680px;
    line-height: 1.7;
    margin-top: 14px;
  }

  .prompt-grid {
    width: 100%;
    max-width: 900px;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
    margin-top: 28px;
  }

  .prompt-card {
    text-align: left;
    border-radius: 22px;
    padding: 18px;
    color: var(--text);
    background: rgba(255, 255, 255, 0.04);
    border-color: var(--line);
  }

  .composer-wrap {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .composer {
    display: flex;
    align-items: flex-end;
    gap: 12px;
    padding: 14px;
    border-radius: 26px;
    background: rgba(10, 16, 30, 0.9);
    border: 1px solid var(--line);
  }

  .composer textarea {
    width: 100%;
    resize: none;
    min-height: 28px;
    max-height: 180px;
    color: var(--text);
    background: transparent;
    border: 0;
    outline: none;
    line-height: 1.6;
  }

  .composer textarea::placeholder {
    color: var(--muted);
  }

  .send-button {
    border-radius: 18px;
    padding: 12px 18px;
    color: #07101e;
    font-weight: 700;
    background: linear-gradient(135deg, #d8e3ff 0%, #89a4ff 100%);
  }

  @media (max-width: 980px) {
    .chat-shell {
      grid-template-columns: 1fr;
    }

    .chat-sidebar {
      order: 2;
    }

    .chat-main {
      min-height: auto;
      order: 1;
    }
  }

  @media (max-width: 720px) {
    .chat-shell {
      padding: 10px;
      gap: 10px;
    }

    .chat-sidebar,
    .chat-main {
      border-radius: 24px;
      padding: 16px;
    }

    .topbar {
      align-items: flex-start;
      flex-direction: column;
    }

    .topbar-actions,
    .prompt-grid {
      width: 100%;
      grid-template-columns: 1fr;
    }

    .message-row,
    .message-row.user {
      margin-left: 0;
      flex-direction: row;
    }

    .message-bubble {
      max-width: 100%;
    }

    .composer {
      flex-direction: column;
      align-items: stretch;
    }
  }
`;

export default ChatGptStylePage;
