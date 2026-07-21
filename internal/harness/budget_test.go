package harness

import (
	"testing"
	"time"
)

func TestRunBudgetAllowsWorkWithinLimits(t *testing.T) {
	budget := RunBudget{
		MaxIterations: 3,
		MaxToolCalls:  2,
		MaxDuration:   time.Minute,
	}
	usage := RunUsage{
		Iterations: 1,
		ToolCalls:  1,
		StartedAt:  time.Now(),
	}

	reason, ok := budget.Check(usage)
	if !ok {
		t.Fatalf("expected budget to allow work, got stop reason %q", reason)
	}
	if reason != StopReasonNone {
		t.Fatalf("expected no stop reason, got %q", reason)
	}
}

func TestRunBudgetStopsWhenIterationsExceeded(t *testing.T) {
	budget := RunBudget{MaxIterations: 3}
	usage := RunUsage{Iterations: 3}

	reason, ok := budget.Check(usage)
	if ok {
		t.Fatal("expected budget to stop when iterations reach max")
	}
	if reason != StopReasonBudgetExceeded {
		t.Fatalf("expected budget exceeded stop reason, got %q", reason)
	}
}

func TestRunBudgetStopsWhenToolCallsExceeded(t *testing.T) {
	budget := RunBudget{MaxToolCalls: 2}
	usage := RunUsage{ToolCalls: 2}

	reason, ok := budget.Check(usage)
	if ok {
		t.Fatal("expected budget to stop when tool calls reach max")
	}
	if reason != StopReasonBudgetExceeded {
		t.Fatalf("expected budget exceeded stop reason, got %q", reason)
	}
}

func TestRunBudgetStopsWhenDurationExceeded(t *testing.T) {
	budget := RunBudget{MaxDuration: time.Second}
	usage := RunUsage{StartedAt: time.Now().Add(-2 * time.Second)}

	reason, ok := budget.Check(usage)
	if ok {
		t.Fatal("expected budget to stop when duration is exceeded")
	}
	if reason != StopReasonTimeout {
		t.Fatalf("expected timeout stop reason, got %q", reason)
	}
}
