import type { Field, GoldenField, SourceRecord } from '../api/types'

// The systems (other than the one the value came from) that hold the same value, each named once.
export function agreeingSystems(field: Field, golden: GoldenField, records: SourceRecord[]): string[] {
  const winner = records.find((r) => r.id === golden.source_record_id)
  const counts = new Map<string, number>()
  for (const r of records) {
    if (r.id === golden.source_record_id || !r.source_enabled || r.agreement?.[field] !== true) continue
    if (winner && r.source_code === winner.source_code) continue
    counts.set(r.source_name, (counts.get(r.source_name) ?? 0) + 1)
  }
  return [...counts.keys()]
}

// "Axis Mobile App (3 records), Axis Core Banking": one name per system, with a count when it holds several.
export function namesOnce(records: SourceRecord[]): string {
  const counts = new Map<string, number>()
  for (const r of records) counts.set(r.source_name, (counts.get(r.source_name) ?? 0) + 1)
  return [...counts.entries()].map(([name, n]) => (n > 1 ? `${name} (${n} records)` : name)).join(', ')
}

// A system's trust for one field (set per field by the administrator), else its default trust.
export function trustFor(record: SourceRecord, field: Field): number {
  return Number(record.field_trust?.[field] ?? record.source_trust)
}

// "A", "A and B", "A, B and C"
export function listJoin(names: string[]): string {
  return names.length > 1 ? `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}` : names.join('')
}
