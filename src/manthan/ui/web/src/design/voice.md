# Voice and copy guide

Who reads it: a recruiter who skims, and an engineer who checks. Both read the same screen. The plain sentence serves the first, and the technical line serves the second.

## Rules
1. Plain sentence first. The technical line comes on request (the Plain, Both or Technical switch).
   - Good: "The attacker asked the target to role-play a chemist."
   - Bad: "Turn 3 emitted by attacker role with crescendo escalation."
2. A number never stands alone. It sits in a sentence with its meaning, and the range comes from the stored metric row. The UI never recomputes it.
   - Good: "4 of 15 Crescendo attacks worked (27%). The true rate is likely between 11% and 52%."
   - Bad: "ASR 0.267"
3. The technical line is a log line in mono: `key=value` pairs separated by two spaces. Units sit on the value.
   - Good: `role=target  model=qwen2.5:7b  latency=21.4s  run=3f2a9c1e`
   - Bad: `target · qwen2.5:7b · 21.4 · 3f2a9c1e` (no keys, no unit)
4. A missing value shows "—". The UI never guesses. A tooltip says why it is missing, for example "This run is older than the event log."
5. Verdict badges read exactly "ATTACK WORKED" or "DEFENCE HELD". These are the only all-caps text in the UI. "ATTACK WORKED" is cream on a solid black fill. It is the only black fill in the UI, so no other button, chip or tag may be black.
6. Empty states say what is missing and how to fill it.
   - Good: "No campaigns in this database yet. Start one on the Run page."
   - Bad: "Nothing to see here!"
7. Errors say what happened and what to do, with no apology.
   - Good: "A run is already going. Stop it on the Run page, or wait until it ends."
   - Bad: "Oops, something went wrong."
8. Buttons name the action, and the result uses the same word: "Start run", then "Run started".
9. Short sentences, active voice, one idea per sentence. Use UK spelling ("defence"), as the badges and the spec do.
10. Banned words: delve, tapestry, robust, seamless, leverage, "it's worth noting", "not just X but Y". No emojis and no exclamation marks.
