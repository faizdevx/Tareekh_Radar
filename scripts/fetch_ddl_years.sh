#!/usr/bin/env bash
# Download, unzip and extract DDL eCourts case files (Harvard Dataverse doi:10.7910/DVN/GHLGSW, CC0)
# one year at a time, deleting the large .dta after extraction to save disk.
# Usage: bash scripts/fetch_ddl_years.sh 2012 2013 ...   (run from the repo root)
set -euo pipefail
PY="${PY:-.venv/Scripts/python}"
DIR=data/raw/ddl
API=https://dataverse.harvard.edu/api/access/datafile
declare -A IDS=([2010]=10794667 [2011]=10794673 [2012]=10794681 [2013]=10794665 [2014]=10794682
                [2015]=10794660 [2016]=10794662 [2017]=10794675)
mkdir -p "$DIR"
for y in "$@"; do
  if [ -f "$DIR/all_$y/cases.parquet" ]; then echo "[$y] already extracted"; continue; fi
  zip="$DIR/cases_clean_$y.zip"
  if [ ! -s "$zip" ]; then
    if [ "$y" = "2018" ]; then
      for part in aa:10794668 ab:10794663 ac:10794666; do
        f="$DIR/cases_clean_2018_zip_part_${part%%:*}"
        [ -s "$f" ] || curl -sSL --retry 5 -o "$f" "$API/${part#*:}?format=original"
      done
      cat "$DIR"/cases_clean_2018_zip_part_aa "$DIR"/cases_clean_2018_zip_part_ab "$DIR"/cases_clean_2018_zip_part_ac > "$zip"
      rm -f "$DIR"/cases_clean_2018_zip_part_a?
    else
      curl -sSL --retry 5 -o "$zip" "$API/${IDS[$y]}?format=original"
    fi
    echo "[$y] downloaded $(stat -c%s "$zip") bytes"
  fi
  unzip -o -q "$zip" -d "$DIR"
  dta=$(ls "$DIR"/cases_clean_"$y"*.dta | head -1)
  echo "[$y] unzipped $dta"
  "$PY" -m tareekh_radar.cli ddl-extract --dta "$dta" --keys-dir "$DIR" --out "$DIR/all_$y" --name "ddl_${y}_all" 2>&1 | tail -1
  rm -f "$DIR"/cases_clean_"$y"*.dta
  echo "[$y] done"
done
