package tools

import (
	"context"
	"fmt"
	"reflect"

	"github.com/cloudwego/eino/components/retriever"
	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/components/tool/utils"
	"github.com/cloudwego/eino/schema"
)

// RAGTool 信息检索工具

type RetrieveRequest struct {
	Query string `json:"query" jsonschema:"description=The query string to search in internal documentation for relevant information and processing steps"`
}

func retrieveWith(docRetriever retriever.Retriever) func(context.Context, RetrieveRequest) ([]*schema.Document, error) {
	return func(ctx context.Context, query RetrieveRequest) ([]*schema.Document, error) {
		if isNilRetriever(docRetriever) {
			return nil, fmt.Errorf("rag retriever is not configured")
		}
		return docRetriever.Retrieve(ctx, query.Query)
	}
}

func isNilRetriever(docRetriever retriever.Retriever) bool {
	if docRetriever == nil {
		return true
	}

	value := reflect.ValueOf(docRetriever)
	switch value.Kind() {
	case reflect.Chan, reflect.Func, reflect.Interface, reflect.Map, reflect.Pointer, reflect.Slice:
		return value.IsNil()
	default:
		return false
	}
}

func RetrieveTool(docRetriever retriever.Retriever) (tool.InvokableTool, error) {
	return utils.InferTool("query_internal_docs",
		"Use this tool to search internal documentation and knowledge base for relevant information. It performs RAG (Retrieval-Augmented Generation) to find similar documents and extract processing steps. This is useful when you need to understand internal procedures, best practices, or step-by-step guides stored in the company's documentation.",
		retrieveWith(docRetriever))
}
