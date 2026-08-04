package change_approval

default allow = false

# ==========================================
# 1. 风险等级定义 & 审批要求
# ==========================================

allow {
    not deny
    risk_level == "low"
    valid_confirmation
    valid_evidence
}

allow {
    not deny
    risk_level == "medium"
    valid_confirmation
    valid_evidence
}

allow {
    not deny
    risk_level == "high"
    valid_confirmation
    valid_evidence
    cross_verified
}

allow {
    not deny
    risk_level == "critical"
    valid_confirmation
    valid_critical_risk_evidence
}

# ==========================================
# 2. 系统级风险禁止执行
# ==========================================
deny {
    irreversible_action
    systemic_risk
}

irreversible_action {
    input.action.irreversible == true
}

systemic_risk {
    input.action.risk_level == "systemic"
}

risk_level = input.action.risk_level

# ==========================================
# 3. 用户确认与绑定对象
# ==========================================
valid_confirmation {
    input.confirmation == true
    input.confirmation_source == "user"
    confirmation_matches_target
}

confirmation_matches_target {
    input.confirmation_target_id == input.action.target_id
    input.confirmation_target_version == input.action.target_version
    input.confirmation_target_hash == input.action.target_hash
}

# ==========================================
# 4. Critical 风险增加双人审批
# ==========================================
dual_approval {
    count(input.approvals) >= 2
}

valid_critical_risk_evidence {
    valid_evidence
    strong_cross_verified
    dual_approval
}

# ==========================================
# 5. 证据存在性、结构完整性与时效性
# ==========================================
valid_evidence {
    count(input.inference.evidence) > 0
    all_evidence_valid
    all_evidence_match_target
}

all_evidence_valid {
    count({e | e := input.inference.evidence[_]; valid_evidence_structure(e)}) == count(input.inference.evidence)
}

valid_evidence_structure(e) {
    e.id != ""
    e.source != ""
    e.type != ""
    e.timestamp != ""
    e.target_id != ""
    e.target_version != ""
    e.target_hash != ""
    e.weight >= 0
    e.age_hours >= 0
}

cross_verified {
    count({e.source | e := input.inference.evidence[_]}) >= 2
}

strong_cross_verified {
    count({e.source | e := input.inference.evidence[_]}) >= 3
}

# ==========================================
# 6. 目标一致性校验 (防止 Evidence Splicing + TOCTOU)
# ==========================================
unique_target_ids := {
    e.target_id |
    e := input.inference.evidence[_]
}

unique_target_versions := {
    e.target_version |
    e := input.inference.evidence[_]
}

unique_target_hashes := {
    e.target_hash |
    e := input.inference.evidence[_]
}

single_target_chain {
    count(unique_target_ids) == 1
}

single_version_chain {
    count(unique_target_versions) == 1
}

single_hash_chain {
    count(unique_target_hashes) == 1
}

all_evidence_match_target {
    count(input.inference.evidence) > 0
    single_target_chain
    single_version_chain
    single_hash_chain

    unique_target_ids[input.action.target_id]
    unique_target_versions[input.action.target_version]
    unique_target_hashes[input.action.target_hash]
}
