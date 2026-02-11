package research

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	"github.com/ayush/research-ai-agent/backend/internal/models"
)

// DepthConfig maps depth names to query/result counts.
var DepthConfig = map[string][2]int{
	"Quick":    {2, 3},
	"Standard": {4, 5},
	"Deep":     {6, 7},
}

// checkResp reads the response body and returns an error if the status is not 2xx.
// On error it includes the upstream body for debugging.
func checkResp(resp *http.Response, service, path string) error {
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		return nil
	}
	body, _ := io.ReadAll(resp.Body)
	return fmt.Errorf("%s %s returned %d: %s", service, path, resp.StatusCode, string(body))
}

// ---------------------------------------------------------------------------
// AIClient — calls the Python AI service (generate-queries, search, report)
// ---------------------------------------------------------------------------

// AIClient calls the Python AI service over HTTP.
type AIClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewAIClient(baseURL string) *AIClient {
	return &AIClient{baseURL: strings.TrimRight(baseURL, "/"), httpClient: &http.Client{}}
}

// GenerateQueries calls POST /api/generate-queries.
func (c *AIClient) GenerateQueries(apiKey, model, topic string) ([]string, error) {
	body, _ := json.Marshal(map[string]string{
		"api_key": apiKey, "model": model, "topic": topic,
	})
	resp, err := c.post("/api/generate-queries", body)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if err := checkResp(resp, "ai-service", "/api/generate-queries"); err != nil {
		return nil, err
	}

	var result struct {
		Queries []string `json:"queries"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("ai-service /api/generate-queries: decode: %w", err)
	}
	return result.Queries, nil
}

// Search calls POST /api/search.
func (c *AIClient) Search(queries []string, resultsPerQuery int) ([]models.Source, error) {
	body, _ := json.Marshal(map[string]interface{}{
		"queries": queries, "results_per_query": resultsPerQuery,
	})
	resp, err := c.post("/api/search", body)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if err := checkResp(resp, "ai-service", "/api/search"); err != nil {
		return nil, err
	}

	var result struct {
		Results []models.Source `json:"results"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("ai-service /api/search: decode: %w", err)
	}
	return result.Results, nil
}

// GenerateReport calls POST /api/generate-report.
func (c *AIClient) GenerateReport(apiKey, model, topic, context string, sources []models.Source) (string, error) {
	body, _ := json.Marshal(map[string]interface{}{
		"api_key": apiKey, "model": model, "topic": topic,
		"context": context, "sources": sources,
	})
	resp, err := c.post("/api/generate-report", body)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if err := checkResp(resp, "ai-service", "/api/generate-report"); err != nil {
		return "", err
	}

	var result struct {
		LatexBody string `json:"latex_body"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("ai-service /api/generate-report: decode: %w", err)
	}
	return result.LatexBody, nil
}

func (c *AIClient) post(path string, body []byte) (*http.Response, error) {
	resp, err := c.httpClient.Post(
		c.baseURL+path,
		"application/json",
		bytes.NewReader(body),
	)
	if err != nil {
		return nil, fmt.Errorf("ai-service %s: %w", path, err)
	}
	return resp, nil
}

// ---------------------------------------------------------------------------
// LaTeXClient — calls the LaTeX compilation service (compile-pdf, compile-tex)
// ---------------------------------------------------------------------------

// LaTeXClient calls the Python LaTeX service over HTTP.
type LaTeXClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewLaTeXClient(baseURL string) *LaTeXClient {
	return &LaTeXClient{baseURL: strings.TrimRight(baseURL, "/"), httpClient: &http.Client{}}
}

// CompilePDF calls POST /api/compile-pdf and returns raw PDF bytes.
func (c *LaTeXClient) CompilePDF(latexBody, title string) ([]byte, error) {
	body, _ := json.Marshal(map[string]string{
		"latex_body": latexBody, "title": title,
	})
	resp, err := c.post("/api/compile-pdf", body)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if err := checkResp(resp, "latex-service", "/api/compile-pdf"); err != nil {
		return nil, err
	}
	return io.ReadAll(resp.Body)
}

// CompileTex calls POST /api/compile-tex and returns the .tex source.
func (c *LaTeXClient) CompileTex(latexBody, title string) (string, error) {
	body, _ := json.Marshal(map[string]string{
		"latex_body": latexBody, "title": title,
	})
	resp, err := c.post("/api/compile-tex", body)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if err := checkResp(resp, "latex-service", "/api/compile-tex"); err != nil {
		return "", err
	}

	var result struct {
		TexSource string `json:"tex_source"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("latex-service /api/compile-tex: decode: %w", err)
	}
	return result.TexSource, nil
}

func (c *LaTeXClient) post(path string, body []byte) (*http.Response, error) {
	resp, err := c.httpClient.Post(
		c.baseURL+path,
		"application/json",
		bytes.NewReader(body),
	)
	if err != nil {
		return nil, fmt.Errorf("latex-service %s: %w", path, err)
	}
	return resp, nil
}
