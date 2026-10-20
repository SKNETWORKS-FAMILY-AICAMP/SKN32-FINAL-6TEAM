source ${ENV_FILE:-/c/Users/playdata2/Documents/wt_known_failures_env.sh}
OUT=/c/Users/playdata2/Documents/wt_known_failures_results/${RUN_TAG:-r1}
mkdir -p $OUT
FILES=${FILES:-"contract/test_api_key_file.py contract/test_web_client_contract.py security/test_no_infra_in_tracked_files.py e2e/test_decision_destination_condition_web.py e2e/test_guest_and_trip_delete.py e2e/test_intake_autofix_dry_run.py e2e/test_intake_catalog_names.py e2e/test_intake_direct_schedule.py e2e/test_intake_experience_tiers.py e2e/test_intake_stay_lines.py e2e/test_nambu_recorded_replay.py e2e/test_watch_relaxed.py scenario/test_apply_or_ask_recheck.py scenario/test_case_watch_dining.py scenario/test_trip_reminders.py integration/api/test_openapi_surface.py unit/core/test_debug_report_status.py unit/eval/test_human_review_adapters.py e2e/test_intake_test_plans.py"}
for f in $FILES; do
  name=$(echo $f | tr '/' '_')
  python -m pytest -q --tb=short -rfE -p no:cacheprovider $EXTRA tests/$f > $OUT/$name.txt 2>&1
  echo "$f :: $(tail -1 $OUT/$name.txt)" >> $OUT/_summary.txt
done
echo DONE >> $OUT/_summary.txt
