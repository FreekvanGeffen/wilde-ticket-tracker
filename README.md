# Ticket Price Trackers

Tracks ticket prices every 15 minutes via GitHub Actions (free on public repos).

## Wildeburg (Paylogic resale)

Tracks the lowest **Weekend + Camping** resale price and sold-ticket count from Paylogic.

History is stored in [`ticket_price_history.csv`](ticket_price_history.csv):

- `date` — Amsterdam date (`YYYY-MM-DD`)
- `time` — Amsterdam time (`HH:MM:SS`)
- `lowest_price_eur`
- `sold_tickets`
- `available_tickets` — counted by how often `statiegeld` appears on the page (one per listed ticket)

## Lowlands 2026 (Ticketmaster verified resale)

Tracks verified resale listings for the Lowlands 2026 festivalticket on Ticketmaster NL.

History is stored in [`lowlands_ticket_price_history.csv`](lowlands_ticket_price_history.csv):

- `date` — Amsterdam date (`YYYY-MM-DD`)
- `time` — Amsterdam time (`HH:MM:SS`)
- `lowest_resale_price_eur` — lowest verified resale listing price
- `available_resale_tickets` — total tickets available across all verified resale listings
- `primary_price_eur` — face-value price shown for new tickets

## GitHub Actions setup (free)

1. Create a **public** GitHub repository.
2. Push this project to `main`:

```bash
cd /Users/freekvangeffen/.cursor/projects/empty-window
git init
git add .
git commit -m "Add ticket price tracker"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

3. In GitHub: **Settings → Actions → General → Workflow permissions**
   - Set to **Read and write permissions**
   - Save

4. Enable scheduled workflows:
   - **Settings → Actions → General → Allow all actions**

5. Trigger the first run manually:
   - **Actions → Track ticket prices → Run workflow**

After that, the workflow runs every 15 minutes and commits new rows to `ticket_price_history.csv`.

## Cost

- Public repo + `ubuntu-latest` runner = **$0** for standard GitHub-hosted runners.
- No artifacts are uploaded; only a small CSV commit is pushed.

## Local run (optional)

```bash
uv sync
uv run playwright install chromium
uv run python ticket_price_tracker.py
uv run python lowlands_ticket_price_tracker.py
```
