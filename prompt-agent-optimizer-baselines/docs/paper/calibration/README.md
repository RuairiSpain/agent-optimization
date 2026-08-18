# Human calibration sample

`human_ratings_TEMPLATE.jsonl` is the actual, generated output of
[`_tools/human_calibration.py`](../../_tools/human_calibration.py)'s `--sample` mode — a stratified
shortlist of 80 judge-eligible items (semantic `instruction_rules`, `should_edit` `accept_if`
criteria, and `rubrics`) pulled from all ten agents' `expected/expectations.json` files, oversampling
the safety-critical agent (`05-clinical-triage-safety`, 18/80) and `should_edit`/semantic `must_have`
items, per the protocol in [`../publication-plan.md`](../publication-plan.md) item #4. Generated with
`--seed 0`, so it's reproducible — anyone running `python human_calibration.py --sample --n 80
--seed 0` against this pack gets this exact file back.

This is as far as this file can get without a human: it is a **template**, not a completed
calibration round. Every line has `text_rated`, `human_rater_id`, and `human_value` set to `null`.
Filling it in is real work someone has to actually do — see
[Step 3 of publication-plan.md's Phase 3](../publication-plan.md) — not something this pack can
generate on its own:

1. Pick a specific run to calibrate against (a specific optimized candidate's instructions, or a
   specific replicate seed's holdout responses).
2. For each line, fill in `text_rated` with the **exact** instructions/response text that item was
   judged against for that run, and `human_rater_id` + `human_value` (`true`/`false` for
   `semantic_rule`/`should_edit_accept_if` and binary `rubric` items, 1-5 for `likert_1_5` `rubric`
   items) from a person who actually reads the text and the statement/question and forms their own
   judgment — not a re-run of the judge.
3. Optionally, have a second `human_rater_id` double-rate a subset of items (the more the better) to
   get a human-vs-human agreement figure alongside judge-vs-human.
4. Run `python human_calibration.py --score --ratings <filled-in file> --judge-backend litellm
   --judge-model <model>` to get the actual calibration numbers for Table 5's companion figure.

Running `--score` against this file today (with `--judge-backend stub`, at zero cost) only proves
the scoring pipeline executes — it is not a calibration result, and the tool refuses to run at all
against the `null` fields as they stand (see `score_ratings`'s completeness check). Nothing in this
folder should be cited as a real judge-vs-human agreement number until step 2 has actually happened.
