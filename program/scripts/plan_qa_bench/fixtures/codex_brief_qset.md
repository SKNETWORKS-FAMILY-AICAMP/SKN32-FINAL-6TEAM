You are building an evaluation dataset. Output ONE JSON object only (no prose, no code fences).

Context: a Seoul travel service keeps each customer's itinerary as a list of items. Customers chat in free text
(mostly Korean, sometimes English, Japanese, Chinese) asking about their own itinerary. We need to test whether a
system can tell WHICH itinerary item a question refers to, or that it refers to none.

Build:
1. "today": "2026-10-09" (the day before the trip).
2. "itinerary": a realistic 4-day Seoul trip for a family of 4, 2026-10-10 (Sat) ~ 2026-10-13 (Tue), 18-22 items.
   Each item: {"id": int starting 1, "date": "YYYY-MM-DD", "start": "HH:MM", "kind": one of activity|dining|lodging|mobility,
   "title": short Korean title as a customer's planner would write it, "place": real Seoul place name (Korean)}.
   Mix: palaces/museums/markets/hiking/river activities/shows/theme parks/cafes/restaurants, one hotel check-in, one or two
   transport items (e.g. airport train). Use real places. Do not reuse this exact set: 경복궁, 토속촌, 한강 카약, 명동교자,
   북한산 둘레길, 광장시장, 국립중앙박물관, 난타, N서울타워, 남대문시장, 롯데월드.
3. "questions": exactly 100 items {"q": text, "gold": item id or null, "type": category}. Categories and counts:
   - direct (names the place or title, possibly partially): 12
   - paraphrase (describes it without its name: what you do there, what kind of place): 20
   - relative_time (first/second/last day, weekday, morning/lunch/evening, a clock time, "tomorrow"): 15
   - english: 10, japanese: 4, chinese: 4 (same mix of direct/paraphrase/time inside)
   - typo_or_slang (misspellings, abbreviations, casual speech): 8
   - sequence ("after lunch where do we go", "the stop before the hotel"): 7  -> gold is the item being asked about
   - policy_about_item (rule/condition questions tied to one item: cancellation if rain, kids allowed, refund): 10
   - none (unrelated to any item: general knowledge, exchange rate, a place NOT in the itinerary, "today" when nothing is
     scheduled today, generic refund policy with no item): 10
   Questions must be natural customer chat, varied in length and politeness. Gold must be unambiguous to a careful human
   reading the itinerary. Do not add hints like item ids.
