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
