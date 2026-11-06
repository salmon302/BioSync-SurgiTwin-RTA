# Dataset provenance: sim/segmentation/data

Author: Seth Nenninger (Builder_Int34 Agent)
Retrieval date: 2026-11-05 (UTC)
Contribution: plan task 2.1 slice 1, see SNDEV/docs/impl-2026-11-05-task21-slice1-segmentation.md

## Status

SMOKE dataset. This is not G2.1 reference data. It has no reference labels for Dice evaluation. The TCIA SEG object in this folder is kept for slice 2 and is not used as segmentation input in slice 1.

## Dataset

- Collection: HCC-TACE-Seg (Multimodality annotated HCC cases with and without advanced imaging segmentation)
- Source: The Cancer Imaging Archive (TCIA), https://www.cancerimagingarchive.net/collection/hcc-tace-seg/
- DOI: 10.7937/TCIA.5FNA-0924
- Version: TCIA v1, updated 2022/08/17 (collection page)
- Subject used: Patient ID HCC_001
- Modalities used: CT (series "C-A-P", two acquisitions of 36 and 30 slices, selected acquisition is 36 slices) and SEG (not used in slice 1)
- License: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/ (text bundled as LICENSE-HCC-TACE-Seg-CT.txt and LICENSE-HCC-TACE-Seg-SEG.txt)
- Required citation: Moawad, A. W., Fuentes, D., Morshid, A., Khalaf, A. M., Elmohr, M. M., Abusaif, A., Hazle, J. D., Kaseb, A. O., Hassan, M., Mahvash, A., Szklaruk, J., Qayyum, A., & Elsayes, K. (2021). Multimodality annotated HCC cases with and without advanced imaging segmentation [Data set]. The Cancer Imaging Archive. https://doi.org/10.7937/TCIA.5FNA-0924
- Download method: NBIA REST API, `https://services.cancerimagingarchive.net/nbia-api/services/v1/getImage?SeriesInstanceUID=<UID>`, no authentication

## Files

| File | Series or object UID | Bytes | SHA-256 |
| --- | --- | --- | --- |
| HCC_001_CT_C-A-P_1.3.6.1.4.1.14519.5.2.1.1706.8374.302065206690360709343725942120.zip | 1.3.6.1.4.1.14519.5.2.1.1706.8374.302065206690360709343725942120 | 17780801 | 4B3E47905148EDE21FDE9AD97AD2EE9EF4BB98A2D63EA6D2DB226F82234DD832 |
| HCC_001_SEG_1.2.276.0.7230010.3.1.3.8323329.719.1600928570.399942.zip | 1.2.276.0.7230010.3.1.3.8323329.719.1600928570.399942 | 36327 | D1CADD284A15A477C0CACD76E9C9AE239701A7AAC280EC99A0A5B3AD5B220A17 |
| HCC-TACE-Seg_clinical_data-V2.xlsx | Clinical data (no DICOM series) | 128507 | E9D2683DC907819AA08E4027E085854F46464BEC834A09E80FC83B19A89E092B |

The extracted folders `HCC_001_CT_C-A-P_<UID>/` (66 DICOM files) and `HCC_001_SEG_<UID>/` (1 DICOM file) are derived from the zips above. The DICOM files inside the folders are not checksummed individually. The zip checksums are the pinned identity.

The clinical spreadsheet was downloaded 2026-11-05 from the TCIA collection page (CC BY 4.0): `https://www.cancerimagingarchive.net/wp-content/uploads/HCC-TACE-Seg_clinical_data-V2.xlsx`. It holds the per-subject clinical table and a glossary sheet. It documents tumor characteristics for HCC_001 (Tr_Size 0.8 cm, multinodular, T_involvment <= 50%) and no lesion location (no lobe, segment, or coordinate field). The search trail for the operator-seeded tumor clause is in `SNDEV/docs/impl-2026-11-05-task21-slice5-val031.md`.

## Excluded source

The Kitware TAIR "Multimodal Imaging Dataset for Cerebrovascular Disease" (http://tair.kitware.com/clinical-data, CC BY 4.0, 70 GB zip) was evaluated and not downloaded. It is NIfTI for CTA/MRA, has no liver, breast, or tumor labels, and its size is outside the slice budget. The search trail is in the implementation log.

## Verification

Both zips open as valid archives. The CT zip holds 66 DICOM files and a LICENSE file. The SEG zip holds one DICOM file and a LICENSE file. Slicer 5.12.4 imports the CT folder through DICOMUtils (see SNDEV/logs/probe-slicer-2026-11-05.log).
