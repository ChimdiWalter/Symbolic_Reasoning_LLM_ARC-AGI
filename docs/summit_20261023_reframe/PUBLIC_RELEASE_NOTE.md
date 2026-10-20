# Public release note (20 October 2026)

Three files of the cancer-lesion review set are kept out of the public repository:
- `figures/fig_maize_annotated_DSC_0042_crop_x2.png`;
- `poster_cancer_lesion_review.pdf`;
- `explainer_cancer_lesion_review.pdf`.

The two PDFs embed the maize crop. The crop is unpublished data from the author's maize lesion study
(`CANCER_LESION_IMAGE_PROVENANCE.md`, section 5). The Org and LaTeX sources are included; building them needs the
figure, which is not distributed.

The public branch is built by `scripts/make_public_release.sh`, which removes exactly these three paths from the
outgoing commits.
