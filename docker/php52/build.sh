#!/usr/bin/env bash
set -euo pipefail

if (( $# != 2 )); then
  echo "Usage: $0 PHP_5.2.17_SOURCE_ARCHIVE ZEND_OPTIMIZER_3.3.9_ARCHIVE" >&2
  exit 2
fi

php_archive=$1
optimizer_archive=$2
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_tmp=$(mktemp -d)
trap 'rm -rf -- "$build_tmp"' EXIT

printf '%s  %s\n' \
  e81beb13ec242ab700e56f366e9da52fd6cf18961d155b23304ca870e53f116c \
  "$php_archive" | sha256sum -c -
printf '%s  %s\n' \
  2dc42dec471cf6754f8f7dbb7444a040c92cc6c99b80c8aa924bdcd4d33decb8 \
  "$optimizer_archive" | sha256sum -c -

mkdir "$build_tmp/php"
cp -- "$php_archive" "$build_tmp/php/php-5.2.17.tar.bz2"
split -b 400K -d -a 2 -- "$optimizer_archive" "$build_tmp/optimizer_"

secrets=()
for index in 00 01 02 03 04 05 06; do
  part="$build_tmp/optimizer_$index"
  test -f "$part"
  secrets+=(--secret "id=optimizer_$index,src=$part")
done
test ! -e "$build_tmp/optimizer_07"

DOCKER_BUILDKIT=1 docker build --platform linux/amd64 \
  --build-context "php_source=$build_tmp/php" \
  "${secrets[@]}" \
  -f "$script_dir/Dockerfile" -t zend-php52-optimizer:local "$script_dir"
