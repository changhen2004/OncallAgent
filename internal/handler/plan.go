package handler

import (
	planserver "OnCallAgent/internal/server/plan"

	"github.com/gin-gonic/gin"
)

// 运维handler

type Plan interface {
	Plan() gin.HandlerFunc
}

type plan struct {
	planServer planserver.PlanServer
}

func NewPlanHandler(planServer planserver.PlanServer) Plan {
	return &plan{planServer: planServer}
}

func (p *plan) Plan() gin.HandlerFunc {
	return func(ctx *gin.Context) {
		msg, msgs, err := p.planServer.Plan(ctx.Request.Context())
		if err != nil {
			ctx.JSON(500, gin.H{
				"message": "获取运维信息错误",
				"error":   err.Error(),
			})
			return
		}
		ctx.JSON(200, gin.H{
			"message": "获取运维信息成功",
			"data": gin.H{
				"lastmsg": msg,
				"msgs":    msgs,
			},
		})
	}
}
