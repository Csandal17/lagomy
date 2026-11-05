# National coverage check, 5 November 2026

Evidence for a later precompute run. No data was changed.

This covers the 30 ingredients that `results/authority_audit.md` lists: the 21 whose evidence relies only on non-national sources, and the 9 with no statements. For each one I looked for a national page that covers it, on www.nhs.uk, NICE CKS and the BNF, using live pages only.

## Summary

- **1 of 30 has a national page.** Chondroitin sulphate is covered by the NHS osteoarthritis treatment page.
- **1 more is only partly covered.** www.nhs.uk mentions flaxseed (linseed) as an omega-3 oil and as fibre, but not flaxseed lignans.
- **28 have no national page found on www.nhs.uk.**
- **Boron and Silicon are not on the NHS vitamins and minerals "Others" page as it is today.** I checked it first. Its sections are beta-carotene, chromium, copper, magnesium, manganese, molybdenum, phosphorus, potassium, selenium, sodium chloride (salt) and zinc. None of the other vitamins and minerals pages (calcium, iodine, iron, vitamins A, B, C, D, E and K) mentions any of the 30 ingredients.
- **NICE CKS and the BNF could not be checked.** Both returned HTTP 403 to every request from this session, including plain topic and drug pages, for example `cks.nice.org.uk/topics/osteoarthritis/` and `bnf.nice.org.uk/drugs/betaine/`. I didn't try to get around the block. So "no national page found" below means none on www.nhs.uk. CKS and the BNF are still to be checked.

## How I checked

1. **The vitamins and minerals hub and every page linked from it**, starting with "Others", searched for each ingredient's name and synonyms.
2. **The NHS website search** (`www.nhs.uk/search/results?q=…`), once for each name and main synonym. For each search with results, I opened the first 5 results and looked for the term as a whole word.
3. **The NHS medicines A to Z index**, for every term.
4. **24 NHS condition and medicine URLs where these ingredients plausibly appear**, checked for all 30 ingredients' terms. These 18 loaded on www.nhs.uk:
   - osteoarthritis treatment
   - age-related macular degeneration, and its treatment page
   - constipation
   - cold sores
   - varicose veins
   - piles
   - high cholesterol, and how to lower it
   - alternatives to HRT
   - menopause treatment
   - different fats
   - IBS
   - indigestion
   - herbal medicines and complementary therapies
   - osteoporosis
   - food guidelines and food labels

   Five of the URLs I tried returned 404: glucosamine, cystinuria, the herbal medicines and supplements guesses, and increasing your milk supply. One, homocystinuria, now redirects to GOV.UK.

A page counts as coverage only if it is about the ingredient as a supplement or nutrient. A passing mention of something else with a similar name doesn't count, and those near-misses are noted below.

The search terms were each ingredient's name plus synonyms where useful: siberian ginseng, lignans, flaxseed, linseed, policosanol, lecithin, borage, flavonoids and piperine. Amino acid names were searched without the "L-" prefix.

## Results

| Ingredient | National page | Exact quote |
| --- | --- | --- |
| Chondroitin sulphate | https://www.nhs.uk/conditions/osteoarthritis/treatment/ (section "Nutritional supplements") | "A number of nutritional supplements have been used to treat osteoarthritis in the past, including chondroitin and glucosamine." The next sentence: "GPs no longer prescribe chondroitin and glucosamine on the NHS because there's no strong evidence that they are effective as a treatment." |
| Flaxseed lignans | Partial: https://www.nhs.uk/live-well/eat-well/food-types/different-fats-nutrition/ and https://www.nhs.uk/conditions/constipation/ | "Sources of omega-3 fatty acids suitable for vegetarians include flaxseed (linseed) oil, rapeseed oil, walnuts and egg enriched with omega-3." and "add some wheat bran, oats or linseed to your diet". Both are about flaxseed as an oil or fibre, not lignans. |
| Lutein | no national page found | Searched "lutein": no results. The AMD pages don't mention it. |
| L-arginine | no national page found | Search hits are only about "arginine vasopressin", a hormone (diabetes insipidus pages). That's not coverage. |
| Eleuthero | no national page found | |
| L-cysteine | no national page found | |
| L-cystine | no national page found | `/conditions/cystinuria/` returns 404. |
| Apple pectin | no national page found | |
| Artichoke extract | no national page found | |
| Betaine hydrochloride | no national page found | The NHS homocystinuria URL redirects to a GOV.UK page, which says "a medication called betaine is sometimes given to help reduce blood homocysteine levels". That's betaine the medicine, not betaine hydrochloride, and the page isn't on www.nhs.uk. |
| Blackcurrant seed oil | no national page found | |
| Fenugreek | no national page found | |
| Hesperidin | no national page found | |
| Horsetail extract | no national page found | |
| Marine collagen | no national page found | The only search hit is the keloid scars page ("too much of a substance called collagen in your skin"), which is not about collagen supplements. |
| Octacosanol | no national page found | |
| Phosphatidylcholine | no national page found | |
| Phosphatidylserine | no national page found | |
| Quercetin | no national page found | |
| Rutin | no national page found | |
| Starflower oil | no national page found | |
| Boron | no national page found | Not on the vitamins and minerals "Others" page as it is today. |
| Citrus bioflavonoids | no national page found | |
| L-lysine | no national page found | The cold sores page doesn't mention it. |
| Silicon | no national page found | Not on the vitamins and minerals "Others" page as it is today. |
| Bilberry extract | no national page found | |
| Black pepper extract | no national page found | "black pepper" returns search results, but none of the first 5 pages contains the term. |
| Grape seed extract | no national page found | "grape seed" returns 1 search result, which doesn't contain the term. |
| Hibiscus flower extract | no national page found | |
| Lemon verbena leaf extract | no national page found | "lemon verbena" returns 4 search results, none of which contains the term. |

## Not checked

- **NICE CKS and the BNF:** both return 403 to this session (see the summary).
- **www.nice.org.uk guidance:** not in this check's scope. It may cover some of these, for example NICE's osteoarthritis guideline on glucosamine and chondroitin.
