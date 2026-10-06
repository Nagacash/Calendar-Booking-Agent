import { create } from "zustand";
import { persist } from "zustand/middleware";

export type KeyBag = {
  livekitUrl: string;
  apiKey: string;
  apiSecret: string;
  agentName: string;
};

type KeyStore = KeyBag & {
  setKeys: (keys: Partial<KeyBag>) => void;
  clearKeys: () => void;
  hasKeys: () => boolean;
};

const empty: KeyBag = {
  livekitUrl: "",
  apiKey: "",
  apiSecret: "",
  agentName: "calendar-avatar",
};

export const useKeyStore = create<KeyStore>()(
  persist(
    (set, get) => ({
      ...empty,
      setKeys: (keys) => set(keys),
      clearKeys: () => set(empty),
      hasKeys: () => {
        const s = get();
        return Boolean(s.livekitUrl && s.apiKey && s.apiSecret && s.agentName);
      },
    }),
    { name: "calendar-face-keys" },
  ),
);
