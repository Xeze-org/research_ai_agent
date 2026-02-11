package store

import (
	"context"

	"github.com/redis/go-redis/v9"
)

// NewRedisClient creates and pings a Redis client with optional password auth.
func NewRedisClient(ctx context.Context, addr, password string) (*redis.Client, error) {
	rdb := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: password,
	})
	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, err
	}
	return rdb, nil
}
