"""Knowledge base: the practice's own information plus openly licensed patient guidance."""

CLINIC_PUBLISHER = "Scope Dental Practice"

# Curated from https://scopedental.pk and the practice's Google Maps listing; edit the Markdown file
# to add services, prices, FAQs, etc., then rebuild the index.
CLINIC = [
    {
        "path": "data/clinic/scope-dental-practice.md",
        "url": "https://scopedental.pk/",
        "title": "Scope Dental Practice Islamabad",
        "slug": "practice-information",
        "retrieved": "2026-09-15",
        "publisher": CLINIC_PUBLISHER,
        "license": "© Scope Dental Practice",
        "attribution": "Information provided by Scope Dental Practice, Islamabad.",
    },
]

NHS = {
    "publisher": "NHS",
    "license": "Open Government Licence v3.0",
    "attribution": "Contains public sector information licensed under the Open Government Licence v3.0.",
}
WHO = {
    "publisher": "WHO",
    "license": "CC BY-NC-SA 3.0 IGO",
    "attribution": "© World Health Organization. Licence: CC BY-NC-SA 3.0 IGO (non-commercial use).",
}

_NHS_URLS = [
    "https://www.nhs.uk/live-well/healthy-teeth-and-gums/how-to-keep-your-teeth-clean/",
    "https://www.nhs.uk/live-well/healthy-teeth-and-gums/take-care-of-your-teeth-and-gums/",
    "https://www.nhs.uk/live-well/healthy-teeth-and-gums/taking-care-of-childrens-teeth/",
    "https://www.nhs.uk/live-well/healthy-teeth-and-gums/dental-check-ups/",
    "https://www.nhs.uk/live-well/healthy-teeth-and-gums/dental-treatments/",
    "https://www.nhs.uk/conditions/tooth-decay/",
    "https://www.nhs.uk/conditions/gum-disease/",
    "https://www.nhs.uk/symptoms/toothache/",
    "https://www.nhs.uk/conditions/dental-abscess/",
    "https://www.nhs.uk/conditions/mouth-ulcers/",
    "https://www.nhs.uk/symptoms/bad-breath/",
    "https://www.nhs.uk/conditions/mouth-cancer/what-is-mouth-cancer/",
    "https://www.nhs.uk/conditions/mouth-cancer/symptoms/",
    "https://www.nhs.uk/conditions/mouth-cancer/causes/",
    "https://www.nhs.uk/conditions/mouth-cancer/tests-and-next-steps/",
    "https://www.nhs.uk/conditions/mouth-cancer/treatment/",
    "https://www.nhs.uk/conditions/cold-sores/",
    "https://www.nhs.uk/conditions/oral-thrush-mouth-thrush/",
    "https://www.nhs.uk/tests-and-treatments/dentures/",
    "https://www.nhs.uk/tests-and-treatments/teeth-whitening/",
    "https://www.nhs.uk/symptoms/dry-mouth/",
    "https://www.nhs.uk/symptoms/teeth-grinding/",
    "https://www.nhs.uk/tests-and-treatments/wisdom-tooth-removal/",
    "https://www.nhs.uk/tests-and-treatments/root-canal-treatment/",
    "https://www.nhs.uk/baby/babys-development/teething/baby-teething-symptoms/",
]

_WHO_URLS = [
    "https://www.who.int/news-room/fact-sheets/detail/oral-health",
    "https://www.who.int/news-room/fact-sheets/detail/noma",
    "https://www.who.int/news-room/fact-sheets/detail/sugars-and-dental-caries",
]

SOURCES = CLINIC + [{"url": u, **NHS} for u in _NHS_URLS] + [{"url": u, **WHO} for u in _WHO_URLS]
