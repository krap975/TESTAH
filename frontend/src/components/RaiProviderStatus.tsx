import type { RaiConfiguration } from '../types/rai';

export function RaiProviderStatus({ configuration }: { configuration: RaiConfiguration | null }) {
  return <p className={configuration?.is_mock ? 'form-success' : 'form-help'}>
    {configuration
      ? `Active RAI configuration: ${configuration.provider} / ${configuration.model}. ` +
        (configuration.is_mock ? 'MOCK MODE. No LLM API is used.' : 'Designer and RAI Examiner use this provider. API access is verified only by successful generation.')
      : 'Loading RAI provider configuration…'}
  </p>;
}
