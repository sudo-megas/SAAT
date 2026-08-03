package io.github.sudomegas.saat.ui.detail

/**
 * The typed-name guard on Delete — SPEC-ANDROID 5.6 and 5.7 item 10.
 *
 * EXACT, as the desktop's `_update_enabled` is: `text == self._model`, with no
 * trimming and no case folding. The point of the guard is not spelling, it is
 * deliberateness — it exists so that deleting a watch cannot be a gesture, and
 * every softening of it gives some of that back.
 *
 * A phone adds a complication the desktop does not have, and the answer is on
 * the other side of it: the field turns OFF autocorrect and autocapitalisation,
 * so the keyboard cannot quietly retype what the owner entered. Keeping the rule
 * strict and stopping the platform interfering beats loosening the rule to
 * accommodate it.
 *
 * A pure function, so the guard is testable without a device — which is what
 * AM5's verification list asks for.
 */
fun deleteConfirmed(typed: String, model: String): Boolean = typed == model
