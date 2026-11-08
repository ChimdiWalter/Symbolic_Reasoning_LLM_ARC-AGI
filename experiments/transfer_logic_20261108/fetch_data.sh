#!/bin/sh
# Download the study's public data into data/raw/ and check every sha256 (see DATA_MANIFEST.md).
set -e
cd "$(dirname "$0")"
mkdir -p data/raw/espresso_logic data/raw/classbench
E=85265139e9598852f9388d293658a1977a829a01
curl -sSL -o data/raw/espresso_logic/espresso-logic-$E.tar.gz https://codeload.github.com/classabbyamp/espresso-logic/tar.gz/$E
curl -sSL -o data/raw/classbench/parameter_files.tar.gz https://www.arl.wustl.edu/classbench/parameter_files.tar.gz
curl -sSL -o data/raw/classbench/db_generator.tar.gz https://www.arl.wustl.edu/classbench/db_generator.tar.gz
sha256sum -c <<SUMS
67bf8bcda36558dda4ca7c0c9f5c3a6fd140e425b1da83bbc7a2557063b9083d  data/raw/espresso_logic/espresso-logic-$E.tar.gz
9f7fd2a531d1606af76b6755b3cc2213c3deffa6671706966419b8ff92d5c4ba  data/raw/classbench/parameter_files.tar.gz
c6165163c417ba561784792992af073975035b6b1ad0f8233529857ac15a5afe  data/raw/classbench/db_generator.tar.gz
SUMS
