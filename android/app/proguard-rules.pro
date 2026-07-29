# Empty by design. R8 is off for the release build in AM1 (isMinifyEnabled =
# false) because there is nothing to shrink yet and an unexplained
# shrinker-induced crash in a scaffold milestone would cost more than the few
# hundred kilobytes it saves. AM11 turns it on with the release build and adds
# whatever keep rules the TOML library's reflection needs.
