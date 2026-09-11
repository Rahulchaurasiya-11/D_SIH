import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useSubmitGuard } from './useSubmitGuard';

/** Resolves only when `release()` is called, so overlap can be forced deliberately. */
function deferred() {
  let release;
  const promise = new Promise((resolve) => {
    release = resolve;
  });
  return { promise, release };
}

describe('useSubmitGuard', () => {
  it('runs the handler once for a single submit', async () => {
    const handler = vi.fn().mockResolvedValue('done');
    const { result } = renderHook(() => useSubmitGuard(handler));

    await act(async () => {
      await result.current[0]();
    });

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('ignores repeat submits while one is in flight', async () => {
    // The bug this prevents: a double-tap fires two requests, the second fails
    // with "the case is already Notice issued", and that error overwrites the
    // success the officer just achieved.
    const gate = deferred();
    const handler = vi.fn().mockImplementation(() => gate.promise);
    const { result } = renderHook(() => useSubmitGuard(handler));

    act(() => {
      result.current[0]();
      result.current[0]();
      result.current[0]();
    });

    expect(handler).toHaveBeenCalledTimes(1);

    await act(async () => {
      gate.release();
      await gate.promise;
    });

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('accepts a new submit after the previous one settles', async () => {
    const handler = vi.fn().mockResolvedValue(null);
    const { result } = renderHook(() => useSubmitGuard(handler));

    await act(async () => {
      await result.current[0]();
    });
    await act(async () => {
      await result.current[0]();
    });

    expect(handler).toHaveBeenCalledTimes(2);
  });

  it('reports busy while running and clears it afterwards', async () => {
    const gate = deferred();
    const { result } = renderHook(() => useSubmitGuard(() => gate.promise));

    act(() => {
      result.current[0]();
    });
    await waitFor(() => expect(result.current[1]).toBe(true));

    await act(async () => {
      gate.release();
      await gate.promise;
    });
    await waitFor(() => expect(result.current[1]).toBe(false));
  });

  it('surfaces a failure as an error message and stays usable', async () => {
    const handler = vi
      .fn()
      .mockRejectedValueOnce(new Error('Network unreachable'))
      .mockResolvedValueOnce('ok');
    const { result } = renderHook(() => useSubmitGuard(handler));

    await act(async () => {
      await result.current[0]();
    });
    expect(result.current[2]).toBe('Network unreachable');

    // A failed submit must not wedge the form: retrying has to work.
    await act(async () => {
      await result.current[0]();
    });
    expect(result.current[2]).toBe('');
    expect(handler).toHaveBeenCalledTimes(2);
  });

  it('unlocks after a rejection so the guard cannot deadlock', async () => {
    const handler = vi.fn().mockRejectedValue(new Error('boom'));
    const { result } = renderHook(() => useSubmitGuard(handler));

    await act(async () => {
      await result.current[0]();
    });
    await act(async () => {
      await result.current[0]();
    });

    expect(handler).toHaveBeenCalledTimes(2);
  });

  it('clearError resets the message', async () => {
    const handler = vi.fn().mockRejectedValue(new Error('nope'));
    const { result } = renderHook(() => useSubmitGuard(handler));

    await act(async () => {
      await result.current[0]();
    });
    expect(result.current[2]).toBe('nope');

    act(() => {
      result.current[3]();
    });
    expect(result.current[2]).toBe('');
  });
});
