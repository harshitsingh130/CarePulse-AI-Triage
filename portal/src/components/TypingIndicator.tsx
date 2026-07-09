/**
 * Animated typing indicator shown while AI is generating a response.
 */

interface TypingIndicatorProps {
  visible: boolean;
  actor?: 'ai' | 'nurse';
}

export function TypingIndicator({ visible, actor = 'ai' }: TypingIndicatorProps) {
  if (!visible) return null;

  const label = actor === 'nurse' ? 'Nurse is typing' : 'AI is thinking';

  return (
    <div className="chat-row chat-row--left" aria-live="polite" aria-label={label}>
      <div className="typing-indicator">
        <span className="typing-indicator__dot" />
        <span className="typing-indicator__dot" />
        <span className="typing-indicator__dot" />
      </div>
    </div>
  );
}
