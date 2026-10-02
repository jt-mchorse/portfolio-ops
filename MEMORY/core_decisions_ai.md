# Core Decisions (AI-readable, YAML, append-only)
# Schema: see .skills/portfolio-memory/SKILL.md

- id: D-001
  date: 2026-05-10
  decision: scope_per_portfolio_handoff_section_2
  rationale: locked_scope_prevents_drift
  alternatives_rejected: []
  reversibility: expensive
  related_issues: []
  superseded_by: D-003

- id: D-002
  # superseded by D-003
  date: 2026-05-10
  decision: stub_trending_scripts_at_bootstrap_implement_in_session_one
  rationale: handoff_forbids_pretending_things_work_section_10_no_fabricated_benchmarks
  alternatives_rejected: [implement_full_scanner_during_bootstrap, omit_workflows_entirely]
  reversibility: cheap
  related_issues: []
  superseded_by: D-003

# D-002 superseded
- id: D-003
  date: 2026-05-11
  decision: real_trending_scripts_implemented_using_stdlib_only
  rationale: bootstrap_proceeds_to_functional_state_per_user_followup_request
  alternatives_rejected: [keep_stubs_and_defer, use_external_deps_anthropic_sdk_feedparser]
  reversibility: cheap
  related_issues: []
  superseded_by: null

- id: D-004
  date: 2026-05-13
  decision: scheduled_sessions_review_and_merge_ready_prs
  rationale: jt_explicitly_overrode_section_10_for_velocity_drafts_still_protected
  alternatives_rejected: [keep_full_human_in_loop, auto_merge_all_prs_ignoring_draft_status]
  reversibility: cheap
  related_issues: []
  superseded_by: null

- id: D-005
  date: 2026-05-13
  decision: execution_via_claude_code_on_local_mac_not_cowork_sandbox
  rationale: cowork_bash_is_sandboxed_no_gh_auth_propagation_jt_requested_full_use_of_granted_permissions
  alternatives_rejected: [stay_in_cowork_sandbox_with_baked_in_pat, switch_entire_workflow_to_claude_code_only]
  reversibility: cheap
  related_issues: []
  superseded_by: null

