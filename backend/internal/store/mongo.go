package store

import (
	"context"
	"fmt"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"

	"github.com/ayush/research-ai-agent/backend/internal/models"
)

// MongoStore handles research document CRUD in MongoDB.
type MongoStore struct {
	col *mongo.Collection
}

func NewMongoStore(db *mongo.Database) *MongoStore {
	return &MongoStore{col: db.Collection("research")}
}

func (s *MongoStore) Insert(ctx context.Context, doc *models.Document) (string, error) {
	doc.CreatedAt = time.Now()
	res, err := s.col.InsertOne(ctx, doc)
	if err != nil {
		return "", fmt.Errorf("mongo insert: %w", err)
	}
	oid := res.InsertedID.(primitive.ObjectID)
	return oid.Hex(), nil
}

func (s *MongoStore) ListByUser(ctx context.Context, userID string) ([]models.Document, error) {
	opts := options.Find().SetSort(bson.D{{Key: "created_at", Value: -1}})
	cur, err := s.col.Find(ctx, bson.M{"user_id": userID}, opts)
	if err != nil {
		return nil, err
	}
	defer cur.Close(ctx)

	var docs []models.Document
	if err := cur.All(ctx, &docs); err != nil {
		return nil, err
	}
	return docs, nil
}

func (s *MongoStore) GetByID(ctx context.Context, id string) (*models.Document, error) {
	oid, err := primitive.ObjectIDFromHex(id)
	if err != nil {
		return nil, fmt.Errorf("invalid id: %w", err)
	}
	var doc models.Document
	if err := s.col.FindOne(ctx, bson.M{"_id": oid}).Decode(&doc); err != nil {
		return nil, err
	}
	return &doc, nil
}

func (s *MongoStore) Delete(ctx context.Context, id string) error {
	oid, err := primitive.ObjectIDFromHex(id)
	if err != nil {
		return fmt.Errorf("invalid id: %w", err)
	}
	_, err = s.col.DeleteOne(ctx, bson.M{"_id": oid})
	return err
}
