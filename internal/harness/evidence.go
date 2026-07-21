package harness

import "time"

type EvidenceType string

const (
	EvidenceTypeAlert   EvidenceType = "alert"
	EvidenceTypeMetric  EvidenceType = "metric"
	EvidenceTypeLog     EvidenceType = "log"
	EvidenceTypeRunbook EvidenceType = "runbook"
	EvidenceTypeHistory EvidenceType = "history"
)

// Evidence is a compact, auditable context unit used by prompts and reports.
type Evidence struct {
	ID        string
	Type      EvidenceType
	Source    string
	Summary   string
	Score     float64
	CreatedAt time.Time
}

type ToolCallStatus string

const (
	ToolCallStatusSucceeded ToolCallStatus = "succeeded"
	ToolCallStatusFailed    ToolCallStatus = "failed"
	ToolCallStatusSkipped   ToolCallStatus = "skipped"
)

// ToolCallRecord stores a sanitized trace of a tool invocation.
type ToolCallRecord struct {
	Name      string
	Input     string
	Output    string
	Status    ToolCallStatus
	Error     string
	StartedAt time.Time
	EndedAt   time.Time
}
