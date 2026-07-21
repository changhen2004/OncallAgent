package harness

import "time"

type RunStatus string

const (
	RunStatusRunning RunStatus = "running"
	RunStatusStopped RunStatus = "stopped"
)

type StopReason string

const (
	StopReasonNone                 StopReason = ""
	StopReasonCompleted            StopReason = "completed"
	StopReasonBudgetExceeded       StopReason = "budget_exceeded"
	StopReasonTimeout              StopReason = "timeout"
	StopReasonInsufficientEvidence StopReason = "insufficient_evidence"
	StopReasonToolFailure          StopReason = "tool_failure"
	StopReasonHumanApproval        StopReason = "human_approval_required"
)

// AgentState is the minimal shared state contract for Harness Engineering.
type AgentState struct {
	IncidentID string
	Goal       string
	Status     RunStatus
	StopReason StopReason
	Evidence   []Evidence
	ToolCalls  []ToolCallRecord
	Usage      RunUsage
	CreatedAt  time.Time
	UpdatedAt  time.Time
}

func NewAgentState(incidentID string, goal string) *AgentState {
	now := time.Now()
	return &AgentState{
		IncidentID: incidentID,
		Goal:       goal,
		Status:     RunStatusRunning,
		CreatedAt:  now,
		UpdatedAt:  now,
		Usage: RunUsage{
			StartedAt: now,
		},
	}
}

func (s *AgentState) AddEvidence(e Evidence) {
	if e.CreatedAt.IsZero() {
		e.CreatedAt = time.Now()
	}
	s.Evidence = append(s.Evidence, e)
	s.UpdatedAt = time.Now()
}

func (s *AgentState) RecordToolCall(record ToolCallRecord) {
	s.ToolCalls = append(s.ToolCalls, record)
	s.Usage.ToolCalls++
	s.UpdatedAt = time.Now()
}

func (s *AgentState) Stop(reason StopReason) {
	s.Status = RunStatusStopped
	s.StopReason = reason
	s.UpdatedAt = time.Now()
}
