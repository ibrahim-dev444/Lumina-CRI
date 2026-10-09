// Labels and colours for KYC status and AML risk, shared by the Compliance page and the customer tab.

export const KYC_LABEL: Record<string, { tone: 'good' | 'warn' | 'bad' | 'neutral'; label: string }> = {
  verified: { tone: 'good', label: 'KYC verified' },
  due_soon: { tone: 'warn', label: 'Re-KYC due soon' },
  overdue: { tone: 'bad', label: 'Re-KYC overdue' },
  no_record: { tone: 'neutral', label: 'No KYC record' },
}

export const RISK_LABEL: Record<string, { tone: 'good' | 'warn' | 'bad'; label: string }> = {
  low: { tone: 'good', label: 'Low risk' },
  medium: { tone: 'warn', label: 'Medium risk' },
  high: { tone: 'bad', label: 'High risk' },
}
