"""A small fixed-window rate limiter for the authentication endpoints.

Why this exists
---------------
Login was completely unthrottled. Measured during review: 20 failed attempts
in 4.1 seconds, every one answered 401, no back-off at any point. bcrypt's
cost (~200ms per attempt) is the only thing slowing an attacker down, and
that is a speed bump, not a control -- it still allows thousands of guesses
per hour against a known address, and it does nothing at all about someone
enumerating many addresses cheaply.

Why not a library
-----------------
slowapi/limits would pull in a dependency and, for real use, Redis. This
application is explicitly single-instance (see the note in backend/storage.py
about not reaching for an object store), so process-local state is the
honest match for the deployment. If Visioret ever ran more than one worker,
this would need to move to shared storage -- each process would otherwise
keep its own allowance, multiplying the effective limit by the worker count.
That trade-off is stated here rather than discovered later.

Why fixed-window rather than token bucket
-----------------------------------------
A fixed window can allow up to 2x the limit across a window boundary. At
these numbers (10 per 5 minutes) that is 20 attempts in the worst case, which
is still far below what makes online guessing viable, and the implementation
is short enough to be obviously correct. A sliding window would be more
precise and more code than the threat justifies.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

# Failed logins allowed per client, per window. Deliberately generous: a real
# person mistyping a password a few times must never be locked out, and
# nothing here is a permanent block -- the window simply has to elapse.
LOGIN_MAX_ATTEMPTS = 10
LOGIN_WINDOW_SECONDS = 300

# Registration is limited separately and more tightly. It is the endpoint that
# creates rows, so the abuse here is bulk account creation rather than
# guessing.
REGISTER_MAX_ATTEMPTS = 5
REGISTER_WINDOW_SECONDS = 3600

_buckets: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request, scope: str) -> str:
    """Identify the caller for limiting purposes.

    request.client.host is the peer address. Behind a reverse proxy that is
    the proxy, not the user -- which would make the whole application share
    one bucket. This deployment serves the API directly (nginx only serves
    the static frontend, on a different port), so the peer really is the
    client. If a proxy is ever put in front of the API, this must switch to
    a validated X-Forwarded-For; trusting that header without a proxy in
    place would let anyone reset their own limit by setting it.
    """
    host = request.client.host if request.client else "unknown"
    return f"{scope}:{host}"


def enforce(request: Request, scope: str, max_attempts: int, window_seconds: int) -> None:
    """Raise 429 if this client has exceeded `max_attempts` in the window."""
    key = _client_key(request, scope)
    now = time.monotonic()
    bucket = _buckets[key]

    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()

    if len(bucket) >= max_attempts:
        retry_after = int(window_seconds - (now - bucket[0])) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    bucket.append(now)


def clear_attempts(request: Request, scope: str) -> None:
    """Forget this client's attempts. Called after a SUCCESSFUL login, so the
    limit only ever counts failures -- somebody signing in and out repeatedly
    is not an attacker, and should not be locked out for it."""
    _buckets.pop(_client_key(request, scope), None)
