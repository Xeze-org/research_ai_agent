package research

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/ayush/research-ai-agent/backend/internal/models"
)

// writeJSON writes a JSON response with the given status code.
func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

// ResearchStore defines the interface for research persistence.
type ResearchStore interface {
	Insert(ctx context.Context, doc *models.Document) (string, error)
	ListByUser(ctx context.Context, userID string) ([]models.Document, error)
	GetByID(ctx context.Context, id string) (*models.Document, error)
	Delete(ctx context.Context, id string) error
}

// FileStore defines the interface for file storage.
type FileStore interface {
	Upload(ctx context.Context, key string, data []byte, contentType string) error
	Download(ctx context.Context, key string) ([]byte, string, error)
	Remove(ctx context.Context, key string) error
}

// Handler holds research HTTP handlers.
type Handler struct {
	mongo       ResearchStore
	minio       FileStore
	aiClient    *AIClient
	latexClient *LaTeXClient
}

func NewHandler(mongo ResearchStore, minio FileStore, aiClient *AIClient, latexClient *LaTeXClient) *Handler {
	return &Handler{mongo: mongo, minio: minio, aiClient: aiClient, latexClient: latexClient}
}

// Create runs the full research pipeline and stores results.
func (h *Handler) Create(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value("user_id").(string)

	var req models.CreateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid request body"}`, http.StatusBadRequest)
		return
	}
	if req.Topic == "" || req.APIKey == "" {
		http.Error(w, `{"error":"topic and api_key are required"}`, http.StatusBadRequest)
		return
	}
	if req.Model == "" {
		req.Model = "mistral-medium-latest"
	}
	if req.Depth == "" {
		req.Depth = "Standard"
	}

	depth, ok := DepthConfig[req.Depth]
	if !ok {
		depth = DepthConfig["Standard"]
	}
	maxQueries, resultsPerQuery := depth[0], depth[1]

	// Step 1: generate search queries
	queries, err := h.aiClient.GenerateQueries(req.APIKey, req.Model, req.Topic)
	if err != nil {
		log.Printf("generate-queries error: %v", err)
		writeJSON(w, http.StatusBadGateway, map[string]string{
			"error": fmt.Sprintf("Failed to generate search queries: %v", err),
		})
		return
	}
	if len(queries) > maxQueries {
		queries = queries[:maxQueries]
	}

	// Step 2: web search
	sources, err := h.aiClient.Search(queries, resultsPerQuery)
	if err != nil {
		log.Printf("search error: %v", err)
		writeJSON(w, http.StatusBadGateway, map[string]string{
			"error": fmt.Sprintf("Web search failed: %v", err),
		})
		return
	}

	// Build context string
	ctxStr := ""
	for _, s := range sources {
		ctxStr += fmt.Sprintf("- %s: %s (Source: %s)\n", s.Title, s.Body, s.Href)
	}

	// Step 3: generate report
	latexBody, err := h.aiClient.GenerateReport(req.APIKey, req.Model, req.Topic, ctxStr, sources)
	if err != nil {
		log.Printf("generate-report error: %v", err)
		writeJSON(w, http.StatusBadGateway, map[string]string{
			"error": fmt.Sprintf("Report generation failed: %v", err),
		})
		return
	}
	if latexBody == "" {
		log.Printf("generate-report returned empty body")
		writeJSON(w, http.StatusBadGateway, map[string]string{
			"error": "AI service returned an empty report. Try again or use a different model.",
		})
		return
	}

	// Step 4: compile PDF (via latex-service)
	pdfBytes, err := h.latexClient.CompilePDF(latexBody, req.Topic)
	if err != nil {
		log.Printf("compile-pdf error (non-fatal): %v", err)
	}

	// Step 5: compile .tex (via latex-service)
	texSource, err := h.latexClient.CompileTex(latexBody, req.Topic)
	if err != nil {
		log.Printf("compile-tex error (non-fatal): %v", err)
	}

	// Step 6: upload to MinIO
	topicSlug := req.Topic
	if len(topicSlug) > 20 {
		topicSlug = topicSlug[:20]
	}
	pdfKey := fmt.Sprintf("%s/%s.pdf", userID, topicSlug)
	texKey := fmt.Sprintf("%s/%s.tex", userID, topicSlug)

	if pdfBytes != nil {
		if err := h.minio.Upload(r.Context(), pdfKey, pdfBytes, "application/pdf"); err != nil {
			log.Printf("minio pdf upload error: %v", err)
			pdfKey = ""
		}
	} else {
		pdfKey = ""
	}

	if texSource != "" {
		if err := h.minio.Upload(r.Context(), texKey, []byte(texSource), "application/x-tex"); err != nil {
			log.Printf("minio tex upload error: %v", err)
			texKey = ""
		}
	} else {
		texKey = ""
	}

	// Step 7: save to MongoDB
	doc := &models.Document{
		UserID:        userID,
		Topic:         req.Topic,
		LatexContent:  latexBody,
		Sources:       sources,
		ModelUsed:     req.Model,
		SearchQueries: queries,
		PDFObjectKey:  pdfKey,
		TexObjectKey:  texKey,
	}
	docID, err := h.mongo.Insert(r.Context(), doc)
	if err != nil {
		log.Printf("mongo insert error: %v", err)
		http.Error(w, `{"error":"failed to save research"}`, http.StatusInternalServerError)
		return
	}

	// Re-fetch to get the full object with _id
	saved, _ := h.mongo.GetByID(r.Context(), docID)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(saved)
}

