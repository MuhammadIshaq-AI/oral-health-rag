# Practice knowledge base

`scope-dental-practice.md` is the practice's own information that the assistant answers from. It
only contains facts published on https://scopedental.pk (checked 2026-09-15). This README is not
indexed.

The live website doesn't publish an address, opening hours, services or prices yet, so the assistant
correctly says it doesn't have them. Google Maps can't be scraped: it's JavaScript-rendered and its
terms forbid scraping. To add these details, copy them from the practice's Google Maps listing
(or ask the practice) into `scope-dental-practice.md`, confirm them with the practice, and rebuild:

```bash
python scripts/build_index.py
```

Also set `address` in `web/src/lib/brand.ts` to show it in the app's contact card.

## Sections to add (copy into `scope-dental-practice.md` and fill in)

```markdown
## Address
Scope Dental Practice, <street / sector>, Islamabad, Pakistan.

## Opening hours
- Monday: <e.g. 10:00 am – 8:00 pm>
- Tuesday: …
- Sunday: <Closed?>

## Treatments we offer
- <e.g. Microscopic root canal treatment>
- <e.g. Teeth whitening>

## Fees
<Only if the practice wants prices shared, e.g. "Consultation: Rs …">

## Frequently asked questions
### Do I need an appointment?
<answer>
```

Keep each fact in a clearly headed section; headings become the section names shown in citations.
