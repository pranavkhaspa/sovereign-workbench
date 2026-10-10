import { create } from "zustand";

export interface AttachmentRef {
  id: string;
  filename: string;
  sizeBytes: number;
  contentType: string;
}

interface SessionState {
  selectedModelId: string | null;
  attachments: AttachmentRef[];
  airgap: boolean;
  setSelectedModelId: (modelId: string | null) => void;
  setAttachments: (attachments: AttachmentRef[]) => void;
  addAttachment: (attachment: AttachmentRef) => void;
  removeAttachment: (id: string) => void;
  setAirgap: (airgap: boolean) => void;
}

export const useSession = create<SessionState>((set) => ({
  selectedModelId: null,
  attachments: [],
  airgap: true,
  setSelectedModelId: (selectedModelId) => set({ selectedModelId }),
  setAttachments: (attachments) => set({ attachments }),
  addAttachment: (attachment) =>
    set((state) => ({
      attachments: state.attachments.some((item) => item.id === attachment.id)
        ? state.attachments
        : [...state.attachments, attachment],
    })),
  removeAttachment: (id) =>
    set((state) => ({ attachments: state.attachments.filter((item) => item.id !== id) })),
  setAirgap: (airgap) => set({ airgap }),
}));