// List returns all research for the current user.
func (h *Handler) List(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value("user_id").(string)
	docs, err := h.mongo.ListByUser(r.Context(), userID)
	if err != nil {
		http.Error(w, `{"error":"database error"}`, http.StatusInternalServerError)
		return
	}
	if docs == nil {
		docs = []models.Document{}
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(docs)
}

// Get returns a single research document.
func (h *Handler) Get(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	doc, err := h.mongo.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, `{"error":"not found"}`, http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(doc)
}

// Delete removes a research document and its files.
func (h *Handler) Delete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	doc, err := h.mongo.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, `{"error":"not found"}`, http.StatusNotFound)
		return
	}

	// Clean up MinIO
	if doc.PDFObjectKey != "" {
		h.minio.Remove(r.Context(), doc.PDFObjectKey)
	}
	if doc.TexObjectKey != "" {
		h.minio.Remove(r.Context(), doc.TexObjectKey)
	}

	if err := h.mongo.Delete(r.Context(), id); err != nil {
		http.Error(w, `{"error":"delete failed"}`, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"message":"deleted"}`))
}

// DownloadPDF streams the PDF from MinIO.
func (h *Handler) DownloadPDF(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	doc, err := h.mongo.GetByID(r.Context(), id)
	if err != nil || doc.PDFObjectKey == "" {
		http.Error(w, `{"error":"pdf not available"}`, http.StatusNotFound)
		return
	}

	data, ct, err := h.minio.Download(r.Context(), doc.PDFObjectKey)
	if err != nil {
		http.Error(w, `{"error":"download failed"}`, http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", ct)
	w.Header().Set("Content-Disposition", "attachment; filename=report.pdf")
	w.Write(data)
}

// DownloadTex streams the .tex source from MinIO.
func (h *Handler) DownloadTex(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	doc, err := h.mongo.GetByID(r.Context(), id)
	if err != nil || doc.TexObjectKey == "" {
		http.Error(w, `{"error":"tex not available"}`, http.StatusNotFound)
		return
	}

	data, _, err := h.minio.Download(r.Context(), doc.TexObjectKey)
	if err != nil {
		http.Error(w, `{"error":"download failed"}`, http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/x-tex")
	w.Header().Set("Content-Disposition", "attachment; filename=report.tex")
	w.Write(data)
}
