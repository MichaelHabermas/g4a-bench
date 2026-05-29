export interface ChatFocus {
  metric_id: string;
  team?: string;
  label: string;
  category?: string;
  decision_id?: string;
}

let currentFocus: ChatFocus | null = null;

export function setChatFocus(focus: ChatFocus | null): void {
  currentFocus = focus;
  window.dispatchEvent(new CustomEvent('yardstick-chat-focus', { detail: focus }));
}

export function getChatFocus(): ChatFocus | null {
  return currentFocus;
}

export function chatFocusEventName(): string {
  return 'yardstick-chat-focus';
}
