package harness

import "time"

// RunBudget defines hard limits that keep an agent run bounded.
type RunBudget struct {
	MaxIterations int
	MaxToolCalls  int
	MaxDuration   time.Duration
}

// RunUsage captures counters consumed by an agent run.
type RunUsage struct {
	Iterations int
	ToolCalls  int
	StartedAt  time.Time
}

// Check returns whether the run can continue under the configured budget.
func (b RunBudget) Check(usage RunUsage) (StopReason, bool) {
	if b.MaxIterations > 0 && usage.Iterations >= b.MaxIterations {
		return StopReasonBudgetExceeded, false
	}
	if b.MaxToolCalls > 0 && usage.ToolCalls >= b.MaxToolCalls {
		return StopReasonBudgetExceeded, false
	}
	if b.MaxDuration > 0 && !usage.StartedAt.IsZero() && time.Since(usage.StartedAt) >= b.MaxDuration {
		return StopReasonTimeout, false
	}
	return StopReasonNone, true
}
