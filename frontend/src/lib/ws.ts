'use client';

import { useEffect, useRef, useState } from 'react';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8001/ws';

export type WsMessage = {
  channel: string;
  data: any;
};

export function useGoldenSocket(onMessage: (msg: WsMessage) => void) {
  const [connected, setConnected] = useState(false);
  const ref = useRef<WebSocket | null>(null);
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    let retry = 0;
    let closed = false;

    const connect = () => {
      const ws = new WebSocket(WS_URL);
      ref.current = ws;

      ws.onopen = () => {
        retry = 0;
        setConnected(true);
      };
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data) as WsMessage;
          handlerRef.current(msg);
        } catch {
          /* ignore */
        }
      };
      ws.onerror = () => setConnected(false);
      ws.onclose = () => {
        setConnected(false);
        if (closed) return;
        const delay = Math.min(30000, 1000 * 2 ** retry++);
        setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      closed = true;
      ref.current?.close();
    };
  }, []);

  return { connected };
}
