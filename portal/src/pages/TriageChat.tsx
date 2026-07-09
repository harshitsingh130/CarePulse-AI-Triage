/**
 * Triage Chat Page — the core patient experience.
 * Real-time conversational interface with WebSocket communication.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ChatBubble } from '@/components/ChatBubble';
import { EmergencyBanner } from '@/components/EmergencyBanner';
import { SeveritySlider } from '@/components/SeveritySlider';
import { TypingIndicator } from '@/components/TypingIndicator';
import { useWebSocket } from '@/hooks/useWebSocket';
import { authService } from '@/services/auth';

export function TriageChat() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authService.isAuthenticated()) {
      navigate('/auth');
    }
  }, [navigate]);

  const [inputText, setInputText] = useState('');
  const [waitingForAI, setWaitingForAI] = useState(false);
  const [showSlider, setShowSlider] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const greetingShown = useRef(false);

  const {
    messages,
    connected,
    reconnecting,
    sendMessage,
    sessionComplete,
    emergencyAlert,
  } = useWebSocket(sessionId || null);

  // Show greeting message when connected
  useEffect(() => {
    if (connected && !greetingShown.current) {
      greetingShown.current = true;
    }
  }, [connected]);

  // Auto-retry new session up to 3 times when connection is fully lost
  const retryCount = useRef(0);
  const maxRetries = 3;

  useEffect(() => {
    if (!connected && !reconnecting && !sessionComplete && retryCount.current < maxRetries) {
      const timer = setTimeout(async () => {
        retryCount.current += 1;
        try {
          const { startTriage } = await import('@/services/api');
          const { session_id } = await startTriage();
          navigate(`/triage/${session_id}`);
          window.location.reload();
        } catch (e) {
          // Will retry on next render cycle if still disconnected
        }
      }, 2000 * retryCount.current + 2000);
      return () => clearTimeout(timer);
    }
  }, [connected, reconnecting, sessionComplete, navigate]);

  const handleNewSession = useCallback(async () => {
    try {
      const { startTriage } = await import('@/services/api');
      const { session_id } = await startTriage();
      navigate(`/triage/${session_id}`);
      window.location.reload();
    } catch (e) {
      navigate('/');
    }
  }, [navigate]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Track AI responding state
  useEffect(() => {
    if (messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      setWaitingForAI(lastMsg.role === 'patient');

      // Show severity slider if AI requested it
      if (lastMsg.showSeveritySlider) {
        setShowSlider(true);
      }
    }
  }, [messages]);

  // Redirect on completion
  useEffect(() => {
    if (sessionComplete && sessionId) {
      setTimeout(() => navigate(`/triage/${sessionId}/status`), 2000);
    }
  }, [sessionComplete, sessionId, navigate]);

  const handleSend = useCallback(() => {
    if (!inputText.trim() || waitingForAI) return;
    sendMessage(inputText.trim());
    setInputText('');
    setWaitingForAI(true);
    setShowSlider(false);
  }, [inputText, sendMessage, waitingForAI]);

  const handleSeveritySelect = useCallback((value: number) => {
    sendMessage(String(value));
    setShowSlider(false);
    setWaitingForAI(true);
  }, [sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="triage-chat">
      <header className="triage-chat__header">
        <h1>{messages.find(m => m.role === 'patient')?.content.slice(0, 50) || 'Triage Chat'}{messages.find(m => m.role === 'patient')?.content && messages.find(m => m.role === 'patient')!.content.length > 50 ? '…' : ''}</h1>
        <div className="triage-chat__header-actions">
          <button className="btn btn--secondary btn--sm" onClick={handleNewSession}>
            New Session
          </button>
          {reconnecting && (
            <span className="connection-status connection-status--reconnecting" role="status">
              Reconnecting...
            </span>
          )}
          {!connected && !reconnecting && (
            <span className="connection-status connection-status--disconnected" role="alert">
              Connection lost
            </span>
          )}
        </div>
      </header>

      <EmergencyBanner
        visible={emergencyAlert}
        onConnect={() => { /* Live transfer logic */ }}
        onDismiss={() => { /* Dismiss */ }}
      />

      <main className="triage-chat__messages" role="log" aria-label="Chat messages" aria-live="polite">
        {messages.map((msg) => (
          <ChatBubble key={msg.id} message={msg} />
        ))}
        <TypingIndicator visible={waitingForAI && messages.length > 0 && !sessionComplete} />
        {showSlider && <SeveritySlider onSelect={handleSeveritySelect} />}
        <div ref={messagesEndRef} />
      </main>

      {!sessionComplete && (
        <footer className="triage-chat__input">
          <label htmlFor="chat-input" className="sr-only">Type your message</label>
          <textarea
            id="chat-input"
            className="chat-input__textarea"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={waitingForAI ? 'Waiting for response...' : 'Type your message...'}
            disabled={waitingForAI || !connected}
            maxLength={1000}
            rows={1}
            aria-label="Chat message input"
          />
          <button
            className="chat-input__send-btn"
            onClick={handleSend}
            disabled={!inputText.trim() || waitingForAI || !connected}
            aria-label="Send message"
          >
            Send
          </button>
        </footer>
      )}

      {sessionComplete && (
        <footer className="triage-chat__complete">
          <p>Your triage is complete. Redirecting to your results...</p>
        </footer>
      )}
    </div>
  );
}
