# Link check, 5 November 2026

`check_links.py` from PR #3's branch (`feature/dictionary-groundwork` at 553a573), which checks every `source_url` in `evidence_store.json` and in `dictionary/`. Run from this sandbox on 5 Nov 2026. No data was changed: the store and dictionary files had the same checksums before and after.

## Summary

- **246 unique URLs checked.** 228 OK, 3 broken, 11 blocked, 4 other errors.
- **The dictionary's 3 source URLs are all OK:** the COT report on GOV.UK and the two DHSC documents. Every failure below is in the evidence store.
- **A second run gave the same broken and blocked lists.** The run reported here is the second; the first ran before `nrv.json` existed and checked 244 URLs.
- **Broken (404), 3:** these pages are gone at these addresses and need new sources or new URLs.
  - https://mft.nhs.uk/app/uploads/sites/7/2026/07/FORMULARY-v10.19-July-2026.pdf (cited by Chondroitin sulphate)
  - https://www.bedfordshirehospitals.nhs.uk/our-services/nutrition-and-dietetics/further-information-on-eating-well (cited by Honey)
  - https://www.rightdecisions.scot.nhs.uk/scottish-cancer-network-clinical-management-pathways/breast-cancer/breast-supportive-care/specific-symptom-issues/management-of-menopausal-symptoms-after-breast-cancer (cited by Red clover extract)
- **Blocked (403), 11:** the site refused this sandbox's automated request. That doesn't show the page is gone. Every BNF page returns 403 here, as do some trust sites (UCLH, MKUH, Royal Devon). Check these from a browser.
  - https://bnf.nice.org.uk/drugs (cited by L-carnitine)
  - https://bnf.nice.org.uk/drugs/acetylcysteine (cited by N-acetylcysteine)
  - https://bnf.nice.org.uk/drugs/choline-salicylate (cited by Choline)
  - https://bnf.nice.org.uk/drugs/folic-acid (cited by Folate)
  - https://bnf.nice.org.uk/drugs/omega-3-acid-ethyl-esters (cited by Fish oil, Omega-3)
  - https://bnf.nice.org.uk/drugs/potassium-aminobenzoate (cited by PABA)
  - https://www.mkuh.nhs.uk/patient-information-leaflet/good-sources-of-iron (cited by Iron)
  - https://www.royaldevon.nhs.uk/services/rheumatology-musculoskeletal-system-joints/conditions-we-treat/osteoarthritis (cited by Chondroitin sulphate)
  - https://www.uclh.nhs.uk/patients-and-visitors/patient-information-pages/coping-nausea (cited by Ginger root extract)
  - https://www.uclh.nhs.uk/patients-and-visitors/patient-information-pages/low-fibre-diet-sheet (cited by Apple pectin)
  - https://www.uclh.nhs.uk/patients-and-visitors/patient-information-pages/ulcerative-colitis-my-diet-during-remission (cited by Artichoke extract, Dandelion root)
- **Other errors, 4:** none is shown to be broken.
  - http://111.wales.nhs.uk/encyclopaedia/v/article/Vitaminsandminerals (cited by Biotin, Chromium, Folate, Iron, Kelp, Riboflavin, Zinc): Plain http:// link. This sandbox only routes HTTPS, so the name couldn't be resolved. The https:// address returns 200. Not shown to be broken.
  - http://www.midlandsmedicines.nhs.uk/filestore/Glucosamine-DA.pdf (cited by Glucosamine): Plain http:// link. This sandbox only routes HTTPS. The https:// address fails TLS certificate verification here ("unable to get local issuer certificate", in both Python and curl). Not verified either way; cause not confirmed.
  - http://www.nhs.uk/live-well/eat-well/food-types/starchy-foods-and-carbohydrates (cited by Potassium): Plain http:// link. This sandbox only routes HTTPS, so the name couldn't be resolved. The https:// address returns 200. Not shown to be broken.
  - https://www.oxfordhealth.nhs.uk/wp-content/uploads/2015/08/Medical_Honey_Simplified_-_Patients-leaflet.pdf (cited by Honey): URLError during this run, but the same URL returned 200 in an earlier run today and when retried afterwards. A temporary failure.

## Raw output

```
Checking 246 unique URLs...

OK: 228
BROKEN: 3
BLOCKED: 11
OTHER: 4

[BROKEN 404] https://mft.nhs.uk/app/uploads/sites/7/2026/07/FORMULARY-v10.19-July-2026.pdf
   cited by: Chondroitin sulphate

[BROKEN 404] https://www.bedfordshirehospitals.nhs.uk/our-services/nutrition-and-dietetics/further-information-on-eating-well
   cited by: Honey

[BROKEN 404] https://www.rightdecisions.scot.nhs.uk/scottish-cancer-network-clinical-management-pathways/breast-cancer/breast-supportive-care/specific-symptom-issues/management-of-menopausal-symptoms-after-breast-cancer
   cited by: Red clover extract

[OTHER ERROR URLError] http://111.wales.nhs.uk/encyclopaedia/v/article/Vitaminsandminerals
   cited by: Biotin, Chromium, Folate, Iron, Kelp, Riboflavin, Zinc

[OTHER ERROR URLError] http://www.midlandsmedicines.nhs.uk/filestore/Glucosamine-DA.pdf
   cited by: Glucosamine

[OTHER ERROR URLError] http://www.nhs.uk/live-well/eat-well/food-types/starchy-foods-and-carbohydrates
   cited by: Potassium

[OTHER ERROR URLError] https://www.oxfordhealth.nhs.uk/wp-content/uploads/2015/08/Medical_Honey_Simplified_-_Patients-leaflet.pdf
   cited by: Honey

[BLOCKED 403] https://bnf.nice.org.uk/drugs
   cited by: L-carnitine

[BLOCKED 403] https://bnf.nice.org.uk/drugs/acetylcysteine
   cited by: N-acetylcysteine

[BLOCKED 403] https://bnf.nice.org.uk/drugs/choline-salicylate
   cited by: Choline

[BLOCKED 403] https://bnf.nice.org.uk/drugs/folic-acid
   cited by: Folate

[BLOCKED 403] https://bnf.nice.org.uk/drugs/omega-3-acid-ethyl-esters
   cited by: Fish oil, Omega-3

[BLOCKED 403] https://bnf.nice.org.uk/drugs/potassium-aminobenzoate
   cited by: PABA

[BLOCKED 403] https://www.mkuh.nhs.uk/patient-information-leaflet/good-sources-of-iron
   cited by: Iron

[BLOCKED 403] https://www.royaldevon.nhs.uk/services/rheumatology-musculoskeletal-system-joints/conditions-we-treat/osteoarthritis
   cited by: Chondroitin sulphate

[BLOCKED 403] https://www.uclh.nhs.uk/patients-and-visitors/patient-information-pages/coping-nausea
   cited by: Ginger root extract

[BLOCKED 403] https://www.uclh.nhs.uk/patients-and-visitors/patient-information-pages/low-fibre-diet-sheet
   cited by: Apple pectin

[BLOCKED 403] https://www.uclh.nhs.uk/patients-and-visitors/patient-information-pages/ulcerative-colitis-my-diet-during-remission
   cited by: Artichoke extract, Dandelion root
exit=0
```