- id: D-006
  date: 2026-05-13
  decision: fifteen_minute_minimum_per_issue
  rationale: sessions_under_15_min_with_only_a_5_line_tweak_were_a_failure_mode_pick_next_unblocked_issue_in_same_repo_instead_of_ending_early
  alternatives_rejected: [no_minimum_let_short_sessions_ship, longer_minimum_30_min]
  reversibility: cheap
  related_issues: [#5]   # retroactively captured 2026-05-27 in issue #5; live since commit 7690999 2026-05-13
  superseded_by: null

- id: D-007
  date: 2026-05-13
  decision: fall_through_to_next_repo_when_chosen_repo_is_one_way_blocked
  rationale: three_consecutive_runs_bailed_on_agent_orchestration_platform_because_issue_1_was_a_one_way_blocker_skip_blocked_repo_and_try_next_best_up_to_three_fall_throughs_per_session
  alternatives_rejected: [end_session_when_blocked, require_jt_intervention_every_time]
  reversibility: cheap
  related_issues: [#5]   # retroactively captured 2026-05-27 in issue #5; live since commit 4670bd0 2026-05-13
  superseded_by: null

- id: D-008
  date: 2026-05-14
  decision: time_of_day_session_caps_day_180min_night_360min_multi_issue_loop
  rationale: jt_observed_27pct_limit_usage_per_session_wants_fuller_utilization
  alternatives_rejected: [uniform_longer_cap, more_frequent_short_sessions]
  reversibility: cheap
  related_issues: []
  superseded_by: null

- id: D-009
  date: 2026-06-17
  decision: priority_tier_of_5_repos_worked_more_often
  priority_tier_repos: [llm-cost-optimizer, llm-eval-harness, rag-production-kit, chunking-strategies-lab, nextjs-streaming-ai-patterns]
  mechanism: tighter_freshness_floor_18h_vs_36h_plus_win_all_tie_breaks_plus_multi_issue_loop_bias
  rationale: jt_requested_these_5_be_updated_more_often_than_the_other_8_which_remain_worked_just_deprioritized
  alternatives_rejected: [exclusive_focus_only_these_5, equal_cadence_for_all_13]
  reversibility: cheap
  related_issues: []
  superseded_by: null
  # note: jt wrote "next-js-streaming-ai-patterns"; canonical repo is nextjs-streaming-ai-patterns

- id: D-010
  date: 2026-08-26
  decision: followups_items_are_quoted_strings_in_full_history_ai_yaml_blocks
  rationale: hash_begins_a_yaml_comment_when_it_follows_whitespace_or_opens_a_token_so_an_unquoted_followups_bracket_hash_107_is_an_unterminated_flow_sequence_that_makes_the_WHOLE_session_block_fail_yaml_safe_load_74_of_953_blocks_across_the_portfolio_are_already_in_that_state_and_handoff_section_3_calls_this_file_ai_optimized_for_fast_machine_parsing_QUOTE_EVERY_ITEM_not_only_the_bare_hash_ones_because_the_narrow_rule_quote_only_when_it_starts_with_hash_is_correct_and_unmemorable_while_quote_everything_is_a_superset_with_no_exceptions
  scope: new_blocks_only_the_retro_fix_of_the_existing_74_is_explicitly_NOT_decided_here_and_remains_jt_gated_per_handoff_section_10_append_only
  measured: "953 followups lines: 866 empty and parsing, 74 bare-#NNN and failing; 72 of the 74 unparseable blocks are fixed by quoting the followups items alone; [leh#212] and [csl#165, aiapp#102] ALREADY parse because # follows a letter there"
  alternatives_rejected: [drop_the_hash_followups_bracket_107, leave_it_and_delete_the_machine_parsing_claim_from_the_handoff, quote_only_items_beginning_with_hash]
  reversibility: cheap
  related_issues: [#66, #65]
  superseded_by: null

- id: D-011
  date: 2026-09-28
  decision: audit_phase_a_gains_a_NINTH_fingerprint_timeout_headroom_which_flags_a_RUNTIME_job_whose_WORST_of_the_newest_five_completed_push_runs_on_the_default_branch_consumed_at_least_0_8_of_the_timeout_minutes_ITS_OWN_YAML_JOB_DECLARES
  rationale: fingerprint_5_missing_timeout_asks_whether_a_job_HAS_a_cap_and_NEVER_whether_the_cap_HAS_ANY_ROOM_LEFT_so_a_job_sitting_at_99_percent_audits_CLEAN_EVERY_SESSION_until_the_day_it_crosses_WHICH_IS_THE_SILENT_ROT_SHAPE_THIS_WHOLE_SCRIPT_EXISTS_FOR
  measured_before_writing_any_code: "llm-cost-optimizer test (3.12) against its 15m cap, newest ten push runs on main: 09-28 15m10s 1.01 CANCELLED, 09-23 10m48s 0.72, 09-22 15m05s 1.00 CANCELLED, 09-21 14m05s 0.94, 09-14 13m12s 0.88, 09-11 10m48s 0.72, 09-10 13m17s 0.89, 09-09 13m10s 0.88, 09-08 14m32s 0.97, 09-07 13m22s 0.89. RATIO >= 0.88 IN EIGHT OF TEN so the finding is robust to WHICH run lands in the window. The 09-28 cancellation was caused BY THIS SESSIONS OWN PHASE A MERGE of lco#228."
  AND_THE_PER_STEP_BREAKDOWN_IS_WHAT_ANSWERS_RAISE_VS_FIX: "run 36390509795 test (3.12): setup 1+1+4s, pip install 23s, pytest --cov 877s of a 910s job. Install and teardown are 29s. The suite is ~38s locally, so the CI figure is a 2-core runner plus coverage, NOT a regression - a cap of 15 was never sized from a measurement."
  THE_UNIT_IS_THE_RUNTIME_JOB_NOT_THE_YAML_JOB: a_matrix_expands_ONE_yaml_block_into_N_runtime_jobs_and_it_is_a_RUNTIME_job_that_gets_cancelled_lco_has_ONE_test_block_at_15m_that_becomes_test_3_11_and_test_3_12_and_ONLY_ONE_OF_THE_TWO_IS_ANYWHERE_NEAR_THE_CAP_10m54s_vs_15m10s_A_RULE_KEYED_ON_THE_YAML_JOB_WOULD_REPORT_BOTH_measured_the_strip_the_matrix_suffix_neighbour_at_8_RED
  KEYED_ON_THE_RATIO_NOT_ON_THE_CONCLUSION_AND_THAT_IS_WHAT_MAKES_IT_COEXIST_WITH_missing_concurrency: D_005s_fingerprint_6_pushes_EVERY_repo_toward_cancel_in_progress_true_whose_SUPERSEDED_runs_are_cancelled_WITH_A_SHORT_DURATION_so_a_conclusion_keyed_rule_would_FLAG_EXACTLY_THE_BEHAVIOUR_ITS_SIBLING_ASKS_FOR_measured_the_conclusion_keyed_neighbour_at_5_RED_the_honest_residue_is_that_a_superseded_run_cancelled_at_14_of_15_MINUTES_still_trips_because_from_outside_it_is_indistinguishable_SAID_IN_THE_DOCSTRING_rather_than_left_to_read_as_a_bug
  AN_UNRESOLVABLE_RUNTIME_NAME_IS_COUNTED_NOT_GUESSED: a_yaml_name_interpolating_matrix_values_renders_to_something_the_default_suffix_rule_CANNOT_INVERT_so_resolve_job_timeout_returns_None_and_the_COUNT_rides_on_every_finding_the_workflow_does_produce_A_WRONG_LABEL_IS_WORSE_THAN_A_MISSING_ONE_because_it_attaches_a_duration_to_SOME_OTHER_JOBS_CAP
  THE_MODULE_DOCSTRING_ALREADY_SAID_SEVEN_WHILE_audit_repo_RAN_EIGHT: main_branch_red_was_wired_in_for_69_WITHOUT_being_added_to_the_numbered_list_A_PROSE_COUNT_BESIDE_A_LITERAL_THAT_NOBODY_COMPARED_which_is_the_fingerprint_shaped_defect_THIS_MODULE_EXISTS_TO_CATCH_IN_ITS_OWN_DOCSTRING_fixed_and_now_test_the_docstring_lists_every_wired_check_DERIVES_both_sets_and_compares_them_so_a_TENTH_landing_the_same_way_fails_immediately
  THE_REPOS_OWN_LOCKS_FIRED_EXACTLY_AS_DESIGNED_AND_THAT_IS_WORTH_RECORDING: test_fingerprints_list_matches_the_script_AND_test_every_fingerprint_kind_in_the_audit_has_a_declared_identity_BOTH_went_red_the_moment_the_check_was_wired_naming_SESSION_PROMPT_md_and_IDENTITY_FIELDS_respectively_THREE_PLACES_BY_DESIGN_copy_that_pattern
  THE_IDENTITY_IS_repo_workflow_path_job_name_AND_EVERY_VOLATILE_FIELD_IS_EXCLUDED: worst_seconds_ratio_conclusion_run_url_and_runs_inspected_ALL_MOVE_ON_EVERY_PUSH_and_the_FINDING_is_this_job_has_no_room_left_in_its_cap_which_is_named_by_the_JOB_not_by_how_close_it_got_this_week_INCLUDING_ANY_OF_THEM_WOULD_MAKE_THE_CRON_RE_FILE_WEEKLY
  SWEPT_ALL_13_REPOS_ONCE_AND_THE_RESULT_IS_ONE_FINDING: only_llm_cost_optimizer_leh_runs_a_4_way_matrix_and_aop_runs_Postgres_integration_and_BOTH_CAME_BACK_CLEAN_which_the_issue_named_as_plausible_neighbours_A_CLEAN_SWEEP_IS_A_RESULT_do_not_re_run_it
  THE_3_11_VS_3_12_DIVERGENCE_IS_RECORDED_AS_UNEXPLAINED_WITH_THE_MEASUREMENT_ATTACHED: "3.12 is slower in 6 of 6 paired runs (sign test p ~ 0.031, so the DIRECTION is real) but the MAGNITUDE ranges from 5 SECONDS on 09-23 (612s vs 624s) to 8m45s on 09-21 (320s vs 845s) on comparable trees. Runner variance dominates and a systematic component CANNOT BE SIZED FROM SIX POINTS. Recording the unexplained branch WITH the data beats inventing a cause."
  alternatives_rejected: ["FLAG_ON_THE_CONCLUSION_cancelled_REJECTED_BUILT_AND_RUN_5_RED_it_flags_the_cancel_in_progress_behaviour_fingerprint_6_asks_every_repo_to_adopt", "REPORT_THE_NEWEST_RUN_RATHER_THAN_THE_WORST_REJECTED_BUILT_AND_RUN_2_RED_lco_went_15m05s_CANCELLED_on_09_22_and_10m48s_on_09_23_so_the_newest_would_have_called_it_clean_THE_DAY_AFTER", "KEY_ON_THE_YAML_JOB_REJECTED_BUILT_AND_RUN_8_RED_it_reports_test_3_11_at_0_73_alongside_test_3_12_at_1_01", "GUESS_A_LABEL_FOR_AN_UNRESOLVABLE_MATRIX_NAME_REJECTED_a_wrong_label_attaches_a_duration_to_another_jobs_cap", "RAISE_lcos_CAP_IN_THIS_PR_DEFERRED_TO_lco_229_a_different_repo_with_its_own_review_surface_and_the_issues_own_Proposed_section_splits_it_that_way"]
  measured: "ops suite 278 -> 295 green (17 new arms); anti-vacuity by unwiring check_timeout_headroom from audit_repo = 2 red (the docstring/wiring lock AND a behavioural arm through audit_repo - the direct-call arms are all green there, which is the llm-cost-optimizer#227 vacuity shape and is why the behavioural arm exists); four neighbours built and run, all rejected; live sweep over all 13 repos = 1 new finding"
  reversibility: cheap
  related_issues: ["#76", "#35", "#40", "#69", "#63"]
  superseded_by: null

- id: D-012
  date: 2026-10-02
  decision: check_timeout_headroom_EMITS_A_SECOND_KIND_timeout_headroom_unresolved_IDENTITY_repo_workflow_path_FOR_A_WORKFLOW_WITH_UNRESOLVABLE_RUNTIME_JOB_NAMES_AND_NO_HEADROOM_FINDING_TO_CARRY_THE_COUNT
  rationale: D_011_promised_the_unresolved_count_RIDES_ON_EVERY_FINDING_so_a_matcher_that_resolves_nothing_CANNOT_LOOK_LIKE_A_CLEAN_REPO_but_a_workflow_where_nothing_resolved_PRODUCED_NO_FINDING_and_audited_clean_rc_0_with_a_job_at_99_percent_of_its_cap
  WHY_A_NEW_KIND_NOT_A_timeout_headroom_FINDING: timeout_headroom_MEANS_THIS_JOB_HAS_NO_ROOM_LEFT_and_its_identity_is_the_JOB_an_unresolved_workflow_has_no_resolved_job_and_its_finding_means_THE_AUDIT_CANNOT_WATCH_THESE_JOBS_a_different_claim_with_a_different_identity
  NO_DOUBLE_REPORT: a_workflow_that_already_has_a_headroom_finding_carries_the_count_there_and_gets_no_second_line
  LIVE: latent_no_portfolio_workflow_interpolates_a_job_name_today_spot_checked_lco_leh_mcp_clean
  alternatives_rejected: ["A_STDERR_NOTE_REJECTED_rc_0_and_clean_would_still_be_printed", "A_timeout_headroom_FINDING_WITH_A_PLACEHOLDER_job_name_REJECTED_it_asserts_a_cap_overrun_nobody_measured", "GUESS_THE_LABEL_REJECTED_by_D_011_already_a_wrong_label_attaches_a_duration_to_another_jobs_cap"]
  measured: "issue repro (Test ${{ matrix.python }}, 99% of 15m) -> before: [] and 'clean' rc 0; after: one timeout-headroom-unresolved finding, rc 1. Revert 2 of 5 red."
  reversibility: cheap
  related_issues: ["#84", "#76"]
  superseded_by: null
