import { api } from './api/client'

// Download the customer list as CSV. The server builds the file, so it applies the same rules as the
// screens (no contact details) and records the export in the audit log.
export async function exportCustomersCsv() {
  const blob = await api.exportCustomers()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `lumina-customers-${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(url)
}
