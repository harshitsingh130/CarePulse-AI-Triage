/**
 * React hook for WebSocket chat connection.
 * Manages connection lifecycle, reconnection, and message state.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ChatMessage, WebSocketMessage } from '@/types';
import { TriageChatSocket } from '@/services/websocket';

interface UseWebSocketReturn {
  messages: ChatMessage[];
  connected: boolean;
  reconnecting: boolean;
  sendMessage: (text: string) => void;
  sessionComplete: boolean;
  emergencyAlert: boolean;
}

export function useWebSocket(sessionId: string | null): UseWebSocketReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [sessionComplete, setSessionComplete] = useState(false);
  const [emergencyAlert, setEmergencyAlert] = useState(false);
  const socketRef = useRef<TriageChatSocket | null>(null);

  const handleMessage = useCallback((msg: WebSocketMessage) => {
    const newMessage: ChatMessage = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      role: msg.role || 'ai',
      content: msg.content || '',
      timestamp: new Date().toISOString(),
      showSeveritySlider: msg.type === 'ui_component' && msg.component === 'severity_slider',
      emergencyAlert: msg.type === 'emergency',
    };

    if (msg.type === 'emergency') {
      setEmergencyAlert(true);
      newMessage.role = 'system';
    }

    if (msg.type === 'complete') {
      setSessionComplete(true);
      newMessage.role = 'system';
      newMessage.content = 'Your triage is complete. Check your status for next steps.';
    }

    if (msg.type === 'status' && msg.content) {
      newMessage.role = 'system';
    }

    if (newMessage.content) {
      setMessages(prev => [...prev, newMessage]);
    }
  }, []);

  const handleStatusChange = useCallback((isConnected: boolean) => {
    setConnected(isConnected);
    if (!isConnected) {
      setReconnecting(true);
    } else {
      setReconnecting(false);
      // Add greeting message when connected
      setMessages(prev => {
        if (prev.length === 0) {
          return [{
            id: 'greeting',
            role: 'ai' as const,
            content: "Hi, I'm here to help assess your symptoms so we can connect you with the right care. This should take about 2-3 minutes.\n\nWhat's your main concern today?",
            timestamp: new Date().toISOString(),
          }];
        }
        return prev;
      });
    }
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    const socket = new TriageChatSocket(sessionId, handleMessage, handleStatusChange);
    socket.connect();
    socketRef.current = socket;

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [sessionId, handleMessage, handleStatusChange]);

  const sendMessage = useCallback((text: string) => {
    if (!socketRef.current || !text.trim()) return;

    // Add patient message to local state immediately (optimistic)
    const patientMsg: ChatMessage = {
      id: `${Date.now()}-patient`,
      role: 'patient',
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, patientMsg]);

    // Send via WebSocket
    socketRef.current.sendMessage(text);
  }, []);

  return { messages, connected, reconnecting, sendMessage, sessionComplete, emergencyAlert };
}
