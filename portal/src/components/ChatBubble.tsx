/**
 * Chat message bubble component.
 * Left-aligned for AI/nurse/system, right-aligned for patient.
 * Supports basic markdown: **bold**, *italic*, and newlines.
 */

import type { ChatMessage } from '@/types';

interface ChatBubbleProps {
  message: ChatMessage;
}

function renderRichText(text: string) {
  // Split by newlines first
  const lines = text.split('\n');

  return lines.map((line, lineIdx) => {
    // Parse **bold** and *italic* within each line
    const parts: (string | JSX.Element)[] = [];
    let remaining = line;
    let key = 0;

    while (remaining.length > 0) {
      // Check for **bold**
      const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
      // Check for *italic*
      const italicMatch = remaining.match(/\*(.+?)\*/);

      const match = boldMatch && italicMatch
        ? (boldMatch.index! <= italicMatch.index! ? boldMatch : italicMatch)
        : boldMatch || italicMatch;

      if (!match || match.index === undefined) {
        parts.push(remaining);
        break;
      }

      // Add text before the match
      if (match.index > 0) {
        parts.push(remaining.slice(0, match.index));
      }

      // Add formatted element
      if (match[0].startsWith('**')) {
        parts.push(<strong key={key++}>{match[1]}</strong>);
      } else {
        parts.push(<em key={key++}>{match[1]}</em>);
      }

      remaining = remaining.slice(match.index + match[0].length);
    }

    return (
      <span key={lineIdx}>
        {parts}
        {lineIdx < lines.length - 1 && <br />}
      </span>
    );
  });
}

export function ChatBubble({ message }: ChatBubbleProps) {
  const isPatient = message.role === 'patient';
  const isSystem = message.role === 'system';

  const bubbleClass = isPatient
    ? 'chat-bubble chat-bubble--patient'
    : isSystem
    ? 'chat-bubble chat-bubble--system'
    : 'chat-bubble chat-bubble--ai';

  const alignClass = isPatient ? 'chat-row chat-row--right' : 'chat-row chat-row--left';

  return (
    <div className={alignClass}>
      <div className={bubbleClass}>
        {message.emergencyAlert && (
          <div className="chat-bubble__emergency-badge" role="alert">
            Emergency Alert
          </div>
        )}
        <p className="chat-bubble__content">{renderRichText(message.content)}</p>
        <time className="chat-bubble__time" dateTime={message.timestamp}>
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </time>
      </div>
    </div>
  );
}
