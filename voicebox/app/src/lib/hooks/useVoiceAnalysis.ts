import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export function useVoiceAnalysis() {
  return useMutation({
    mutationFn: ({ file, transcript }: { file: File; transcript?: string }) =>
      apiClient.analyzeVoice(file, transcript),
  });
}
