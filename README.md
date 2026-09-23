# The Quiet Takeover — mirror feed

**Why it exists:** the platform-generated RSS feed
(`https://muse.ai/podcasts/feed/1282384998281277/5435f036-8a3c-4b28-95f2-d6c2e4a05e29`)
does not render `<itunes:author>` or `<itunes:owner>`/`<itunes:email>`, and the
platform offers no way to add them (`podcast-helper publish` only takes
`--feed-title`/`--feed-description`; `remote-storage publish-episode` has no
author/email flags either). Spotify for Podcasters rejects the import without
those tags ("Your podcast RSS feed is missing some things: Author, Email
address"). This mirror injects them; everything else passes through byte-
equivalent in meaning (same GUIDs, enclosure URLs, titles, descriptions).

## Injected values

| Tag | Value | Source |
|---|---|---|
| `itunes:author` | `Milo and Nadia` | show hosts (fixed) |
| `itunes:owner/itunes:name` | `Spenz` | show owner |
| `itunes:owner/itunes:email` | `spencererskine2009@gmail.com` | Spenz's Gmail via Gmail `users.getProfile` |

The Gmail address is required: Spotify sends its show-ownership verification
code to `itunes:owner/itunes:email` during the "claim existing show" import.
Note it becomes publicly visible in the feed XML — that is inherent to how
podcast ownership verification works.

## Files

- `mirror_feed.py` — fetches the official feed, injects the tags right after
  `<channel><title>`, validates, writes `feed.xml`. Stdlib only. Idempotent.
  `python3 mirror_feed.py --check feed.xml` validates a built file.
- `feed.xml` — latest built mirror (regenerated, committed by CI).
- `.github/workflows/refresh-feed.yml` — daily refresh Action (see below).

## Hosting (pending)

No durable public HTTPS hosting is available from the agent VM today:
no public inbound IP (outbound goes through Cloudflare WARP), `gh` is not
logged in, Tailscale is not connected, `cloudflared` is unconfigured, and
anonymous file hosts (catbox, 0x0.st, transfer.sh, …) issue a new random URL
per upload, which breaks the stable feed URL Spotify/Apple poll.
Using a web artifact as the host is also off the table (policy: artifacts are
not file hosting for other integrations; and the runtime serves HTML pages,
not raw XML).

**Planned:** GitHub Pages, the smallest robust unblock.
1. Spenz runs `gh auth login` on the VM (device flow: ~1 minute, one code).
2. Create repo `the-quiet-takeover-feed` containing `mirror_feed.py`,
   `feed.xml`, and `.github/workflows/refresh-feed.yml`; enable Pages.
3. Public mirror URL: `https://<github-user>.github.io/the-quiet-takeover-feed/feed.xml`
   (serves `.xml` as `application/xml`).
4. Hand that URL to the parked Spotify import browser task; same URL works
   for the Apple Podcasts Connect submission.

## Freshness

The daily episode cron publishes to the official feed ~6:39 AM PT. The
GitHub Action above regenerates `feed.xml` daily at 8:30 AM PT (15:30 UTC)
and commits only when the feed changed. New episodes therefore reach
Spotify/Apple within a few hours of publication (directories poll on their
own cadence after that).

## Failure modes

- **Action fails / Pages down:** mirror goes stale; Spotify/Apple keep
  serving the last good copy. The Action run history shows the failure.
- **Official feed unreachable at refresh time:** the script exits non-zero
  and writes nothing, so the last good `feed.xml` stays live.
- **Official feed format changes:** `--check` validation fails loudly rather
  than publishing a broken feed.
- **Owner email changes:** update `OWNER_EMAIL` in `mirror_feed.py` and
  re-run; then re-verify show ownership with Spotify (it re-checks the tag).
