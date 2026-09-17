import { useCallback, useState } from 'react'

/** Read a JSON value from localStorage. Never throws (private mode, quota, disabled storage). */
export function readStorage<T>(key: string, fallback: T, validate?: (value: unknown) => value is T): T {
  try {
    const raw = window.localStorage.getItem(key)
    if (raw === null) return fallback
    const parsed: unknown = JSON.parse(raw)
    if (validate && !validate(parsed)) return fallback
    return parsed as T
  } catch {
    return fallback
  }
}

export function writeStorage(key: string, value: unknown): void {
  try {
    if (value === undefined || value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Storage unavailable: the preference simply won't persist.
  }
}

/**
 * useState backed by localStorage. All storage access is wrapped in try/catch
 * so the app keeps working when storage is blocked.
 */
export function useLocalStorage<T>(
  key: string,
  initial: T,
  validate?: (value: unknown) => value is T,
): [T, (next: T | ((prev: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => readStorage(key, initial, validate))

  const update = useCallback(
    (next: T | ((prev: T) => T)) => {
      setValue((prev) => {
        const resolved = typeof next === 'function' ? (next as (p: T) => T)(prev) : next
        writeStorage(key, resolved)
        return resolved
      })
    },
    [key],
  )

  return [value, update]
}
