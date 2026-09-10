import { useCallback, useRef, useState } from 'react';

/**
 * Runs an async submit handler at most once at a time.
 *
 * A `busy` state alone does not prevent a double submission: between the click
 * and React re-rendering with the button disabled, a second tap still lands — and
 * on a phone, double-tapping a button is ordinary behaviour, not misuse. Two
 * requests then race, and the loser's error overwrites the winner's success, so
 * the officer sees "the case is already Notice issued" immediately after
 * successfully issuing it.
 *
 * The ref is checked and set synchronously, so the second call returns before it
 * can start a request.
 *
 * Returns [run, busy, error, clearError].
 */
export function useSubmitGuard(handler) {
  const inFlight = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const run = useCallback(
    async (...args) => {
      if (inFlight.current) return undefined;
      inFlight.current = true;
      setBusy(true);
      setError('');
      try {
        return await handler(...args);
      } catch (err) {
        setError(err?.message || 'Something went wrong');
        return undefined;
      } finally {
        inFlight.current = false;
        setBusy(false);
      }
    },
    [handler],
  );

  return [run, busy, error, useCallback(() => setError(''), [])];
}
