package config

import "os"

// Config holds all service configuration loaded from environment variables.
type Config struct {
	Port           string
	PostgresDSN    string
	MongoURI       string
	MongoDB        string
	RedisAddr      string
	RedisPassword  string
	MinioEndpoint  string
	MinioAccessKey string
	MinioSecretKey string
	MinioBucket    string
	MinioUseSSL    bool
	AIServiceURL    string
	LaTeXServiceURL string
	SessionSecret   string
}

func Load() *Config {
	return &Config{
		Port:            getenv("PORT", "8080"),
		PostgresDSN:     getenv("POSTGRES_DSN", ""),
		MongoURI:        getenv("MONGO_URI", ""),
		MongoDB:         getenv("MONGO_DB", "research_agent"),
		RedisAddr:       getenv("REDIS_ADDR", "redis:6379"),
		RedisPassword:   getenv("REDIS_PASSWORD", ""),
		MinioEndpoint:   getenv("MINIO_ENDPOINT", "minio:9000"),
		MinioAccessKey:  getenv("MINIO_ACCESS_KEY", ""),
		MinioSecretKey:  getenv("MINIO_SECRET_KEY", ""),
		MinioBucket:     getenv("MINIO_BUCKET", "research-pdfs"),
		MinioUseSSL:     getenv("MINIO_USE_SSL", "false") == "true",
		AIServiceURL:    getenv("AI_SERVICE_URL", "http://ai-service:8000"),
		LaTeXServiceURL: getenv("LATEX_SERVICE_URL", "http://latex-service:8001"),
		SessionSecret:   getenv("SESSION_SECRET", ""),
	}
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
