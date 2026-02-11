package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/jackc/pgx/v5/pgxpool"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"

	"github.com/ayush/research-ai-agent/backend/internal/auth"
	"github.com/ayush/research-ai-agent/backend/internal/config"
	"github.com/ayush/research-ai-agent/backend/internal/middleware"
	"github.com/ayush/research-ai-agent/backend/internal/research"
	"github.com/ayush/research-ai-agent/backend/internal/store"
)

func main() {
	cfg := config.Load()
	ctx := context.Background()

	// ── PostgreSQL ────────────────────────────────────────────
	pgPool, err := pgxpool.New(ctx, cfg.PostgresDSN)
	if err != nil {
		log.Fatalf("postgres connect: %v", err)
	}
	defer pgPool.Close()
	pgStore := store.NewPostgresStore(pgPool)
	if err := pgStore.Migrate(ctx); err != nil {
		log.Fatalf("postgres migrate: %v", err)
	}

	// ── MongoDB ──────────────────────────────────────────────
	mongoClient, err := mongo.Connect(ctx, options.Client().ApplyURI(cfg.MongoURI))
	if err != nil {
		log.Fatalf("mongo connect: %v", err)
	}
	defer mongoClient.Disconnect(ctx)
	mongoDB := mongoClient.Database(cfg.MongoDB)
	mongoStore := store.NewMongoStore(mongoDB)

	// ── Redis ────────────────────────────────────────────────
	rdb, err := store.NewRedisClient(ctx, cfg.RedisAddr, cfg.RedisPassword)
	if err != nil {
		log.Fatalf("redis connect: %v", err)
	}
	defer rdb.Close()
	sessions := auth.NewSessionStore(rdb)

	// ── MinIO ────────────────────────────────────────────────
	minioStore, err := store.NewMinioStore(
		ctx, cfg.MinioEndpoint, cfg.MinioAccessKey,
		cfg.MinioSecretKey, cfg.MinioBucket, cfg.MinioUseSSL,
	)
	if err != nil {
		log.Fatalf("minio connect: %v", err)
	}

	// ── AI client ────────────────────────────────────────────
	aiClient := research.NewAIClient(cfg.AIServiceURL)

	// ── LaTeX client ─────────────────────────────────────────
	latexClient := research.NewLaTeXClient(cfg.LaTeXServiceURL)

	// ── Handlers ─────────────────────────────────────────────
	authHandler := auth.NewHandler(pgStore, sessions)
	researchHandler := research.NewHandler(mongoStore, minioStore, aiClient, latexClient)

	// ── Router ───────────────────────────────────────────────
	r := chi.NewRouter()
	r.Use(chimw.Logger)
	r.Use(chimw.Recoverer)
	r.Use(chimw.RealIP)
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{"http://localhost:5173", "http://localhost:3000"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Content-Type", "Authorization"},
		AllowCredentials: true,
		MaxAge:           300,
	}))

	// Health check
	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"status":"ok"}`))
	})

	// Auth routes (public)
	r.Route("/api/auth", func(r chi.Router) {
		r.Post("/register", authHandler.Register)
		r.Post("/login", authHandler.Login)
		r.Post("/logout", authHandler.Logout)
		r.With(middleware.RequireAuth(sessions)).Get("/me", authHandler.Me)
	})

	// Research routes (protected)
	r.Route("/api/research", func(r chi.Router) {
		r.Use(middleware.RequireAuth(sessions))
		r.Post("/", researchHandler.Create)
		r.Get("/", researchHandler.List)
		r.Get("/{id}", researchHandler.Get)
		r.Delete("/{id}", researchHandler.Delete)
		r.Get("/{id}/pdf", researchHandler.DownloadPDF)
		r.Get("/{id}/tex", researchHandler.DownloadTex)
	})

	// ── Server ───────────────────────────────────────────────
	srv := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      r,
		ReadTimeout:  5 * time.Minute,
		WriteTimeout: 5 * time.Minute,
	}

	go func() {
		log.Printf("Backend listening on :%s", cfg.Port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server error: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down...")
	shutCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	srv.Shutdown(shutCtx)
}
