# String resource conventions

Every user-visible string lives in `res/values/strings.xml` from the first
commit. No literal ever enters a composable. AM11 adds `values-tr/`, and a
string sweep at that point would be the expensive way to do it.

`StringsConventionTest` enforces both rules below, so this document explains
*why* they exist rather than serving as the rule itself.

## Naming

| prefix | for |
|---|---|
| `app_` | the application name |
| `nav_` | bottom-navigation destination labels |
| `screen_` | screen titles and placeholder body text |
| `settings_` | labels and descriptions inside Settings |
| `action_` | buttons and menu items |
| `error_` | messages surfaced per SPEC-ANDROID hard rule 6 |
| `field_` | a watch attribute used as a form label or column header |
| `enum_<group>_` | one suggested value within a specific `enum*` list |

## Why `field_` and `enum_<group>_` are separate

This is the rule that will actually save work, and it is not obvious.

The desktop gets away with a flat English vocabulary because Qt translation
*contexts* disambiguate: the same English word can carry a different Turkish
translation depending on which context it appears in. Android string resources
are a single flat namespace with no equivalent mechanism.

Several terms in this domain genuinely recur in more than one place:

- **Power Reserve** is a movement field label *and* a complication value.
- **GMT** is a case bezel value, a dial complication, and a watch style.
- **None**, **Other**, **Chronograph** and **Silicone** each appear in two or
  three separate `enum*` lists.

If those collapse to one resource key, Turkish gets one translation for all of
them and at least one reads wrong. The damage is invisible in English, so it
would surface in AM11 — the public-release milestone — at the point where the
sweep is already frozen and every screen already exists.

Hence `field_power_reserve` and `enum_complication_power_reserve` are always
distinct keys, **even when the English text is identical**. Duplicating an
English string is cheap; discovering a namespace collision during a release
milestone is not.

## Storage stays canonical English

SPEC-ANDROID hard rule 7. An `enum*` dropdown shows the Turkish label and
writes the English value into `watch.toml`. The resource key is the UI's
concern; the value written to disk is the data's, and the two are never the
same string. AM5 builds the mapping; AM11 adds the Turkish side of it.
