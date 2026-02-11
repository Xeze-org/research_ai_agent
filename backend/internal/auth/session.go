package auth

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

const (
	SessionTTL    = 24 * time.Hour
	SessionCookie = "session_id"
)

// SessionStore wraps Redis for session management.
type SessionStore struct {
	rdb *redis.Client
}

func NewSessionStore(rdb *redis.Client) *SessionStore {
	return &SessionStore{rdb: rdb}
}

// Create stores a new session mapping sessionID -> userID.
func (s *SessionStore) Create(ctx context.Context, userID string) (string, error) {
	sid := uuid.New().String()
	err := s.rdb.Set(ctx, "session:"+sid, userID, SessionTTL).Err()
	return sid, err
}

// Get returns the userID for a session, or "" if not found / expired.
func (s *SessionStore) Get(ctx context.Context, sessionID string) (string, error) {
	val, err := s.rdb.Get(ctx, "session:"+sessionID).Result()
	if err == redis.Nil {
		return "", nil
	}
	return val, err
}

// Delete removes a session.
func (s *SessionStore) Delete(ctx context.Context, sessionID string) error {
	return s.rdb.Del(ctx, "session:"+sessionID).Err()
}
