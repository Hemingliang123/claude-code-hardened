/**
 * Secure random utilities for retry jitter and timing operations.
 * Replaces Math.random() with crypto.randomInt() to prevent
 * predictable timing patterns that could enable timing attacks.
 * 
 * Added as part of security hardening audit.
 */
import { randomInt } from 'crypto'

/**
 * Returns a secure random float in range [min, max] using crypto.randomInt.
 * For jitter fractions, use secureJitterFraction().
 */
export function secureRandomFloat(min: number, max: number): number {
  const range = (max - min) * 1_000_000
  return min + randomInt(0, range + 1) / 1_000_000
}

/**
 * Returns a jitter multiplier in range [-1, 1] using crypto.randomInt.
 * Usage: baseDelay + baseDelay * 0.25 * secureJitterFraction()
 * Replaces: baseDelay + baseDelay * 0.25 * (2 * Math.random() - 1)
 */
export function secureJitterFraction(): number {
  return 2 * (randomInt(0, 1_000_001) / 1_000_000) - 1
}

/**
 * Returns a random jitter in milliseconds [0, maxMs] using crypto.randomInt.
 * Usage: delay + secureJitterMs(500)
 * Replaces: delay + Math.random() * 500
 */
export function secureJitterMs(maxMs: number): number {
  return randomInt(0, maxMs + 1)
}
