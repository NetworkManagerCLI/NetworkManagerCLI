#!/bin/sh

REV=1
BRANCH=4.4.5-mp_l4flow

git submodule init || exit 1
git submodule update || exit 1

cp fibbing.config linux/.config
(cd linux && make deb-pkg LOCALVERSION=-fibbing KDEB_PKGVERSION="$(make kernelversion)-$REV" -j 8)
