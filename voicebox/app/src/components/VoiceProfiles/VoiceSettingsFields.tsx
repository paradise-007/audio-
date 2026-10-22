import { useTranslation } from 'react-i18next';
import { FormLabel } from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';

export const DEFAULT_VOICE_SPEED = 1;
export const DEFAULT_REFERENCE_SECONDS = 15;
const REFERENCE_SECONDS_OPTIONS = [8, 15, 25] as const;
const SPEED_MIN = 0.7;
const SPEED_MAX = 1.3;

/** Snap a stored value to the nearest option the Select offers. */
export function nearestReferenceSeconds(value: number): number {
  return REFERENCE_SECONDS_OPTIONS.reduce((best, option) =>
    Math.abs(option - value) < Math.abs(best - value) ? option : best,
  );
}

interface VoiceSettingsFieldsProps {
  speed: number;
  onSpeedChange: (value: number) => void;
  referenceSeconds: number;
  onReferenceSecondsChange: (value: number) => void;
}

/**
 * The basic per-voice settings. Both are applied by the LuxTTS engine on every
 * generation with this voice (speed multiplies the recording's own pace; reference
 * seconds is how much of the recording the engine listens to).
 */
export function VoiceSettingsFields({
  speed,
  onSpeedChange,
  referenceSeconds,
  onReferenceSecondsChange,
}: VoiceSettingsFieldsProps) {
  const { t } = useTranslation();
  const speedLabel =
    Math.abs(speed - DEFAULT_VOICE_SPEED) < 0.01
      ? t('profileForm.settings.speedSame')
      : `${speed.toFixed(2)}×`;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <FormLabel>{t('profileForm.settings.speed')}</FormLabel>
          <span className="text-sm text-muted-foreground tabular-nums">{speedLabel}</span>
        </div>
        <Slider
          min={SPEED_MIN}
          max={SPEED_MAX}
          step={0.05}
          value={[speed]}
          onValueChange={([value]) => onSpeedChange(Math.round(value * 100) / 100)}
          aria-label={t('profileForm.settings.speed')}
        />
        <p className="text-xs text-muted-foreground">{t('profileForm.settings.speedHint')}</p>
      </div>

      <div className="space-y-2">
        <FormLabel>{t('profileForm.settings.similarity')}</FormLabel>
        <Select
          value={String(nearestReferenceSeconds(referenceSeconds))}
          onValueChange={(value) => onReferenceSecondsChange(Number(value))}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="8">{t('profileForm.settings.similarityStandard')}</SelectItem>
            <SelectItem value="15">{t('profileForm.settings.similarityDetailed')}</SelectItem>
            <SelectItem value="25">{t('profileForm.settings.similarityMaximum')}</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">{t('profileForm.settings.similarityHint')}</p>
      </div>
    </div>
  );
}
