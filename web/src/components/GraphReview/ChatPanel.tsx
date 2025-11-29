import React, { useRef, useEffect } from 'react';
import { Message } from '../../types/graph';
import { QuickActions } from './QuickActions';

interface ChatPanelProps {
  messages: Message[];
  inputValue: string;
  agentThinking: boolean;
  onInputChange: (value: string) => void;
  onSendMessage: (content: string) => void;
  onQuickAction: (prompt: string) => void;
}

export function ChatPanel({
  messages,
  inputValue,
  agentThinking,
  onInputChange,
  onSendMessage,
  onQuickAction,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim() && !agentThinking) {
      onSendMessage(inputValue);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-full bg-dark">
      {/* Quick Actions */}
      <QuickActions
        onSelectAction={(prompt) => {
          onInputChange(prompt);
        }}
        disabled={agentThinking}
      />

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg p-3 ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : message.role === 'system'
                  ? 'bg-dark-panel/50 text-text-muted italic text-sm'
                  : 'bg-dark-panel text-text-main'
              }`}
            >
              <div className="whitespace-pre-wrap break-words">{message.content}</div>
              {message.timestamp && (
                <div className="text-xs opacity-70 mt-1">{message.timestamp}</div>
              )}
            </div>
          </div>
        ))}

        {agentThinking && (
          <div className="flex justify-start">
            <div className="bg-dark-panel text-text-main rounded-lg p-3">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </div>
                <span className="text-sm text-text-muted">Agent thinking...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-dark-border">
        <div className="flex gap-2">
          <textarea
            value={inputValue}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask the agent or give instructions…"
            disabled={agentThinking}
            rows={2}
            className="flex-1 px-3 py-2 bg-dark-panel text-text-main border border-dark-border rounded resize-none focus:border-blue-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || agentThinking}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium disabled:opacity-50 disabled:cursor-not-allowed self-end"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
