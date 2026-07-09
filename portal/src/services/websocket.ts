/**
 * WebSocket client for real-time triage chat.
 * Handles connection, reconnection, and message routing.
 */

import type { WebSocketMessage } from '@/types';

const WS_URL = import.meta.env.VITE_WS_URL || 'wss://placeholder.execute-api.us-east-1.amazonaws.com/prod';

type MessageHandler = (message: WebSocketMessage) => void;
type StatusHandler = (connected: boolean) => void;

export class TriageChatSocket {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private onMessage: MessageHandler;
  private onStatusChange: StatusHandler;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;
  private reconnectTimeouts = [1000, 3000, 5000];

  constructor(sessionId: string, onMessage: MessageHandler, onStatusChange: StatusHandler) {
    this.sessionId = sessionId;
    this.onMessage = onMessage;
    this.onStatusChange = onStatusChange;
  }

  connect(): void {
    const token = sessionStorage.getItem('accessToken');
    if (!token) {
      console.error('No access token for WebSocket connection');
      return;
    }

    const url = `${WS_URL}?token=${encodeURIComponent(token)}&session_id=${this.sessionId}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.onStatusChange(true);
    };

    this.ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.onMessage(message);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    this.ws.onclose = () => {
      this.onStatusChange(false);
      this.attemptReconnect();
    };

    this.ws.onerror = () => {
      this.onStatusChange(false);
    };
  }

  sendMessage(text: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'sendMessage',
        text,
        session_id: this.sessionId,
      }));
    }
  }

  disconnect(): void {
    this.maxReconnectAttempts = 0; // Prevent reconnection
    this.ws?.close();
    this.ws = null;
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }

    const delay = this.reconnectTimeouts[this.reconnectAttempts] || 5000;
    this.reconnectAttempts++;

    setTimeout(() => {
      this.connect();
    }, delay);
  }
}
