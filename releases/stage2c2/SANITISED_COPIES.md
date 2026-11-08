# Sanitised public copies, stage 2c-2 (the companion study's reviewed count-only addendum; the final paper PDFs and Writeup follow as stage 2d)

These files are published as copies. Their originals, which ran and which the freeze records hash,
stay unchanged in the author's private repository. Each copy differs from its original only in the
replacements listed: private absolute folders, private Python environments and tools, temporary and
job folders, the companion study's folder names and a reserved data folder's name. A copy marked
'wording' also has the standard wording neutralization of this branch's text files. No other byte
differs. The same map is in
`SANITISED_COPIES.json`, and `MANIFEST.json` gives the sha256 of every file this release adds or
replaces.

| file | sha256 of the original | sha256 of the public copy | what was replaced |
|---|---|---|---|
| `records/companion_aggregates_20261108/addendum/ARC_FREEZE_CANDIDATE.json` | `37fc1cebff0d4c6d6f566ba7581d12b796d4823d5f67133543b4788fadfb45b4` | `347294f76b9c2aa8ed7fcc98aa57d5eff0bd0a6786f8f3863846b5a3cb414232` | the companion study's folder, by absolute path (now `<companion study folder>/`, 3x) |
| `records/companion_aggregates_20261108/addendum/ARC_FREEZE_PROVENANCE.json` | `9b4ad350ce98fb363c29b86ce35480b574aafc77e1669287d20d2137e449dd01` | `9a4cbf65e63a53368b0d2c0a40ed467bd27b3794f7ba1901cf7a3dff2e4e5de5` | the repository's absolute folder on the study machine (now `/path/to/repository`, 2x); the companion study's folder, by absolute path (now `<companion study folder>/`, 26x) |
| `records/companion_aggregates_20261108/addendum/BIOLOGY_PROVENANCE.json` | `c49b6e1b248a463a0da81baad8c53ea6afc01afcf555e3d626ca4febd200385a` | `bb1a6cf8626f7183c8379062841f82d86133b47ea4a20eb31fc368094df8ca28` | the repository's absolute folder on the study machine (now `/path/to/repository`, 1x); the companion study's folder, by absolute path (now `<companion study folder>/`, 8x) |
