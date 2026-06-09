# Threads AI Agent

AI-assisted content automation for generating, reviewing, illustrating, and publishing Threads-style posts in the persona of Abdul Fatah Tirtayasa.

The app uses FastAPI, SQLAlchemy, Telegram webhooks, Gemini/OpenAI-compatible APIs, OpenRouter image generation, and the official Threads Graph API.

## Core Flow

1. **Content strategy**
   - `/changestyle` switches the active content strategy stored in `app_configs`.
   - Style v1 uses `writer_system.md` and carousel media.
   - Style v2 uses `writer_system_v2.md` with broader conversation-first Threads topics.
   - Style v2 supports either text-only posts or single-image posts.
   - Scheduler and manual jobs both use the active strategy.

2. **Ideation**
   - `/ideate` or scheduler generates 2 unique post ideas.
   - The ideation prompt receives previous `thread_post_ideas` so the AI avoids repeats.
   - Style v1 keeps ideas focused on AI, automation, data, CLI agents, and business workflows.
   - Style v2 broadens ideas into work life, career anxiety, productivity, dashboard/spreadsheet culture, and relatable operational friction through Abdul’s AI/data/automation lens.
   - Scheduler skips ideation when there are 2+ approved unpublished drafts.
   - Telegram `/ideate` asks for confirmation when backlog is high.
   - `/addidea <topic> | <angle>` manually inserts a human idea and bypasses backlog checks.

2. **Draft generation**
   - `/generate` or scheduler drafts pending ideas.
   - Drafts run through safety and style checkers.
   - Telegram sends text draft approval buttons: approve, reject, regenerate.
   - Draft regeneration creates a new draft row and marks the old one as `regenerated`.

3. **Media review**
   - Approving a text draft marks it `approved` and then follows the active media mode.
   - `carousel`: generates 3–6 slide images using `app/prompts/illustration_style.md` and flattened per-slide prompts.
   - `single_image`: generates one image using `app/prompts/illustration_single_style.md`.
   - `text_only`: skips image generation and becomes ready to publish immediately.
   - Images are stored in `thread_post_images` and sent to Telegram for approval.
   - Carousel slides and single images can be regenerated individually by reusing the stored flattened prompt.
   - Overall media buttons allow approve, reject, or regenerate full media.
   - If media is rejected or fails, the already-approved text can still publish text-only.

4. **Publishing**
   - `/publish` or scheduler publishes one approved draft FIFO.
   - Drafts with carousel status `generating` or `pending_approval` are skipped.
   - If media is approved, stored image(s) publish to Threads.
   - Multiple approved images publish as a Threads carousel; one approved image publishes as a single-image post.
   - If media is rejected/failed/none, post publishes text-only.
   - On carousel approval with multiple images, a LinkedIn-ready PDF is generated in `static/pdfs/` and the public URL is sent to Telegram for manual LinkedIn upload.

## Important Files

- `app/main.py` — FastAPI app, routes, scheduler startup, static mount.
- `app/models.py` — SQLAlchemy models.
- `app/routes/approval.py` — Telegram webhook, commands, inline callback handling.
- `app/jobs/generate_ideas.py` — ideation job, duplicate/backlog guard.
- `app/jobs/generate_daily_drafts.py` — draft generation, draft regeneration, carousel generation.
- `app/jobs/publish_approved_posts.py` — publishing approved drafts.
- `app/services/ai_generator.py` — text draft and idea generation using active writer style.
- `app/services/content_strategy.py` — active writer style/media mode config helpers.
- `app/services/illustration_generator.py` — carousel/single-image plans, flattened prompts, image generation.
- `app/services/threads_client.py` — Threads text/image/carousel publishing.
- `app/services/telegram_approval.py` — Telegram messages and approval UI.
- `app/services/pdf_carousel_generator.py` — converts carousel images into LinkedIn PDF.
- `app/prompts/` — writer v1/v2, safety, style, carousel, and single-image prompts.

## Database Tables

- `thread_post_ideas`
  - Stores ideas with `topic`, `angle`, `source_note`, `status`.
- `thread_post_drafts`
  - Stores draft content, approval/publish status, scores, Threads ID, and carousel status.
- `thread_post_images`
  - Stores generated carousel slide images, slide position, headline, caption text, and flattened prompt.
- `thread_post_logs`
  - Stores audit logs for generation, approval, publishing, and carousel actions.
- `app_configs`
  - Stores dynamic scheduler hours.

For existing databases, `create_all()` will not add new columns. Apply schema changes manually when model columns are added.

Current required manual migration for carousel review fields:

```sql
alter table thread_post_drafts
add column if not exists carousel_status varchar default 'none';

alter table thread_post_drafts
add column if not exists carousel_rejection_reason text;
```

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill credentials.

Key environment variables:

- `DATABASE_URL`
- `AI_API_KEY`
- `AI_MODEL`
- `OPENROUTER_API_KEY`
- `IMAGE_MODEL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `THREADS_USER_ID`
- `THREADS_ACCESS_TOKEN`
- `BASE_URL`
- `GENERATE_ILLUSTRATIONS`
- `AUTO_PUBLISH`

Run locally:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Static assets are served from `/static`, including generated images and PDFs.

## Telegram Webhook

```bash
curl -F "url=https://YOUR_DOMAIN/api/approval/webhook" \
  https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook
```

Use ngrok or another public tunnel for local webhook testing.

## Telegram Commands

Primary commands:

- `/changestyle` — switch content strategy:
  - Style v1 → `writer_system.md` + carousel posts.
  - Style v2 Text-post → `writer_system_v2.md` + text-only posts.
  - Style v2 Image-post → `writer_system_v2.md` + single-image posts.
- `/ideate` — generate new AI ideas; asks confirmation if approved draft backlog is high.
- `/generate` — generate text drafts for pending ideas.
- `/publish` — publish the next approved/resolved draft.
- `/schedule` — view schedules.
- `/schedule <job> <hours>` — update schedule, e.g. `/schedule publish 9,15,21`.
- `/addidea <topic> | <angle>` — manually add a pending human idea.

Admin report commands use HTML formatting and are safe predefined reads:

- `postapproved` — approved unpublished drafts: topic, content, approved time.
- `postpublished` — last 5 published posts: topic, content, published time.
- `ideaspending` — last 5 pending ideas: topic, angle, source, created time.
- `ideasdrafted` — last 5 drafted ideas: topic, angle, source, created time.
- `imageprompt <topic>` — last 10 published image prompts matching a topic.

The admin command parser also tolerates slash/hyphen forms such as `/post-approved`, but prefer the compact forms above.

## Scheduler

Configured in `app/services/scheduler.py`.

Default jobs:

- `generate_ideas` — ideation.
- `generate_daily_drafts` — draft generation.
- `publish_approved_posts` — publishing.
- `refresh_threads_token` — token refresh.

Schedule hours are stored in `app_configs` and can be updated from Telegram.

## Verification

Basic syntax/import check:

```bash
venv/bin/python -m compileall app
```

Avoid running real publish/image-generation tests unless you intend to call external APIs or publish live content.

## Safety Notes

- Only `TELEGRAM_CHAT_ID` is authorized for commands.
- Do not add raw SQL execution from Telegram.
- Do not log secrets or raw tokens.
- Draft safety rules live in `app/prompts/safety_checker.md`.
- Threads publishing can create live posts; test carefully.
