package change_approval

# ==========================================
# Mock Data Generators
# ==========================================

mock_evidence(id, source, target_id, target_version, target_hash) = {
    "id": id,
    "source": source,
    "type": "incident",
    "timestamp": "2026-08-04T12:00:00Z",
    "target_id": target_id,
    "target_version": target_version,
    "target_hash": target_hash,
    "weight": 40,
    "age_hours": 1
}

mock_input(risk, irreversible, target_id, target_version, target_hash, evidence_list, approvals) = {
    "action": {
        "risk_level": risk,
        "irreversible": irreversible,
        "target_id": target_id,
        "target_version": target_version,
        "target_hash": target_hash
    },
    "confirmation": true,
    "confirmation_source": "user",
    "confirmation_target_id": target_id,
    "confirmation_target_version": target_version,
    "confirmation_target_hash": target_hash,
    "inference": {
        "evidence": evidence_list
    },
    "approvals": approvals
}

# ==========================================
# Test Cases
# ==========================================

# 1. 成功测试：Critical 等级，具备强交叉验证与双人审批
test_allow_critical_dual_approval {
    evidence := [
        mock_evidence("INC-1001", "ticket_system", "db-prod-01", "v100", "sha256:abc123"),
        mock_evidence("ALM-2001", "monitoring", "db-prod-01", "v100", "sha256:abc123"),
        mock_evidence("LOG-3001", "log_system", "db-prod-01", "v100", "sha256:abc123")
    ]
    approvals := ["userA", "userB"]
    input_data := mock_input("critical", true, "db-prod-01", "v100", "sha256:abc123", evidence, approvals)
    
    allow with input as input_data
}

# 2. 失败测试：Critical 等级，缺少双人审批
test_deny_critical_missing_dual_approval {
    evidence := [
        mock_evidence("INC-1001", "ticket_system", "db-prod-01", "v100", "sha256:abc123"),
        mock_evidence("ALM-2001", "monitoring", "db-prod-01", "v100", "sha256:abc123"),
        mock_evidence("LOG-3001", "log_system", "db-prod-01", "v100", "sha256:abc123")
    ]
    approvals := ["userA"] # 仅1人审批
    input_data := mock_input("critical", true, "db-prod-01", "v100", "sha256:abc123", evidence, approvals)
    
    not allow with input as input_data
}

# 3. 失败测试：TOCTOU 防御（审批版本 v100，执行版本 v138）
test_deny_toctou_version_mismatch {
    evidence := [
        mock_evidence("INC-1001", "ticket_system", "db-prod-01", "v100", "sha256:abc123")
    ]
    # 用户确认的是 v100
    approvals := ["userA"]
    
    # 构造攻击请求：action 中的 target_version 被篡改为 v138
    input_data := {
        "action": {
            "risk_level": "low",
            "irreversible": false,
            "target_id": "db-prod-01",
            "target_version": "v138",
            "target_hash": "sha256:abc123"
        },
        "confirmation": true,
        "confirmation_source": "user",
        "confirmation_target_id": "db-prod-01",
        "confirmation_target_version": "v100", # 用户当初确认的版本
        "confirmation_target_hash": "sha256:abc123",
        "inference": {
            "evidence": evidence
        },
        "approvals": approvals
    }
    
    not allow with input as input_data
}

# 4. 失败测试：证据链分裂 (Evidence Splicing)
test_deny_evidence_splicing {
    evidence := [
        mock_evidence("INC-1001", "ticket_system", "db-prod-01", "v100", "sha256:abc123"),
        mock_evidence("ALM-2001", "monitoring", "db-prod-02", "v100", "sha256:abc123") # 恶意混入另一台DB的证据
    ]
    approvals := ["userA"]
    input_data := mock_input("high", false, "db-prod-01", "v100", "sha256:abc123", evidence, approvals)
    
    not allow with input as input_data
}

# 5. 成功测试：High 等级，单人审批+交叉验证
test_allow_high_cross_verified {
    evidence := [
        mock_evidence("INC-1001", "ticket_system", "db-prod-01", "v100", "sha256:abc123"),
        mock_evidence("ALM-2001", "monitoring", "db-prod-01", "v100", "sha256:abc123")
    ]
    approvals := ["userA"]
    input_data := mock_input("high", false, "db-prod-01", "v100", "sha256:abc123", evidence, approvals)
    
    allow with input as input_data
}

# 6. 失败测试：Systemic 风险直接拒绝
test_deny_systemic_risk {
    evidence := [
        mock_evidence("INC-1001", "ticket_system", "db-prod-01", "v100", "sha256:abc123")
    ]
    approvals := ["userA", "userB", "userC"]
    input_data := mock_input("systemic", true, "db-prod-01", "v100", "sha256:abc123", evidence, approvals)
    
    not allow with input as input_data
}
