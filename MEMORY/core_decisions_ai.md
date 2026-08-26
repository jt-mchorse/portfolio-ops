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
