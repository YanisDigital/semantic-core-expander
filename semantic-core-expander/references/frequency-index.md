# The popularity index (1-100) and how to use it

Google does not give search volumes for free (Keyword Planner shows only ranges,
and only with an Ads account). The index is a proxy computed from how Google
suggested each phrase during the crawl.

## How it is computed

For every cached answer and every suggestion in it:

- **Earlier is stronger** — weight is divided by the square root of the number
  of characters typed beyond the root. A phrase suggested after "dentist a"
  outweighs one that appears only after a long prefix.
- **Higher position is stronger** — position 1 of 15 weighs most.
- **More appearances add up** — a phrase suggested for many prefixes collects
  more points.
- **Prefix matches beat infix matches** — if the suggestion starts with what was
  typed, full weight; if the typed text is inside it, 0.6.

The sum goes on a log scale and is stretched to 1-100 inside the project: the
strongest phrase gets 100, the weakest 1.

## How to read it

- 60-100: the stable, mass queries of the topic — sections, hubs, main pages.
- 30-59: the middle layer — articles, guides, category pages.
- 1-29: the long tail — specific questions, FAQs, small pages.

What it does not tell you:

- Traffic. 80 is not "twice as many searches" as 40; the scale is logarithmic and
  relative.
- Comparison with other files. Each export has its own scale.
- Stability. Event-driven phrases (news, incidents, sales) can score high because
  of a recent spike.

## Using it instead of search volume

1. **Cluster first, then sort.** One phrase with index 20 means little. Look at
   the Clusters sheet: sum of index shows how "alive" a topic is, number of
   queries shows its depth — many different queries suggest a whole section.
2. **Tier the work.** Build structure from the top tier, content plans from the
   middle, FAQ / long-form answers from the tail. A high index shows demand, not
   that you can rank for it.
3. **Filter noise.** Index below ~5-10 is often a random tail (an address, a
   surname, a cut-off phrase). Keep it for coverage, deprioritise it in plans.
4. **Separate spikes from steady demand.** News-like phrases need fast formats,
   evergreen ones (prices, schedules, how-to, addresses) need durable pages.
5. **Confirm the top with real numbers.** Upload the top 1-3 thousand phrases
   (not the whole file) to Google Keyword Planner for volume ranges; once the
   site is live, Google Search Console shows real impressions; Google Trends
   compares a few topics.

Do not add indexes up as "traffic", and do not drop the tail automatically: for
informational sites the tail is a large share of total coverage.
