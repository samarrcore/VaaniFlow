-- ==============================================================================
-- VaaniFlow Sales AI & Evaluation Harness SQL Analysis Queries
-- Database: vaaniflow_evals.db
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. PROMPT VERSION BENCHMARK COMPARISON
-- Compares overall pass rates and individual criterion pass rates across prompts.
-- ------------------------------------------------------------------------------
SELECT 
    c.prompt_version,
    COUNT(c.id) AS total_evaluated_calls,
    ROUND(AVG(s.overall_pass_rate) * 100, 1) AS overall_pass_pct,
    ROUND(AVG(s.stayed_in_character) * 100, 1) AS in_character_pct,
    ROUND(AVG(s.replies_short_spoken) * 100, 1) AS short_spoken_pct,
    ROUND(AVG(s.language_matched) * 100, 1) AS lang_matched_pct,
    ROUND(AVG(s.handled_objection) * 100, 1) AS objection_handled_pct,
    ROUND(AVG(s.achieved_goal) * 100, 1) AS goal_achieved_pct,
    ROUND(AVG(s.no_false_claims_or_pressure) * 100, 1) AS anti_hallucination_pct
FROM conversations c
JOIN eval_scores s ON c.id = s.conversation_id
GROUP BY c.prompt_version
ORDER BY overall_pass_pct DESC;


-- ------------------------------------------------------------------------------
-- 2. PERFORMANCE BREAKDOWN BY SCENARIO CATEGORY
-- Compares prompt resilience on edge cases (hallucination bait, rude, price sensitive, etc.)
-- ------------------------------------------------------------------------------
SELECT 
    c.category,
    c.prompt_version,
    COUNT(c.id) AS category_calls,
    ROUND(AVG(s.overall_pass_rate) * 100, 1) AS pass_pct,
    ROUND(AVG(s.no_false_claims_or_pressure) * 100, 1) AS anti_hallucination_pct,
    ROUND(AVG(s.handled_objection) * 100, 1) AS objection_handling_pct
FROM conversations c
JOIN eval_scores s ON c.id = s.conversation_id
GROUP BY c.category, c.prompt_version
ORDER BY c.category, c.prompt_version;


-- ------------------------------------------------------------------------------
-- 3. WORST-PERFORMING SCENARIOS (FAILURE HUNTING)
-- Identifies scenarios with lowest pass rates to guide prompt engineering iterations.
-- ------------------------------------------------------------------------------
SELECT 
    c.scenario_id,
    c.scenario_name,
    c.category,
    COUNT(c.id) AS attempts,
    ROUND(AVG(s.overall_pass_rate) * 100, 1) AS avg_pass_pct,
    SUM(CASE WHEN s.replies_short_spoken = 0 THEN 1 ELSE 0 END) AS length_fails,
    SUM(CASE WHEN s.no_false_claims_or_pressure = 0 THEN 1 ELSE 0 END) AS hallucination_fails,
    SUM(CASE WHEN s.handled_objection = 0 THEN 1 ELSE 0 END) AS objection_fails
FROM conversations c
JOIN eval_scores s ON c.id = s.conversation_id
GROUP BY c.scenario_id, c.scenario_name, c.category
HAVING avg_pass_pct < 100.0
ORDER BY avg_pass_pct ASC, hallucination_fails DESC;


-- ------------------------------------------------------------------------------
-- 4. CONVERSATION STOP REASON DISTRIBUTION
-- Analyzes how conversations ended (agreed visit, refused twice, hangup, turn cap).
-- ------------------------------------------------------------------------------
SELECT 
    c.prompt_version,
    c.stop_reason,
    COUNT(c.id) AS call_count,
    ROUND(COUNT(c.id) * 100.0 / SUM(COUNT(c.id)) OVER(PARTITION BY c.prompt_version), 1) AS pct_of_version_calls,
    ROUND(AVG(c.total_customer_turns), 1) AS avg_customer_turns
FROM conversations c
GROUP BY c.prompt_version, c.stop_reason
ORDER BY c.prompt_version, call_count DESC;


-- ------------------------------------------------------------------------------
-- 5. ANTI-HALLUCINATION / BAIT SCENARIO DEEP-DIVE
-- Specifically filters for bait scenarios (swimming pool, car parking, 50% discount).
-- ------------------------------------------------------------------------------
SELECT 
    c.prompt_version,
    c.scenario_id,
    c.scenario_name,
    s.no_false_claims_or_pressure,
    s.judge_reasoning
FROM conversations c
JOIN eval_scores s ON c.id = s.conversation_id
WHERE c.category = 'hallucination_bait'
ORDER BY c.scenario_id, c.prompt_version;


-- ------------------------------------------------------------------------------
-- 6. RULE VIOLATIONS AUDIT LOG
-- Inspects exact turn numbers and violation messages where deterministic checks failed.
-- ------------------------------------------------------------------------------
SELECT 
    c.id AS conv_id,
    c.prompt_version,
    c.scenario_id,
    s.rule_violations
FROM conversations c
JOIN eval_scores s ON c.id = s.conversation_id
WHERE s.replies_short_spoken = 0 AND s.rule_violations != ''
LIMIT 20;
