package harness

import "testing"

func TestAgentStateRecordsEvidenceAndToolCalls(t *testing.T) {
	state := NewAgentState("inc-1", "分析 HighLatency 告警")

	state.AddEvidence(Evidence{
		ID:      "ev-1",
		Type:    EvidenceTypeRunbook,
		Source:  "docs/resource-community-p95-latency.md",
		Summary: "P95 延迟升高排障步骤",
		Score:   0.82,
	})
	state.RecordToolCall(ToolCallRecord{
		Name:   "query_prometheus_alerts",
		Status: ToolCallStatusSucceeded,
	})

	if len(state.Evidence) != 1 {
		t.Fatalf("expected 1 evidence item, got %d", len(state.Evidence))
	}
	if len(state.ToolCalls) != 1 {
		t.Fatalf("expected 1 tool call, got %d", len(state.ToolCalls))
	}
	if state.Usage.ToolCalls != 1 {
		t.Fatalf("expected usage tool calls to be 1, got %d", state.Usage.ToolCalls)
	}
}

func TestAgentStateStopsWithReason(t *testing.T) {
	state := NewAgentState("inc-1", "分析 HighErrorRate 告警")

	state.Stop(StopReasonInsufficientEvidence)

	if state.Status != RunStatusStopped {
		t.Fatalf("expected stopped status, got %q", state.Status)
	}
	if state.StopReason != StopReasonInsufficientEvidence {
		t.Fatalf("expected insufficient evidence, got %q", state.StopReason)
	}
}
