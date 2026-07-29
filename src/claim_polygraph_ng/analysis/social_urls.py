"""Fetch-free deterministic classification and canonicalization of social URLs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from claim_polygraph_ng.domain import SocialPlatform, SocialUrlCandidate, SocialUrlKind

_TRACKING_QUERY_KEYS = frozenset(
    {
        "fbclid",
        "gclid",
        "igshid",
        "ref",
        "ref_src",
        "si",
        "source",
    }
)
_TRACKING_PREFIXES = ("utm_",)
_MASTODON_HOSTS = frozenset({"mastodon.social"})


def classify_social_url(url: str) -> SocialUrlCandidate | None:
    """Return a normalized social candidate without requesting the URL."""

    parsed = urlsplit(url.strip())
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("candidate URL must be HTTP(S) with a hostname")
    if parsed.username or parsed.password:
        raise ValueError("candidate URL cannot contain credentials")

    host = parsed.hostname.casefold().rstrip(".")
    path = _normalized_path(parsed.path)
    query = tuple(parse_qsl(parsed.query, keep_blank_values=False))

    if host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}:
        return _x_candidate(path)
    if host in {"facebook.com", "www.facebook.com", "m.facebook.com"}:
        return _facebook_candidate(path, query)
    if host in {"instagram.com", "www.instagram.com"}:
        return _instagram_candidate(path)
    if host in {"threads.net", "www.threads.net"}:
        return _threads_candidate(path)
    if host in {"linkedin.com", "www.linkedin.com"}:
        return _linkedin_candidate(path)
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        return _youtube_candidate(host, path, query)
    if host in {"tiktok.com", "www.tiktok.com", "m.tiktok.com"}:
        return _tiktok_candidate(path)
    if host == "bsky.app":
        return _bluesky_candidate(path)
    if host in {"reddit.com", "www.reddit.com", "old.reddit.com"}:
        return _reddit_candidate(path)
    if host in _MASTODON_HOSTS:
        return _mastodon_candidate(host, path)
    return None


def _x_candidate(path: str) -> SocialUrlCandidate:
    match = re.fullmatch(r"/([^/]+)/status/([0-9]+)", path, re.IGNORECASE)
    if match:
        handle, post_id = match.groups()
        return _candidate(
            SocialPlatform.X,
            SocialUrlKind.POST,
            f"https://x.com/{handle}/status/{post_id}",
            handle,
            post_id,
        )
    match = re.fullmatch(r"/([^/]+)", path)
    if match and match.group(1).casefold() not in {"home", "search", "explore", "i"}:
        handle = match.group(1)
        return _candidate(
            SocialPlatform.X,
            SocialUrlKind.ACCOUNT,
            f"https://x.com/{handle}",
            handle,
        )
    return _candidate(SocialPlatform.X, SocialUrlKind.UNKNOWN, f"https://x.com{path}")


def _facebook_candidate(
    path: str, query: tuple[tuple[str, str], ...]
) -> SocialUrlCandidate:
    query_map = dict(query)
    if path.casefold() == "/permalink.php" and query_map.get("story_fbid"):
        post_id = query_map["story_fbid"]
        owner = query_map.get("id")
        kept = (("story_fbid", post_id),) + ((("id", owner),) if owner else ())
        canonical = f"https://www.facebook.com/permalink.php?{urlencode(kept)}"
        return _candidate(
            SocialPlatform.FACEBOOK,
            SocialUrlKind.POST,
            canonical,
            owner,
            post_id,
        )
    match = re.fullmatch(r"/([^/]+)/posts/([^/]+)", path, re.IGNORECASE)
    if match:
        handle, post_id = match.groups()
        return _candidate(
            SocialPlatform.FACEBOOK,
            SocialUrlKind.POST,
            f"https://www.facebook.com/{handle}/posts/{post_id}",
            handle,
            post_id,
        )
    match = re.fullmatch(r"/([^/]+)", path)
    if match:
        handle = match.group(1)
        return _candidate(
            SocialPlatform.FACEBOOK,
            SocialUrlKind.ACCOUNT,
            f"https://www.facebook.com/{handle}",
            handle,
        )
    return _candidate(
        SocialPlatform.FACEBOOK,
        SocialUrlKind.UNKNOWN,
        f"https://www.facebook.com{path}",
    )


def _instagram_candidate(path: str) -> SocialUrlCandidate:
    match = re.fullmatch(r"/(p|reel|tv)/([^/]+)", path, re.IGNORECASE)
    if match:
        kind, post_id = match.groups()
        return _candidate(
            SocialPlatform.INSTAGRAM,
            SocialUrlKind.POST,
            f"https://www.instagram.com/{kind.casefold()}/{post_id}",
            post_id=post_id,
        )
    match = re.fullmatch(r"/([^/]+)", path)
    if match:
        handle = match.group(1)
        return _candidate(
            SocialPlatform.INSTAGRAM,
            SocialUrlKind.ACCOUNT,
            f"https://www.instagram.com/{handle}",
            handle,
        )
    return _candidate(
        SocialPlatform.INSTAGRAM,
        SocialUrlKind.UNKNOWN,
        f"https://www.instagram.com{path}",
    )


def _threads_candidate(path: str) -> SocialUrlCandidate:
    match = re.fullmatch(r"/@([^/]+)/post/([^/]+)", path, re.IGNORECASE)
    if match:
        handle, post_id = match.groups()
        return _candidate(
            SocialPlatform.THREADS,
            SocialUrlKind.POST,
            f"https://www.threads.net/@{handle}/post/{post_id}",
            handle,
            post_id,
        )
    match = re.fullmatch(r"/@([^/]+)", path)
    if match:
        handle = match.group(1)
        return _candidate(
            SocialPlatform.THREADS,
            SocialUrlKind.ACCOUNT,
            f"https://www.threads.net/@{handle}",
            handle,
        )
    return _candidate(
        SocialPlatform.THREADS,
        SocialUrlKind.UNKNOWN,
        f"https://www.threads.net{path}",
    )


def _linkedin_candidate(path: str) -> SocialUrlCandidate:
    match = re.fullmatch(r"/posts/([^/]+)", path, re.IGNORECASE)
    if match:
        post_id = match.group(1)
        return _candidate(
            SocialPlatform.LINKEDIN,
            SocialUrlKind.POST,
            f"https://www.linkedin.com/posts/{post_id}",
            post_id=post_id,
        )
    match = re.fullmatch(r"/feed/update/([^/]+)", path, re.IGNORECASE)
    if match:
        post_id = match.group(1)
        return _candidate(
            SocialPlatform.LINKEDIN,
            SocialUrlKind.POST,
            f"https://www.linkedin.com/feed/update/{post_id}",
            post_id=post_id,
        )
    match = re.fullmatch(r"/(in|company)/([^/]+)", path, re.IGNORECASE)
    if match:
        owner_kind, handle = match.groups()
        return _candidate(
            SocialPlatform.LINKEDIN,
            SocialUrlKind.ACCOUNT,
            f"https://www.linkedin.com/{owner_kind.casefold()}/{handle}",
            handle,
        )
    return _candidate(
        SocialPlatform.LINKEDIN,
        SocialUrlKind.UNKNOWN,
        f"https://www.linkedin.com{path}",
    )


def _youtube_candidate(
    host: str, path: str, query: tuple[tuple[str, str], ...]
) -> SocialUrlCandidate:
    query_map = dict(query)
    if host == "youtu.be" and re.fullmatch(r"/([^/]+)", path):
        post_id = path.removeprefix("/")
        return _youtube_post(post_id)
    if path.casefold() == "/watch" and query_map.get("v"):
        return _youtube_post(query_map["v"])
    match = re.fullmatch(r"/(shorts|live)/([^/]+)", path, re.IGNORECASE)
    if match:
        return _youtube_post(match.group(2))
    match = re.fullmatch(r"/(@[^/]+|channel/[^/]+|c/[^/]+)", path, re.IGNORECASE)
    if match:
        handle = match.group(1)
        return _candidate(
            SocialPlatform.YOUTUBE,
            SocialUrlKind.ACCOUNT,
            f"https://www.youtube.com/{handle}",
            handle,
        )
    return _candidate(
        SocialPlatform.YOUTUBE,
        SocialUrlKind.UNKNOWN,
        f"https://www.youtube.com{path}",
    )


def _youtube_post(post_id: str) -> SocialUrlCandidate:
    return _candidate(
        SocialPlatform.YOUTUBE,
        SocialUrlKind.POST,
        f"https://www.youtube.com/watch?v={urlencode({'v': post_id})[2:]}",
        post_id=post_id,
    )


def _tiktok_candidate(path: str) -> SocialUrlCandidate:
    match = re.fullmatch(r"/@([^/]+)/video/([0-9]+)", path, re.IGNORECASE)
    if match:
        handle, post_id = match.groups()
        return _candidate(
            SocialPlatform.TIKTOK,
            SocialUrlKind.POST,
            f"https://www.tiktok.com/@{handle}/video/{post_id}",
            handle,
            post_id,
        )
    match = re.fullmatch(r"/@([^/]+)", path)
    if match:
        handle = match.group(1)
        return _candidate(
            SocialPlatform.TIKTOK,
            SocialUrlKind.ACCOUNT,
            f"https://www.tiktok.com/@{handle}",
            handle,
        )
    return _candidate(
        SocialPlatform.TIKTOK,
        SocialUrlKind.UNKNOWN,
        f"https://www.tiktok.com{path}",
    )


def _bluesky_candidate(path: str) -> SocialUrlCandidate:
    match = re.fullmatch(r"/profile/([^/]+)/post/([^/]+)", path, re.IGNORECASE)
    if match:
        handle, post_id = match.groups()
        return _candidate(
            SocialPlatform.BLUESKY,
            SocialUrlKind.POST,
            f"https://bsky.app/profile/{handle}/post/{post_id}",
            handle,
            post_id,
        )
    match = re.fullmatch(r"/profile/([^/]+)", path)
    if match:
        handle = match.group(1)
        return _candidate(
            SocialPlatform.BLUESKY,
            SocialUrlKind.ACCOUNT,
            f"https://bsky.app/profile/{handle}",
            handle,
        )
    return _candidate(
        SocialPlatform.BLUESKY,
        SocialUrlKind.UNKNOWN,
        f"https://bsky.app{path}",
    )


def _reddit_candidate(path: str) -> SocialUrlCandidate:
    match = re.fullmatch(r"/r/([^/]+)/comments/([^/]+)(?:/[^/]*)?", path, re.IGNORECASE)
    if match:
        community, post_id = match.groups()
        return _candidate(
            SocialPlatform.REDDIT,
            SocialUrlKind.POST,
            f"https://www.reddit.com/r/{community}/comments/{post_id}",
            community,
            post_id,
        )
    match = re.fullmatch(r"/(user|u)/([^/]+)", path, re.IGNORECASE)
    if match:
        handle = match.group(2)
        return _candidate(
            SocialPlatform.REDDIT,
            SocialUrlKind.ACCOUNT,
            f"https://www.reddit.com/user/{handle}",
            handle,
        )
    match = re.fullmatch(r"/r/([^/]+)", path, re.IGNORECASE)
    if match:
        community = match.group(1)
        return _candidate(
            SocialPlatform.REDDIT,
            SocialUrlKind.COMMUNITY,
            f"https://www.reddit.com/r/{community}",
            community,
        )
    return _candidate(
        SocialPlatform.REDDIT,
        SocialUrlKind.UNKNOWN,
        f"https://www.reddit.com{path}",
    )


def _mastodon_candidate(host: str, path: str) -> SocialUrlCandidate:
    match = re.fullmatch(r"/@([^/]+)/([0-9]+)", path)
    if match:
        handle, post_id = match.groups()
        return _candidate(
            SocialPlatform.MASTODON,
            SocialUrlKind.POST,
            f"https://{host}/@{handle}/{post_id}",
            handle,
            post_id,
        )
    match = re.fullmatch(r"/@([^/]+)", path)
    if match:
        handle = match.group(1)
        return _candidate(
            SocialPlatform.MASTODON,
            SocialUrlKind.ACCOUNT,
            f"https://{host}/@{handle}",
            handle,
        )
    return _candidate(
        SocialPlatform.MASTODON,
        SocialUrlKind.UNKNOWN,
        f"https://{host}{path}",
    )


def _candidate(
    platform: SocialPlatform,
    kind: SocialUrlKind,
    canonical_url: str,
    handle: str | None = None,
    post_id: str | None = None,
) -> SocialUrlCandidate:
    return SocialUrlCandidate(
        platform=platform,
        url_kind=kind,
        canonical_url=canonical_url,
        account_handle=handle,
        platform_post_id=post_id,
    )


def _normalized_path(path: str) -> str:
    compact = re.sub(r"/+", "/", path or "/")
    if compact != "/":
        compact = compact.rstrip("/")
    return compact


def retained_query(
    query: Iterable[tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    """Remove common tracking keys while retaining unrecognized provider values."""

    return tuple(
        (key, value)
        for key, value in query
        if key.casefold() not in _TRACKING_QUERY_KEYS
        and not key.casefold().startswith(_TRACKING_PREFIXES)
    )


def canonical_web_url(url: str) -> str:
    """Normalize a non-social HTTP URL without fetching or resolving redirects."""

    parsed = urlsplit(url.strip())
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("candidate URL must be HTTP(S) with a hostname")
    if parsed.username or parsed.password:
        raise ValueError("candidate URL cannot contain credentials")
    host = parsed.hostname.casefold().rstrip(".")
    port = f":{parsed.port}" if parsed.port else ""
    query = urlencode(retained_query(parse_qsl(parsed.query, keep_blank_values=False)))
    return urlunsplit(
        (
            parsed.scheme.casefold(),
            f"{host}{port}",
            _normalized_path(parsed.path),
            query,
            "",
        )
    )

