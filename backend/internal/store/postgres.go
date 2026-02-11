package store

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/ayush/research-ai-agent/backend/internal/models"
)

// PostgresStore handles user CRUD against PostgreSQL.
type PostgresStore struct {
	pool *pgxpool.Pool
}

func NewPostgresStore(pool *pgxpool.Pool) *PostgresStore {
	return &PostgresStore{pool: pool}
}

// Migrate creates the users table if it doesn't exist.
func (s *PostgresStore) Migrate(ctx context.Context) error {
	_, err := s.pool.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS users (
			id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
			username   VARCHAR(50)  UNIQUE NOT NULL,
			email      VARCHAR(255) UNIQUE NOT NULL,
			password   VARCHAR(255) NOT NULL,
			created_at TIMESTAMPTZ  DEFAULT NOW()
		)
	`)
	return err
}

func (s *PostgresStore) CreateUser(ctx context.Context, username, email, hashedPassword string) (*models.User, error) {
	var u models.User
	err := s.pool.QueryRow(ctx,
		`INSERT INTO users (username, email, password)
		 VALUES ($1, $2, $3)
		 RETURNING id, username, email, created_at`,
		username, email, hashedPassword,
	).Scan(&u.ID, &u.Username, &u.Email, &u.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("create user: %w", err)
	}
	return &u, nil
}

func (s *PostgresStore) GetUserByEmail(ctx context.Context, email string) (*models.User, error) {
	var u models.User
	err := s.pool.QueryRow(ctx,
		`SELECT id, username, email, password, created_at FROM users WHERE email = $1`, email,
	).Scan(&u.ID, &u.Username, &u.Email, &u.Password, &u.CreatedAt)
	if err != nil {
		return nil, err
	}
	return &u, nil
}

func (s *PostgresStore) GetUserByID(ctx context.Context, id string) (*models.User, error) {
	var u models.User
	err := s.pool.QueryRow(ctx,
		`SELECT id, username, email, created_at FROM users WHERE id = $1`, id,
	).Scan(&u.ID, &u.Username, &u.Email, &u.CreatedAt)
	if err != nil {
		return nil, err
	}
	return &u, nil
}
