package models

import (
	"time"

	"go.mongodb.org/mongo-driver/bson/primitive"
)

// Source is a web source cited in the report.
type Source struct {
	Title string `json:"title" bson:"title"`
	Body  string `json:"body"  bson:"body"`
	Href  string `json:"href"  bson:"href"`
}

// Document is a single research report stored in MongoDB.
type Document struct {
	ID            primitive.ObjectID `json:"id"              bson:"_id,omitempty"`
	UserID        string             `json:"user_id"         bson:"user_id"`
	Topic         string             `json:"topic"           bson:"topic"`
	LatexContent  string             `json:"latex_content"   bson:"latex_content"`
	Sources       []Source           `json:"sources"         bson:"sources"`
	ModelUsed     string             `json:"model_used"      bson:"model_used"`
	SearchQueries []string           `json:"search_queries"  bson:"search_queries"`
	PDFObjectKey  string             `json:"pdf_object_key"  bson:"pdf_object_key"`
	TexObjectKey  string             `json:"tex_object_key"  bson:"tex_object_key"`
	CreatedAt     time.Time          `json:"created_at"      bson:"created_at"`
}

// CreateRequest is the JSON body for POST /api/research.
type CreateRequest struct {
	Topic  string `json:"topic"`
	Model  string `json:"model"`
	Depth  string `json:"depth"`
	APIKey string `json:"api_key"`
}
