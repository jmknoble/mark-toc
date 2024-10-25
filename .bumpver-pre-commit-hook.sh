#!/bin/sh

set -u
set -e
set -x
uv sync
git diff --exit-code uv.lock || git add uv.lock
