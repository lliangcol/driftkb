from __future__ import annotations

from pathlib import Path

from driftkb.adapters.enterprise_java import EnterpriseJavaAdapter
from driftkb.adapters.java import JavaRegexAdapter
from driftkb.adapters.registry import build_adapters
from driftkb.fingerprints.snapshots import compare_fingerprint


def test_enterprise_java_adapter_extracts_risk_fingerprints(tmp_path: Path) -> None:
    source = _write_enterprise_source(tmp_path)

    fingerprint = EnterpriseJavaAdapter().extract(source, tmp_path)
    risks = fingerprint.metadata["risk_fingerprints"]

    assert fingerprint.adapter == "enterprise-java"
    assert "com.example.payment.PaymentConsumer" in fingerprint.symbols
    assert risks["fqcn"] == ["com.example.payment.PaymentConsumer"]
    assert risks["ds"] == ['@DS("order")']
    assert risks["transactional"] == ["@Transactional(rollbackFor = Exception.class)"]
    assert risks["rocketmq_listeners"] == ['@RocketMQMessageListener(topic = "pay-topic", consumerGroup = "pay-group")']
    assert risks["xxl_jobs"] == ['@XxlJob("payJob")']
    assert risks["logic_exceptions"] == ["DomainError.PAY_FAILED"]
    assert risks["rocketmq_senders"] == [
        {
            "target": "rocketMQTemplate",
            "method": "syncSend",
            "args": '"pay-result", message',
        }
    ]


def test_enterprise_java_semantic_fingerprint_changes_for_logic_exception(tmp_path: Path) -> None:
    source = _write_enterprise_source(tmp_path)
    adapter = EnterpriseJavaAdapter()
    original = adapter.extract(source, tmp_path)

    source.write_text(
        source.read_text(encoding="utf-8").replace("DomainError.PAY_FAILED", "DomainError.PAY_TIMEOUT"),
        encoding="utf-8",
    )
    changed = adapter.extract(source, tmp_path)

    assert original.raw_hash != changed.raw_hash
    assert not compare_fingerprint(changed, original)


def test_enterprise_java_semantic_fingerprint_ignores_whitespace_only_body_changes(tmp_path: Path) -> None:
    source = _write_enterprise_source(tmp_path)
    adapter = EnterpriseJavaAdapter()
    original = adapter.extract(source, tmp_path)

    source.write_text(
        source.read_text(encoding="utf-8").replace(
            'rocketMQTemplate.syncSend("pay-result", message);',
            'rocketMQTemplate.syncSend(\n            "pay-result",\n            message\n        );',
        ),
        encoding="utf-8",
    )
    changed = adapter.extract(source, tmp_path)

    assert original.raw_hash != changed.raw_hash
    assert compare_fingerprint(changed, original)


def test_java_adapter_does_not_switch_to_enterprise_behavior_by_default(tmp_path: Path) -> None:
    source = _write_enterprise_source(tmp_path)

    fingerprint = JavaRegexAdapter().extract(source, tmp_path)

    assert fingerprint.adapter == "java"
    assert "risk_fingerprints" not in fingerprint.metadata


def test_registry_builds_enterprise_java_only_when_configured() -> None:
    assert [adapter.name for adapter in build_adapters(("generic",))] == ["generic"]
    assert [adapter.name for adapter in build_adapters(("enterprise-java",))] == ["enterprise-java"]
    assert [adapter.name for adapter in build_adapters(("enterprise_java",))] == ["enterprise-java"]


def _write_enterprise_source(tmp_path: Path) -> Path:
    source = tmp_path / "src" / "main" / "java" / "com" / "example" / "payment" / "PaymentConsumer.java"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
package com.example.payment;

import com.baomidou.dynamic.datasource.annotation.DS;
import com.example.errors.DomainError;
import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQTemplate;
import org.springframework.transaction.annotation.Transactional;
import com.xxl.job.core.handler.annotation.XxlJob;

@DS("order")
@RocketMQMessageListener(topic = "pay-topic", consumerGroup = "pay-group")
public class PaymentConsumer {
    private RocketMQTemplate rocketMQTemplate;

    @Transactional(rollbackFor = Exception.class)
    @XxlJob("payJob")
    public void consume(String message) {
        rocketMQTemplate.syncSend("pay-result", message);
        throw new LogicException(DomainError.PAY_FAILED);
    }
}
""".lstrip(),
        encoding="utf-8",
    )
    return source
