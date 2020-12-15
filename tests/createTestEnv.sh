#!/usr/bin/env sh
ENV_DIR=./shit
python3 -m virtualenv --no-seed $ENV_DIR
envLibDir=$ENV_DIR/lib/python3.9/site-packages;

for PACKAGE_NAME in "cryptography"; do
	DIST_PACKAGES=`python3 -c "import $PACKAGE_NAME;from pathlib import Path; print(Path($PACKAGE_NAME.__file__).resolve().parent.parent)"`
	ln -s $DIST_PACKAGES/$PACKAGE_NAME $envLibDir/$PACKAGE_NAME;
	for eID in `find $DIST_PACKAGES -maxdepth 1 -name "$PACKAGE_NAME*.egg-info"`; do
		ln -s $eID $envLibDir/`basename $eID`;
	done;
done
