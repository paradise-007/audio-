import { AlertTriangle, Loader2, RefreshCw, Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import type { VoiceAnalysis } from '@/lib/api/types';

interface VoiceAnalysisCardProps {
  analysis: VoiceAnalysis | null;
  /** What the automatic pass is doing right now, or null when idle. */
  stage: 'transcribing' | 'analyzing' | null;
  error: string | null;
  /** True when the Description field already holds the suggested description. */
  descriptionApplied: boolean;
  onUseDescription: () => void;
  onReanalyze: () => void;
}

/** Plain-language summary of what was detected in the uploaded/recorded voice sample. */
export function VoiceAnalysisCard({
  analysis,
  stage,
  error,
  descriptionApplied,
  onUseDescription,
  onReanalyze,
}: VoiceAnalysisCardProps) {
  const { t } = useTranslation();

  if (!analysis && !stage && !error) {
    return null;
  }

  return (
    <div className="rounded-lg border border-border p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Sparkles className="h-4 w-4 text-muted-foreground" />
          {t('profileForm.analysis.title')}
        </div>
        {!stage && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs text-muted-foreground"
            onClick={onReanalyze}
          >
            <RefreshCw className="h-3 w-3 mr-1" />
            {t('profileForm.analysis.reanalyze')}
          </Button>
        )}
      </div>

      {stage && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {stage === 'transcribing'
            ? t('profileForm.analysis.transcribing')
            : t('profileForm.analysis.analyzing')}
        </div>
      )}

      {!stage && error && (
        <p className="text-sm text-destructive">
          {t('profileForm.analysis.failed')}: {error}
        </p>
      )}

      {!stage && analysis && (
        <>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
            {analysis.traits.map((trait) => (
              <div key={trait.key} className="min-w-0">
                <dt className="text-xs text-muted-foreground">{trait.label}</dt>
                <dd className="text-sm">{trait.value}</dd>
              </div>
            ))}
          </dl>

          {analysis.warnings.length > 0 && (
            <ul className="space-y-1">
              {analysis.warnings.map((warning) => (
                <li
                  key={warning}
                  className="flex items-start gap-1.5 text-xs text-muted-foreground"
                >
                  <AlertTriangle className="h-3.5 w-3.5 mt-px shrink-0" />
                  {warning}
                </li>
              ))}
            </ul>
          )}

          <p className="text-xs text-muted-foreground">
            {t('profileForm.analysis.note')} {analysis.limits}
          </p>

          {!descriptionApplied && (
            <Button type="button" variant="outline" size="sm" onClick={onUseDescription}>
              {t('profileForm.analysis.useDescription')}
            </Button>
          )}
        </>
      )}
    </div>
  );
}
