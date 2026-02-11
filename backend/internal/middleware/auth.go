package middleware

import (
	"context"
	"net/http"

	"github.com/ayush/research-ai-agent/backend/internal/auth"
)

// RequireAuth is middleware that validates the session cookie and
// injects the user_id into the request context.
func RequireAuth(sessions *auth.SessionStore) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			cookie, err := r.Cookie(auth.SessionCookie)
			if err != nil {
				http.Error(w, `{"error":"not authenticated"}`, http.StatusUnauthorized)
				return
			}

			userID, err := sessions.Get(r.Context(), cookie.Value)
			if err != nil || userID == "" {
				http.Error(w, `{"error":"session expired"}`, http.StatusUnauthorized)
				return
			}

			ctx := context.WithValue(r.Context(), "user_id", userID)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}
