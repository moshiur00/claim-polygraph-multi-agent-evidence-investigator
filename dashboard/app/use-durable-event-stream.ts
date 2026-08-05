"use client";

import { useEffect, useRef, useState } from "react";

export type DurableStreamStatus =
  | "idle"
  | "connecting"
  | "live"
  | "reconnecting"
  | "polling"
  | "stale"
  | "terminal";

type DurableStreamOptions<T> = {
  active: boolean;
  url: string | null;
  cursorKey: string;
  eventNames: readonly string[];
  onEvent: (eventName: string, payload: T) => void;
  sequenceOf?: (eventName: string, payload: T) => number | null;
  poll: () => Promise<T>;
  terminal: (payload: T) => boolean;
  staleAfterMs?: number;
  pollingIntervalMs?: number;
};

type DurableStreamState = {
  status: DurableStreamStatus;
  lastSequence: number;
  reconnectAttempts: number;
  malformedEvents: number;
  lastUpdateAt: number | null;
  message: string;
};

const initialState: DurableStreamState = {
  status: "idle",
  lastSequence: 0,
  reconnectAttempts: 0,
  malformedEvents: 0,
  lastUpdateAt: null,
  message: "Live progress is idle.",
};

const withCursor = (url: string, cursor: number) => {
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}after=${Math.max(0, cursor)}&follow=true`;
};

export function useDurableEventStream<T>(options: DurableStreamOptions<T>) {
  const [state, setState] = useState<DurableStreamState>(initialState);
  const callbacks = useRef(options);
  const eventSignature = options.eventNames.join("|");

  useEffect(() => {
    callbacks.current = options;
  }, [options]);

  useEffect(() => {
    if (!options.active || !options.url) return;

    let cancelled = false;
    let source: EventSource | null = null;
    let reconnectTimer: number | null = null;
    let pollTimer: number | null = null;
    let staleTimer: number | null = null;
    let failures = 0;
    let malformedEvents = 0;
    let lastUpdateAt = Date.now();
    const storageKey = `claim-polygraph-sse:${options.cursorKey}`;
    let cursor = Number.parseInt(window.sessionStorage.getItem(storageKey) ?? "0", 10);
    if (!Number.isFinite(cursor) || cursor < 0) cursor = 0;

    const persistCursor = (next: number) => {
      if (!Number.isFinite(next) || next <= cursor) return;
      cursor = next;
      window.sessionStorage.setItem(storageKey, String(cursor));
    };

    const publish = (status: DurableStreamStatus, message: string) => {
      if (cancelled) return;
      setState({
        status,
        lastSequence: cursor,
        reconnectAttempts: failures,
        malformedEvents,
        lastUpdateAt,
        message,
      });
    };

    const accept = (eventName: string, payload: T, eventSequence?: string) => {
      const explicit = Number.parseInt(eventSequence ?? "", 10);
      const derived = callbacks.current.sequenceOf?.(eventName, payload) ?? null;
      persistCursor(Number.isFinite(explicit) ? explicit : derived ?? cursor);
      lastUpdateAt = Date.now();
      failures = 0;
      callbacks.current.onEvent(eventName, payload);
      if (callbacks.current.terminal(payload)) {
        source?.close();
        publish("terminal", "The durable workflow reached a terminal state.");
      } else {
        publish("live", "Live persisted progress is connected.");
      }
    };

    const poll = async () => {
      try {
        const payload = await callbacks.current.poll();
        if (cancelled) return;
        lastUpdateAt = Date.now();
        callbacks.current.onEvent("poll_snapshot", payload);
        const derived = callbacks.current.sequenceOf?.("poll_snapshot", payload) ?? null;
        if (derived != null) persistCursor(derived);
        if (callbacks.current.terminal(payload)) {
          source?.close();
          publish("terminal", "The durable workflow reached a terminal state.");
        } else {
          publish("polling", "Live events are unavailable; persisted state polling is active.");
        }
      } catch {
        if (Date.now() - lastUpdateAt >= (callbacks.current.staleAfterMs ?? 15_000)) {
          publish("stale", "Progress is stale. The dashboard is still trying to reconnect.");
        }
      }
    };

    const startPolling = () => {
      if (pollTimer != null) return;
      void poll();
      pollTimer = window.setInterval(
        () => void poll(),
        callbacks.current.pollingIntervalMs ?? 2_000,
      );
    };

    const connect = () => {
      if (cancelled) return;
      source?.close();
      publish(failures ? "reconnecting" : "connecting", failures
        ? `Reconnecting from persisted sequence ${cursor}.`
        : `Connecting from persisted sequence ${cursor}.`);
      source = new EventSource(withCursor(options.url!, cursor));
      source.onopen = () => {
        if (pollTimer != null) window.clearInterval(pollTimer);
        pollTimer = null;
        lastUpdateAt = Date.now();
        publish("live", "Live persisted progress is connected.");
      };
      for (const eventName of eventSignature.split("|").filter(Boolean)) {
        source.addEventListener(eventName, (rawEvent) => {
          try {
            const event = rawEvent as MessageEvent<string>;
            accept(eventName, JSON.parse(event.data) as T, event.lastEventId);
          } catch {
            malformedEvents += 1;
            publish("live", "A malformed progress event was ignored safely.");
          }
        });
      }
      source.onerror = () => {
        source?.close();
        failures += 1;
        if (failures >= 3) startPolling();
        const delay = Math.min(8_000, 500 * 2 ** Math.min(failures - 1, 4));
        publish(failures >= 3 ? "polling" : "reconnecting", failures >= 3
          ? "Live events disconnected; persisted state polling is active."
          : `Live events disconnected; retrying in ${delay / 1_000}s.`);
        reconnectTimer = window.setTimeout(connect, delay);
      };
    };

    staleTimer = window.setInterval(() => {
      if (Date.now() - lastUpdateAt >= (callbacks.current.staleAfterMs ?? 15_000)) {
        publish("stale", "No persisted update has arrived recently; recovery remains active.");
      }
    }, 5_000);
    connect();

    return () => {
      cancelled = true;
      source?.close();
      if (reconnectTimer != null) window.clearTimeout(reconnectTimer);
      if (pollTimer != null) window.clearInterval(pollTimer);
      if (staleTimer != null) window.clearInterval(staleTimer);
    };
  }, [eventSignature, options.active, options.cursorKey, options.url]);

  return options.active ? state : initialState;
}
