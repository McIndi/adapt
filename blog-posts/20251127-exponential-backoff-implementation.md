# Exponential Backoff Implementation for Lock Retries

*Date: 2025-11-27*

---

## Introduction

In our ongoing effort to align the Adapt implementation with its specifications, we recently addressed a discrepancy in the locking mechanism's retry behavior. The README and spec documents claimed "exponential backoff" for lock acquisition retries, but the code was initially using constant delays. This post details the implementation of proper exponential backoff and the rationale behind it.

---

## Background

Adapt's safe write operations use a locking system to prevent concurrent modifications to files. When a lock cannot be acquired immediately (because another process holds it), the system retries with backoff to avoid overwhelming the database with rapid retry attempts.

The original implementation used a simple constant delay:

```python
while time.time() - start < self.timeout_seconds:
    try:
        self.lock = self.manager.acquire_lock(...)
        return self.lock
    except RuntimeError:
        time.sleep(0.1)  # Constant 0.1s delay
```

While functional, this approach doesn't scale well under high contention, as it can still generate significant database load.

---

## Exponential Backoff Implementation

We implemented exponential backoff with the following characteristics:

- **Initial delay**: 0.1 seconds (matching the original constant delay)
- **Growth factor**: 2x (delay doubles each retry)
- **Maximum delay**: 1.0 seconds (prevents excessive wait times)
- **Retry cap**: Limited to prevent integer overflow in calculations

### Code Changes

```python
def __enter__(self):
    start = time.time()
    retry_count = 0
    while time.time() - start < self.timeout_seconds:
        try:
            self.lock = self.manager.acquire_lock(self.resource, self.owner, self.reason)
            return self.lock
        except RuntimeError:
            delay = min(0.1 * (2 ** min(retry_count, 10)), 1.0)
            time.sleep(delay)
            retry_count += 1
```

### Delay Progression

| Retry | Delay | Cumulative Time |
|-------|-------|-----------------|
| 0     | 0.1s  | 0.1s           |
| 1     | 0.2s  | 0.3s           |
| 2     | 0.4s  | 0.7s           |
| 3     | 0.8s  | 1.5s           |
| 4+    | 1.0s  | 2.5s+         |

---

## Testing

We added comprehensive tests to verify the exponential backoff behavior:

```python
def test_lock_context_manager_exponential_backoff(lock_manager, monkeypatch):
    """Test that backoff delays increase exponentially."""
    # Acquire lock first
    lock_manager.acquire_lock("test.csv", "user1", "test")
    
    delays = []
    fake_time = [0]
    def mock_time():
        return fake_time[0]
    def mock_sleep(delay):
        delays.append(delay)
        fake_time[0] += delay
    
    monkeypatch.setattr(time, 'time', mock_time)
    monkeypatch.setattr(time, 'sleep', mock_sleep)
    
    with pytest.raises(TimeoutError):
        with lock_manager.lock("test.csv", "user2", "test", timeout_seconds=2):
            pass
    
    expected = [0.1, 0.2, 0.4, 0.8, 1.0]
    assert delays == expected
```

The test uses time mocking to verify exact delay sequences without actual waiting.

---

## Benefits

1. **Reduced Database Load**: Under high contention, exponential backoff significantly reduces the frequency of retry attempts, easing pressure on the database.

2. **Better Scalability**: As the number of concurrent processes increases, the backoff naturally spaces out retries, preventing thundering herd problems.

3. **Maintained Responsiveness**: The 30-second timeout ensures operations don't hang indefinitely, while the 1.0s cap prevents excessive individual delays.

4. **Spec Compliance**: Implementation now matches the documented behavior, improving trust in the specifications.

---

## Performance Impact

For typical usage with low contention, the impact is minimal - most locks are acquired on the first attempt. Under high load, the exponential backoff provides better throughput by reducing failed database operations.

The timeout test (1 second) now takes approximately 4 retries (0.1 + 0.2 + 0.4 + 0.8 = 1.5s), which is acceptable and demonstrates the backoff is working.

---

## Conclusion

This implementation brings Adapt's locking behavior in line with its specifications while improving performance under load. The exponential backoff strategy is a best practice for retry logic in distributed systems, and its addition strengthens Adapt's reliability for concurrent operations.

The changes maintain backward compatibility while providing the documented exponential backoff behavior. All existing tests pass, and the new test ensures the feature works as intended.